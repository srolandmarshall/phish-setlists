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
    EncoreStatistics,
    SongFrequency,
    encore_statistics,
    previous_show_tracks,
    song_frequencies_by_set,
    songs_seen_by_date,
)


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

    def __init__(self, session: Session, rng: Optional[Random] = None):
        self.session = session
        self.rng = rng or Random()

    def generate(
        self,
        *,
        reference_date: Optional[date] = None,
        num_sets: int = 2,
        include_encore: bool = True,
        set_lengths: Optional[Dict[str, int]] = None,
        era: Optional[str] = None,
        year: Optional[int] = None,
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

        previous_show_songs = set(previous_show_tracks(self.session, reference))
        seen_songs = songs_seen_by_date(self.session, cutoff)

        frequencies_by_set = song_frequencies_by_set(
            self.session,
            cutoff_date=cutoff,
            era=era,
            year=year,
        )

        encore_stats: Optional[EncoreStatistics] = None
        longform_titles: Set[str] = set()
        if include_encore:
            encore_stats = encore_statistics(
                self.session,
                cutoff_date=cutoff,
                era=era,
                year=year,
                top_n_sequences=50,
            )
            longform_titles = {title for title, _ in encore_stats.longform_songs}

        used_songs: Set[str] = set(previous_show_songs)
        metadata_notes: List[str] = []
        if previous_show_songs:
            metadata_notes.append(
                f"Excluded {len(previous_show_songs)} songs played on {self._previous_show_date(reference)}"
            )

        sets: List[SetSegment] = []
        for idx in range(1, num_sets + 1):
            canonical_set = f"set{idx}"
            set_label = f"Set {idx}"
            desired = lengths.get(canonical_set, 8)
            set_songs = self._pick_songs_for_set(
                frequencies_by_set, canonical_set, desired, used_songs, seen_songs
            )
            if len(set_songs) < desired:
                metadata_notes.append(
                    f"Only selected {len(set_songs)}/{desired} songs for {set_label};"
                    " limited historical data."
                )
            sets.append(SetSegment(label=set_label, songs=set_songs))

        encore_segment: Optional[SetSegment] = None
        if include_encore:
            encore_songs, encore_notes = self._pick_encore_songs(
                frequencies_by_set=frequencies_by_set,
                desired_override=lengths.get("encore"),
                used_songs=used_songs,
                eligible_songs=seen_songs,
                stats=encore_stats,
                longform_titles=longform_titles,
            )
            metadata_notes.extend(encore_notes)
            encore_segment = SetSegment(label="Encore", songs=encore_songs)

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

    def _previous_show_date(self, reference: date) -> Optional[date]:
        stmt = (
            select(Show.date)
            .where(Show.date < reference)
            .order_by(Show.date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def _pick_encore_songs(
        self,
        *,
        frequencies_by_set: Dict[str, List[SongFrequency]],
        desired_override: Optional[int],
        used_songs: Set[str],
        eligible_songs: Iterable[str],
        stats: Optional[EncoreStatistics],
        longform_titles: Set[str],
    ) -> Tuple[List[str], List[str]]:
        notes: List[str] = []

        if stats is None:
            desired = desired_override or DEFAULT_SET_LENGTHS["encore"]
        else:
            recommended = self._recommended_encore_length(stats)
            desired = desired_override if desired_override is not None else max(2, recommended)

        max_length = desired_override

        encore_songs: List[str] = []

        if stats is not None:
            sequence = self._choose_encore_sequence(
                stats=stats,
                used_songs=used_songs,
                eligible_songs=eligible_songs,
                desired_length=desired,
                max_length=max_length,
            )
            if sequence:
                encore_songs.extend(sequence)
                used_songs.update(sequence)

        remaining = max(0, desired - len(encore_songs))
        if remaining > 0:
            additional = self._pick_songs_for_set(
                frequencies_by_set,
                "encore",
                remaining,
                used_songs,
                eligible_songs,
            )
            encore_songs.extend(additional)

        if (
            len(encore_songs) == 1
            and (desired_override is None or desired_override > 1)
            and encore_songs[0] not in longform_titles
        ):
            extra = self._pick_songs_for_set(
                frequencies_by_set,
                "encore",
                1,
                used_songs,
                eligible_songs,
            )
            encore_songs.extend(extra)

        # Ensure uniqueness and order preservation after extensions.
        seen: Set[str] = set()
        deduped: List[str] = []
        for song in encore_songs:
            if song in seen:
                continue
            seen.add(song)
            deduped.append(song)
        encore_songs = deduped

        used_songs.update(encore_songs)

        if not encore_songs:
            notes.append("No encore songs available; limited historical data.")
        elif len(encore_songs) == 1:
            song = encore_songs[0]
            if song in longform_titles:
                notes.append(f"Encore anchored by long-form performance of {song}.")
            else:
                notes.append(
                    "Encore limited to a single song without long-form precedent;"
                    " additional data may unlock multi-song encores."
                )
        elif stats is not None and desired_override is None and len(encore_songs) < desired:
            notes.append(
                f"Encore truncated to {len(encore_songs)} songs (target {desired}); limited historical data."
            )

        return encore_songs, notes

    def _recommended_encore_length(self, stats: Optional[EncoreStatistics]) -> int:
        if not stats or not stats.count_histogram:
            return DEFAULT_SET_LENGTHS["encore"]

        sorted_counts = sorted(
            stats.count_histogram.items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        mode = sorted_counts[0][0]
        if mode == 1:
            multi = [item for item in sorted_counts if item[0] >= 2]
            if multi:
                return multi[0][0]
            return 1
        return min(max(mode, 2), 3)

    def _choose_encore_sequence(
        self,
        *,
        stats: EncoreStatistics,
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
    ) -> List[str]:
        pool = self._build_candidate_pool(frequencies_by_set, target_set, eligible_songs)
        selection: List[str] = []

        for _ in range(desired_count):
            choice = self._weighted_pick(pool, used_songs)
            if not choice:
                break
            selection.append(choice)
            used_songs.add(choice)
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

    def _weighted_pick(self, pool: List[SongFrequency], used_songs: Set[str]) -> Optional[str]:
        available = [freq for freq in pool if freq.title not in used_songs]
        if not available:
            return None

        total_weight = sum(freq.weight for freq in available)
        if total_weight <= 0:
            return None

        rand = self.rng.random() * total_weight
        cumulative = 0.0
        for freq in available:
            cumulative += freq.weight
            if rand <= cumulative:
                return freq.title
        return available[-1].title
