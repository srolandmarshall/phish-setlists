"""Historical data utilities backing the generator."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from random import Random
from statistics import mean, median
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.sql import Select

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import DEFAULT_SET_LENGTHS, ERA_DEFINITIONS, SET_ALIASES
from ..models import Show, Track


@dataclass(frozen=True)
class SongFrequency:
    """Aggregated statistics about a song in a particular context."""

    title: str
    count: int

    @property
    def weight(self) -> float:
        return float(self.count)


def normalize_set_label(label: str) -> str:
    """Normalize raw set designator into canonical buckets."""

    normalized = label.strip()
    for canonical, aliases in SET_ALIASES.items():
        if normalized in aliases:
            return canonical
    return normalized.lower()


def filter_shows_query(
    cutoff_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
) -> Select:
    """Construct a base selectable for shows respecting temporal filters."""

    query = select(Show)

    bounds = []
    if cutoff_date:
        bounds.append(Show.date <= cutoff_date)
    if year:
        year_end = date(year, 12, 31)
        bounds.append(Show.date <= year_end)
    if era:
        era_def = ERA_DEFINITIONS.get(era)
        if era_def:
            bounds.append(Show.date >= era_def.start)
            bounds.append(Show.date <= era_def.end)

    for clause in bounds:
        query = query.where(clause)

    return query


def previous_show_tracks(session: Session, reference_date: date) -> List[str]:
    """Return titles from the show immediately preceding ``reference_date``."""

    show_stmt = (
        select(Show)
        .where(Show.date < reference_date)
        .order_by(Show.date.desc())
        .limit(1)
    )
    previous_show = session.execute(show_stmt).scalar_one_or_none()
    if not previous_show:
        return []

    tracks_stmt = (
        select(Track.title)
        .where(Track.show_id == previous_show.id)
        .order_by(Track.position.asc())
    )
    return [row[0] for row in session.execute(tracks_stmt)]


def song_frequencies_by_set(
    session: Session,
    cutoff_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, List[SongFrequency]]:
    """Compute song appearance frequencies keyed by normalized set label."""

    show_ids_subquery = filter_shows_query(
        cutoff_date=cutoff_date,
        era=era,
        year=year,
    ).subquery()

    track_stmt = (
        select(Track.title, Track.set)
        .join(show_ids_subquery, Track.show_id == show_ids_subquery.c.id)
    )

    counters: Dict[str, Counter] = {}
    for title, set_label in session.execute(track_stmt):
        canonical_set = normalize_set_label(set_label)
        counters.setdefault(canonical_set, Counter()).update([title])

    frequencies: Dict[str, List[SongFrequency]] = {}
    for set_label, counter in counters.items():
        frequencies[set_label] = [
            SongFrequency(title=title, count=count)
            for title, count in counter.most_common()
        ]

    return frequencies


@dataclass(frozen=True)
class EncorePattern:
    """Represents a single encore performance sequence."""

    show_id: int
    date: date
    titles: Tuple[str, ...]
    total_duration: float


@dataclass(frozen=True)
class EncoreStatistics:
    """Aggregations describing encore structures."""

    patterns: List[EncorePattern]
    count_histogram: Dict[int, int]
    average_durations_by_count: Dict[int, float]
    top_sequences: List[Tuple[Tuple[str, ...], int]]
    longform_songs: List[Tuple[str, float]]


def encore_statistics(
    session: Session,
    *,
    cutoff_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
    top_n_sequences: int = 10,
    longform_threshold: int = 12 * 60,
) -> EncoreStatistics:
    """Compute descriptive statistics about encore song selections."""

    show_ids_subquery = filter_shows_query(
        cutoff_date=cutoff_date,
        era=era,
        year=year,
    ).subquery()

    encore_stmt = (
        select(Show.id, Show.date, Track.position, Track.title, Track.duration)
        .join(show_ids_subquery, Show.id == show_ids_subquery.c.id)
        .join(Track, Track.show_id == Show.id)
        .where(Track.set.in_(SET_ALIASES["encore"]))
        .order_by(Show.date.asc(), Track.position.asc())
    )

    encore_by_show: Dict[int, List[Tuple[int, str, float]]] = {}
    encore_dates: Dict[int, date] = {}
    for show_id, show_date, position, title, duration in session.execute(encore_stmt):
        seconds = (duration or 0) / 1000.0
        encore_by_show.setdefault(show_id, []).append((position, title, seconds))
        encore_dates[show_id] = show_date

    patterns: List[EncorePattern] = []
    count_histogram: Counter[int] = Counter()
    duration_by_count: Dict[int, List[float]] = {}
    sequence_counter: Counter[Tuple[str, ...]] = Counter()
    longform_song_durations: Dict[str, List[float]] = {}

    for show_id, tracks in encore_by_show.items():
        tracks.sort(key=lambda item: item[0])
        titles = tuple(title for _, title, _ in tracks)
        total_duration = sum(duration for _, _, duration in tracks)
        count = len(titles)

        patterns.append(
            EncorePattern(
                show_id=show_id,
                date=encore_dates[show_id],
                titles=titles,
                total_duration=total_duration,
            )
        )
        count_histogram[count] += 1
        duration_by_count.setdefault(count, []).append(total_duration)
        sequence_counter[titles] += 1

        for title, duration in [(title, duration) for _, title, duration in tracks]:
            if duration > 0:
                longform_song_durations.setdefault(title, []).append(duration)

    average_durations = {
        count: mean(values) if values else 0.0 for count, values in duration_by_count.items()
    }

    top_sequences = sequence_counter.most_common(top_n_sequences)

    longform_songs = [
        (title, mean(durations))
        for title, durations in longform_song_durations.items()
        if mean(durations) >= longform_threshold
    ]
    longform_songs.sort(key=lambda item: item[1], reverse=True)

    return EncoreStatistics(
        patterns=patterns,
        count_histogram=dict(count_histogram),
        average_durations_by_count=average_durations,
        top_sequences=top_sequences,
        longform_songs=longform_songs,
    )


def songs_seen_by_date(session: Session, cutoff: date) -> Iterable[str]:
    """Return the set of song titles that have appeared up to ``cutoff``."""

    track_stmt = (
        select(Track.title)
        .join(Show, Track.show_id == Show.id)
        .where(Show.date <= cutoff)
    )
    return {row[0] for row in session.execute(track_stmt)}


@dataclass(frozen=True)
class SetLengthStatistics:
    """Describes observed song counts for a canonical set label."""

    histogram: Dict[int, int]
    average: float
    median: float
    minimum: int
    maximum: int


def set_length_statistics(
    session: Session,
    *,
    cutoff_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, SetLengthStatistics]:
    """Summarize how many songs typically appear in each set label."""

    show_ids_subquery = filter_shows_query(
        cutoff_date=cutoff_date,
        era=era,
        year=year,
    ).subquery()

    track_stmt = (
        select(Track.show_id, Track.set)
        .join(show_ids_subquery, Track.show_id == show_ids_subquery.c.id)
    )

    counts: Dict[Tuple[int, str], int] = {}
    for show_id, raw_label in session.execute(track_stmt):
        canonical = normalize_set_label(raw_label)
        if canonical not in DEFAULT_SET_LENGTHS:
            continue
        counts[(show_id, canonical)] = counts.get((show_id, canonical), 0) + 1

    histograms: Dict[str, Counter[int]] = {}
    for (_, canonical), total in counts.items():
        histograms.setdefault(canonical, Counter()).update([total])

    stats: Dict[str, SetLengthStatistics] = {}
    for canonical, histogram in histograms.items():
        expanded: List[int] = []
        for length, freq in histogram.items():
            expanded.extend([length] * freq)

        if not expanded:
            continue

        expanded.sort()
        avg = sum(expanded) / len(expanded)
        stats[canonical] = SetLengthStatistics(
            histogram=dict(sorted(histogram.items())),
            average=avg,
            median=median(expanded),
            minimum=expanded[0],
            maximum=expanded[-1],
        )

    return stats


def random_set_lengths(
    session: Session,
    *,
    reference_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
    num_sets: int = 2,
    include_encore: bool = True,
    rng: Optional[Random] = None,
) -> Dict[str, int]:
    """Sample realistic set lengths using historical distributions."""

    if rng is None:
        rng = Random()

    cutoff_date: Optional[date] = reference_date
    if year:
        year_end = date(year, 12, 31)
        if cutoff_date is None or cutoff_date > year_end:
            cutoff_date = year_end

    stats = set_length_statistics(
        session,
        cutoff_date=cutoff_date,
        era=era,
        year=year,
    )

    def pick_length(label: str) -> int:
        distribution = stats.get(label)
        if not distribution or not distribution.histogram:
            return DEFAULT_SET_LENGTHS.get(label, 8)

        total_weight = sum(distribution.histogram.values())
        choice = rng.random() * total_weight
        cumulative = 0.0
        for length, weight in distribution.histogram.items():
            cumulative += weight
            if choice <= cumulative:
                return length
        return max(distribution.histogram, key=distribution.histogram.get)

    selected: Dict[str, int] = {}
    for idx in range(1, num_sets + 1):
        label = f"set{idx}"
        selected[label] = pick_length(label)

    if include_encore:
        selected["encore"] = pick_length("encore")

    return selected
