"""Baseline setlist generator using historical frequency heuristics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from random import Random
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import DEFAULT_SET_LENGTHS, ERA_DEFINITIONS
from ..models import Show
from .historical import (
    SegmentStatistics,
    SongFrequency,
    previous_show_tracks,
    segment_statistics,
    song_frequencies_by_set,
    songs_seen_by_date,
)
from .rules import apply_rules


@dataclass(slots=True)
class SetSegment:
    """A contiguous block of songs, e.g., Set 1 or Encore."""

    label: str
    songs: List[str] = field(default_factory=list)


@dataclass(slots=True)
class GenerationMetadata:
    """Informational metadata about how a setlist was produced."""

    reference_date: date
    cutoff_date: date
    era: Optional[str]
    year: Optional[int]
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedSetlist:
    """Container for the generated show structure."""

    sets: List[SetSegment]
    encore: Optional[SetSegment]
    metadata: GenerationMetadata


class SetlistGenerator:
    """Generate Phish setlists from historical performance data."""

    def __init__(
        self,
        session: Session,
        rng: Optional[Random] = None,
        *,
        adjacency_bonus: float = 0.3,
        adjacency_min_support: int = 2,
    ):
        self.session = session
        self.rng = rng or Random()
        self._adjacency_bonus = max(0.0, adjacency_bonus)
        self._adjacency_min_support = max(0, adjacency_min_support)

    def generate(
        self,
        *,
        reference_date: Optional[date] = None,
        num_sets: int = 2,
        include_encore: bool = True,
        set_lengths: Optional[Dict[str, int]] = None,
        era: Optional[str] = None,
        year: Optional[int] = None,
        exclude_previous_show: bool = True,
    ) -> GeneratedSetlist:
        """Produce a setlist honoring baseline Phish show conventions.

        Args:
            reference_date: Anchor date for the generation context. If omitted, the
                most recent show in the database is used.
            num_sets: Number of main sets to generate (2 or 3 typical).
            include_encore: Whether to include an encore block.
            set_lengths: Optional overrides for how many songs each set should contain.
            era: Era identifier (e.g., "3.0") restricting historical data.
            year: Restrict historical data to performances through the end of ``year``.
            exclude_previous_show: When ``True`` (default), songs from the previous show
                are excluded from selection.
        """

        if num_sets not in (2, 3):
            raise ValueError("num_sets must be 2 or 3")

        if era and era not in ERA_DEFINITIONS:
            raise ValueError(f"Unsupported era '{era}'. Known eras: {', '.join(ERA_DEFINITIONS)}")

        reference = reference_date or self._latest_show_date()
        cutoff = reference
        if year and cutoff.year > year:
            cutoff = date(year, 12, 31)

        lengths = {**DEFAULT_SET_LENGTHS, **(set_lengths or {})}

        previous_show_songs: Set[str] = set()
        previous_show_date: Optional[date] = None
        if exclude_previous_show:
            exclusion_reference = cutoff
            previous_show_songs = set(
                previous_show_tracks(
                    self.session,
                    exclusion_reference,
                    era=era,
                    year=year,
                )
            )
            previous_show_date = self._previous_show_date(
                exclusion_reference,
                era=era,
                year=year,
            )

        seen_songs = songs_seen_by_date(
            self.session,
            cutoff,
            era=era,
            year=year,
        )

        frequencies_by_set = song_frequencies_by_set(
            self.session,
            cutoff_date=cutoff,
            era=era,
            year=year,
        )

        # Pre-compute segment statistics and long-form song references.
        segment_stats_map: Dict[str, Optional[SegmentStatistics]] = {}
        segment_longform_titles: Dict[str, Set[str]] = {}

        target_segments = [f"set{idx}" for idx in range(1, num_sets + 1)]
        if include_encore:
            target_segments.append("encore")

        for canonical in target_segments:
            stats = segment_statistics(
                self.session,
                target_set=canonical,
                cutoff_date=cutoff,
                era=era,
                year=year,
                top_n_sequences=50,
            )
            segment_stats_map[canonical] = stats
            segment_longform_titles[canonical] = {title for title, _ in stats.longform_songs}

        used_songs: Set[str] = set(previous_show_songs)
        metadata_notes: List[str] = []
        if exclude_previous_show and previous_show_songs:
            label = (
                previous_show_date.isoformat() if isinstance(previous_show_date, date) else "the previous show"
            )
            metadata_notes.append(
                f"Excluded {len(previous_show_songs)} songs played on {label}"
            )

        sets: List[SetSegment] = []
        for idx in range(1, num_sets + 1):
            canonical_set = f"set{idx}"
            set_label = f"Set {idx}"
            desired = lengths.get(canonical_set, 8)

            set_stats = segment_stats_map.get(canonical_set)
            set_longform = segment_longform_titles.get(canonical_set, set())

            adjacency_map = set_stats.adjacency_map if set_stats else None

            set_songs, set_notes = self._compose_segment(
                canonical_set=canonical_set,
                segment_label=set_label,
                desired_count=desired,
                frequencies_by_set=frequencies_by_set,
                stats=set_stats,
                used_songs=used_songs,
                eligible_songs=seen_songs,
                allow_sequences=True,
                allow_single_song=False,
                longform_titles=set_longform,
                adjacency_map=adjacency_map,
            )
            metadata_notes.extend(set_notes)
            sets.append(SetSegment(label=set_label, songs=set_songs))

        encore_segment: Optional[SetSegment] = None
        if include_encore:
            desired_encore = lengths.get("encore", DEFAULT_SET_LENGTHS["encore"])
            encore_stats = segment_stats_map.get("encore")
            encore_longform = segment_longform_titles.get("encore", set())
            encore_adjacency = encore_stats.adjacency_map if encore_stats else None

            encore_songs, encore_notes = self._compose_segment(
                canonical_set="encore",
                segment_label="Encore",
                desired_count=desired_encore,
                frequencies_by_set=frequencies_by_set,
                stats=encore_stats,
                used_songs=used_songs,
                eligible_songs=seen_songs,
                allow_sequences=True,
                allow_single_song=True,
                longform_titles=encore_longform,
                adjacency_map=encore_adjacency,
            )
            metadata_notes.extend(encore_notes)
            encore_segment = SetSegment(label="Encore", songs=encore_songs)

        apply_rules(
            sets=sets,
            encore=encore_segment,
            stats_by_segment=segment_stats_map,
            eligible_songs=seen_songs,
            used_songs=used_songs,
            metadata_notes=metadata_notes,
        )

        metadata = GenerationMetadata(
            reference_date=reference,
            cutoff_date=cutoff,
            era=era,
            year=year,
            notes=metadata_notes,
        )

        return GeneratedSetlist(sets=sets, encore=encore_segment, metadata=metadata)

    def _latest_show_date(self) -> date:
        stmt = select(Show.date).order_by(Show.date.desc()).limit(1)
        latest = self.session.execute(stmt).scalar_one_or_none()
        if latest is None:
            raise RuntimeError("No shows available in database.")
        return latest

    def _previous_show_date(
        self,
        reference: date,
        *,
        era: Optional[str],
        year: Optional[int],
    ) -> Optional[date]:
        stmt = select(Show.date).where(Show.date < reference)

        if year:
            year_end = date(year, 12, 31)
            upper_bound = min(year_end, reference)
            stmt = stmt.where(Show.date <= upper_bound)

        if era and era in ERA_DEFINITIONS:
            era_def = ERA_DEFINITIONS[era]
            stmt = stmt.where(Show.date >= era_def.start, Show.date <= era_def.end)

        stmt = stmt.order_by(Show.date.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    def _compose_segment(
        self,
        *,
        canonical_set: str,
        segment_label: str,
        desired_count: int,
        frequencies_by_set: Dict[str, List[SongFrequency]],
        used_songs: Set[str],
        eligible_songs: Iterable[str],
        stats: Optional[SegmentStatistics],
        allow_sequences: bool,
        allow_single_song: bool,
        longform_titles: Set[str],
        adjacency_map: Optional[Dict[str, Dict[str, int]]],
    ) -> Tuple[List[str], List[str]]:
        notes: List[str] = []
        songs: List[str] = []

        max_length = desired_count if desired_count > 0 else None

        if allow_sequences and stats is not None and desired_count > 0:
            sequence = self._choose_sequence(
                stats=stats,
                used_songs=used_songs,
                eligible_songs=eligible_songs,
                desired_length=desired_count,
                max_length=max_length,
            )
            if sequence:
                songs.extend(sequence)
                used_songs.update(sequence)

        remaining = max(0, desired_count - len(songs))
        if remaining > 0:
            previous_song = songs[-1] if songs else None
            additional = self._pick_songs_for_set(
                frequencies_by_set,
                canonical_set,
                remaining,
                used_songs,
                eligible_songs,
                previous_song=previous_song,
                adjacency_map=adjacency_map,
            )
            songs.extend(additional)

        if (
            not allow_single_song
            and desired_count > 1
            and len(songs) == 1
            and songs[0] not in longform_titles
        ):
            previous_song = songs[-1] if songs else None
            extra = self._pick_songs_for_set(
                frequencies_by_set,
                canonical_set,
                1,
                used_songs,
                eligible_songs,
                previous_song=previous_song,
                adjacency_map=adjacency_map,
            )
            songs.extend(extra)

        # Ensure uniqueness and order preservation after extensions.
        seen: Set[str] = set()
        deduped: List[str] = []
        for song in songs:
            if song in seen:
                continue
            seen.add(song)
            deduped.append(song)
        songs = deduped

        used_songs.update(songs)

        if not songs:
            notes.append(f"No songs selected for {segment_label}; limited historical data.")
        elif len(songs) < desired_count:
            notes.append(
                f"Only selected {len(songs)}/{desired_count} songs for {segment_label}; limited historical data."
            )
        elif len(songs) == 1:
            song = songs[0]
            if song in longform_titles:
                notes.append(f"{segment_label} anchored by long-form performance of {song}.")
            elif desired_count > 1:
                if allow_single_song:
                    notes.append(
                        f"{segment_label} limited to a single song without long-form precedent;"
                        " additional data may unlock longer segments."
                    )
                else:
                    notes.append(
                        f"{segment_label} limited to a single song; limited historical data."
                    )

        return songs, notes

    def _choose_sequence(
        self,
        *,
        stats: SegmentStatistics,
        used_songs: Set[str],
        eligible_songs: Iterable[str],
        desired_length: int,
        max_length: Optional[int],
    ) -> Optional[Tuple[str, ...]]:
        eligible = set(eligible_songs)

        def valid(sequence: Tuple[str, ...]) -> bool:
            if max_length is not None and len(sequence) > max_length:
                return False
            return all(song in eligible and song not in used_songs for song in sequence)

        candidates = [(seq, weight) for seq, weight in stats.top_sequences if valid(seq)]
        if not candidates:
            return None

        multi_candidates = [
            (seq, weight)
            for seq, weight in candidates
            if len(seq) >= 2
        ]

        if multi_candidates:
            lengths = {len(seq) for seq, _ in multi_candidates}
            target_length = min(
                lengths,
                key=lambda length: (abs(desired_length - length), -length),
            )
            filtered = [item for item in multi_candidates if len(item[0]) == target_length]
            choice = self._weighted_sequence_choice(filtered)
            if choice:
                return choice

        single_candidates = [(seq, weight) for seq, weight in candidates if len(seq) == 1]
        if single_candidates:
            return self._weighted_sequence_choice(single_candidates)

        return None

    def _weighted_sequence_choice(
        self, candidates: List[Tuple[Tuple[str, ...], int]]
    ) -> Optional[Tuple[str, ...]]:
        total_weight = sum(max(weight, 1) for _, weight in candidates)
        if total_weight <= 0:
            return None

        rand = self.rng.random() * total_weight
        cumulative = 0.0
        for sequence, weight in candidates:
            cumulative += max(weight, 1)
            if rand <= cumulative:
                return sequence
        return candidates[-1][0]

    def _pick_songs_for_set(
        self,
        frequencies_by_set: Dict[str, List[SongFrequency]],
        target_set: str,
        desired_count: int,
        used_songs: Set[str],
        eligible_songs: Iterable[str],
        *,
        previous_song: Optional[str] = None,
        adjacency_map: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[str]:
        pool = self._build_candidate_pool(frequencies_by_set, target_set, eligible_songs)
        selection: List[str] = []
        prev = previous_song

        for _ in range(desired_count):
            choice = self._weighted_pick(
                pool,
                used_songs,
                previous_song=prev,
                adjacency_map=adjacency_map,
            )
            if not choice:
                break
            selection.append(choice)
            used_songs.add(choice)
            prev = choice
            pool = [freq for freq in pool if freq.title not in used_songs]

        return selection

    def _build_candidate_pool(
        self,
        frequencies_by_set: Dict[str, List[SongFrequency]],
        target_set: str,
        eligible_songs: Iterable[str],
    ) -> List[SongFrequency]:
        eligible = set(eligible_songs)

        candidates = [
            freq for freq in frequencies_by_set.get(target_set, []) if freq.title in eligible
        ]
        if not candidates and target_set.startswith("set"):
            # Fall back to any non-encore appearances if the specific set lacks data.
            combined: Dict[str, SongFrequency] = {}
            for key, freqs in frequencies_by_set.items():
                if key.startswith("set"):
                    for freq in freqs:
                        if freq.title not in eligible:
                            continue
                        current = combined.get(freq.title)
                        if current:
                            combined[freq.title] = SongFrequency(
                                title=freq.title,
                                count=current.count + freq.count,
                            )
                        else:
                            combined[freq.title] = freq
            candidates = sorted(combined.values(), key=lambda f: f.count, reverse=True)

        return candidates

    def _weighted_pick(
        self,
        pool: List[SongFrequency],
        used_songs: Set[str],
        *,
        previous_song: Optional[str] = None,
        adjacency_map: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Optional[str]:
        available = [freq for freq in pool if freq.title not in used_songs]
        if not available:
            return None

        weighted_candidates: List[Tuple[SongFrequency, float]] = [
            (freq, float(freq.weight)) for freq in available
        ]

        if previous_song and adjacency_map:
            neighbors = adjacency_map.get(previous_song)
            if neighbors:
                filtered_neighbors = {
                    song: count
                    for song, count in neighbors.items()
                    if count >= self._adjacency_min_support
                }
                if filtered_neighbors:
                    max_neighbor = max(filtered_neighbors.values())
                else:
                    max_neighbor = 0
                if max_neighbor > 0:
                    for idx, (freq, weight) in enumerate(weighted_candidates):
                        neighbor_weight = filtered_neighbors.get(freq.title)
                        if neighbor_weight:
                            normalized = neighbor_weight / max_neighbor
                            boost = 1.0 + self._adjacency_bonus * normalized
                            weighted_candidates[idx] = (freq, weight * boost)

        total_weight = sum(weight for _, weight in weighted_candidates)
        if total_weight <= 0:
            return None

        rand = self.rng.random() * total_weight
        cumulative = 0.0
        for freq, weight in weighted_candidates:
            cumulative += weight
            if rand <= cumulative:
                return freq.title
        return weighted_candidates[-1][0].title
