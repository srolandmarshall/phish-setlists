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

from ..constants import (
    DEFAULT_SET_DURATION_TARGETS,
    DEFAULT_SET_LENGTHS,
    ERA_DEFINITIONS,
    SET_ALIASES,
    THREE_SET_DURATION_OVERRIDES,
)
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


def _quantile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    clamped = min(max(percentile, 0.0), 1.0)
    index = clamped * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


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


def previous_show_tracks(
    session: Session,
    reference_date: date,
    *,
    era: Optional[str] = None,
    year: Optional[int] = None,
) -> List[str]:
    """Return titles from the show immediately preceding ``reference_date``."""

    show_stmt = (
        filter_shows_query(
            cutoff_date=reference_date,
            era=era,
            year=year,
        )
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
class SegmentPattern:
    """Represents a single contiguous performance block (set or encore)."""

    show_id: int
    date: date
    label: str
    titles: Tuple[str, ...]
    total_duration: float


@dataclass(frozen=True)
class SegmentStatistics:
    """Aggregations describing song structures for a specific set label."""

    label: str
    patterns: List[SegmentPattern]
    count_histogram: Dict[int, int]
    average_durations_by_count: Dict[int, float]
    top_sequences: List[Tuple[Tuple[str, ...], int]]
    longform_songs: List[Tuple[str, float]]
    adjacency_map: Dict[str, Dict[str, int]]
    song_durations: Dict[str, float]


def segment_statistics(
    session: Session,
    *,
    target_set: str,
    cutoff_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
    top_n_sequences: int = 10,
    longform_threshold: int = 12 * 60,
) -> SegmentStatistics:
    """Compute descriptive statistics for the requested canonical set label."""

    canonical_label = target_set

    show_ids_subquery = filter_shows_query(
        cutoff_date=cutoff_date,
        era=era,
        year=year,
    ).subquery()

    track_stmt = (
        select(Show.id, Show.date, Track.set, Track.position, Track.title, Track.duration)
        .join(show_ids_subquery, Show.id == show_ids_subquery.c.id)
        .join(Track, Track.show_id == Show.id)
        .order_by(Show.date.asc(), Track.position.asc())
    )

    segments: Dict[Tuple[int, str], List[Tuple[int, str, float]]] = {}
    segment_dates: Dict[Tuple[int, str], date] = {}
    for show_id, show_date, raw_label, position, title, duration in session.execute(track_stmt):
        canonical = normalize_set_label(raw_label)
        if canonical != canonical_label:
            continue
        seconds = (duration or 0) / 1000.0
        key = (show_id, raw_label)
        segments.setdefault(key, []).append((position, title, seconds))
        segment_dates[key] = show_date

    patterns: List[SegmentPattern] = []
    count_histogram: Counter[int] = Counter()
    duration_by_count: Dict[int, List[float]] = {}
    sequence_counter: Counter[Tuple[str, ...]] = Counter()
    longform_song_durations: Dict[str, List[float]] = {}
    song_duration_samples: Dict[str, List[float]] = {}

    for (show_id, raw_label), tracks in segments.items():
        tracks.sort(key=lambda item: item[0])
        titles = tuple(title for _, title, _ in tracks)
        total_duration = sum(duration for _, _, duration in tracks)
        count = len(titles)

        patterns.append(
            SegmentPattern(
                show_id=show_id,
                date=segment_dates[(show_id, raw_label)],
                label=raw_label,
                titles=titles,
                total_duration=total_duration,
            )
        )
        count_histogram[count] += 1
        duration_by_count.setdefault(count, []).append(total_duration)
        sequence_counter[titles] += 1

        for _, title, duration in tracks:
            if duration > 0:
                longform_song_durations.setdefault(title, []).append(duration)
                song_duration_samples.setdefault(title, []).append(duration)

    average_durations = {
        count: mean(values) if values else 0.0 for count, values in duration_by_count.items()
    }

    top_sequences = sequence_counter.most_common(top_n_sequences)

    adjacency_map: Dict[str, Dict[str, int]] = {}
    for sequence, weight in sequence_counter.items():
        if len(sequence) < 2:
            continue
        for first, second in zip(sequence, sequence[1:]):
            adjacency_map.setdefault(first, {})
            adjacency_map[first][second] = adjacency_map[first].get(second, 0) + weight

    longform_songs = [
        (title, mean(durations))
        for title, durations in longform_song_durations.items()
        if mean(durations) >= longform_threshold
    ]
    longform_songs.sort(key=lambda item: item[1], reverse=True)

    song_durations = {
        title: _quantile(values, 0.8) if values else 0.0
        for title, values in song_duration_samples.items()
    }

    return SegmentStatistics(
        label=canonical_label,
        patterns=patterns,
        count_histogram=dict(count_histogram),
        average_durations_by_count=average_durations,
        top_sequences=top_sequences,
        longform_songs=longform_songs,
        adjacency_map={key: dict(value.items()) for key, value in adjacency_map.items()},
        song_durations=song_durations,
    )


def encore_statistics(
    session: Session,
    *,
    cutoff_date: Optional[date] = None,
    era: Optional[str] = None,
    year: Optional[int] = None,
    top_n_sequences: int = 10,
    longform_threshold: int = 12 * 60,
) -> SegmentStatistics:
    """Backward-compatible wrapper returning encore statistics."""

    return segment_statistics(
        session,
        target_set="encore",
        cutoff_date=cutoff_date,
        era=era,
        year=year,
        top_n_sequences=top_n_sequences,
        longform_threshold=longform_threshold,
    )


# Backward-compatible aliases
EncoreStatistics = SegmentStatistics
EncorePattern = SegmentPattern


def songs_seen_by_date(
    session: Session,
    cutoff: date,
    *,
    era: Optional[str] = None,
    year: Optional[int] = None,
) -> Iterable[str]:
    """Return the set of song titles that have appeared up to ``cutoff``."""

    show_ids = filter_shows_query(
        cutoff_date=cutoff,
        era=era,
        year=year,
    ).subquery()

    track_stmt = select(Track.title).join(show_ids, Track.show_id == show_ids.c.id)
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

    duration_targets: Dict[str, Tuple[int, int]] = dict(DEFAULT_SET_DURATION_TARGETS)
    if num_sets == 3:
        duration_targets.update(THREE_SET_DURATION_OVERRIDES)

    target_segments = [f"set{idx}" for idx in range(1, num_sets + 1)]
    if include_encore:
        target_segments.append("encore")

    segment_stats_map: Dict[str, SegmentStatistics] = {}
    for canonical in target_segments:
        segment_stats_map[canonical] = segment_statistics(
            session,
            target_set=canonical,
            cutoff_date=cutoff_date,
            era=era,
            year=year,
            top_n_sequences=0,
        )

    def pick_length(label: str) -> int:
        distribution = stats.get(label)
        if not distribution or not distribution.histogram:
            return DEFAULT_SET_LENGTHS.get(label, 8)

        histogram = dict(distribution.histogram)
        segment_stats = segment_stats_map.get(label)
        duration_range = duration_targets.get(label)

        if duration_range and segment_stats:
            lower, upper = duration_range
            averages = segment_stats.average_durations_by_count
            eligible = {
                count: weight
                for count, weight in histogram.items()
                if lower <= averages.get(count, 0.0) <= upper
            }
            if eligible:
                histogram = eligible
            else:
                target_mid = (lower + upper) / 2

                def duration_distance(count: int) -> float:
                    duration = averages.get(count)
                    if duration is None or duration <= 0:
                        return float("inf")
                    return abs(duration - target_mid)

                closest = min(
                    histogram.keys(),
                    key=lambda count: (duration_distance(count), -histogram[count]),
                )
                return closest

        weighted_items = list(histogram.items())
        total_weight = sum(weight for _, weight in weighted_items)
        if total_weight <= 0:
            return DEFAULT_SET_LENGTHS.get(label, 8)

        choice = rng.random() * total_weight
        cumulative = 0.0
        for length, weight in weighted_items:
            cumulative += weight
            if choice <= cumulative:
                return length
        return max(histogram, key=histogram.get)

    selected: Dict[str, int] = {}
    for idx in range(1, num_sets + 1):
        label = f"set{idx}"
        selected[label] = pick_length(label)

    if include_encore:
        selected["encore"] = pick_length("encore")

    return selected
