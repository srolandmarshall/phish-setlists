"""Baseline setlist generator using historical frequency heuristics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import logging
from pathlib import Path
from random import Random
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..analysis.feature_store import FeatureStore
from ..constants import (
    DEFAULT_SET_DURATION_TARGETS,
    DEFAULT_SET_LENGTHS,
    ERA_DEFINITIONS,
    THREE_SET_DURATION_OVERRIDES,
)
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

    _duration_safety_factor: float = 1.05
    _duration_margin_ratio: float = 0.25
    _duration_margin_cap: int = 8 * 60

    def __init__(
        self,
        session: Session,
        rng: Optional[Random] = None,
        *,
        adjacency_bonus: float = 0.05,
        adjacency_min_support: int = 2,
        use_ml_features: bool = False,
        ml_placement_weight: float = 0.3,
        ml_transition_bonus: float = 0.1,
        features_dir: Optional[Path] = None,
        jamminess: Optional[float] = None,
        same_show_segues: bool = False,
    ):
        self.session = session
        self.rng = rng or Random()
        self._adjacency_bonus = max(0.0, adjacency_bonus)
        self._adjacency_min_support = max(0, adjacency_min_support)
        self._use_ml_features = use_ml_features
        self._ml_placement_weight = ml_placement_weight
        self._ml_transition_bonus = ml_transition_bonus
        # Jamminess: 0.0 = tight/concise, 0.5 = balanced, 1.0 = maximum jams
        # None = use dynamic intensity based on remaining budget
        self._jamminess = max(0.0, min(1.0, jamminess)) if jamminess is not None else None
        self._same_show_segues = same_show_segues

        self._feature_store: Optional[FeatureStore] = None
        if use_ml_features:
            if features_dir is None:
                # Default to data/analytics/features relative to project root
                features_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "analytics" / "features"
            if not features_dir.exists():
                raise RuntimeError(f"ML features directory not found: {features_dir}")
            self._feature_store = FeatureStore(features_dir)
            self._feature_store.load()
        
        # Load excluded songs (always loaded, not just for ML)
        self._excluded_songs: Set[str] = self._load_excluded_songs()
        
        # Era context for generation (set during generate() call)
        self._current_era: Optional[str] = None
        self._segment_segue_counts: Dict[str, int] = {}

    def _load_excluded_songs(self) -> Set[str]:
        """Load list of songs to exclude from generation (situational, meta, technical)."""
        excluded = set()
        
        # Try to load from CSV file
        excluded_file = Path(__file__).resolve().parent.parent.parent.parent / "data" / "analytics" / "excluded_songs.csv"
        
        if excluded_file.exists():
            try:
                import csv
                with open(excluded_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        excluded.add(row['song_title'])
            except Exception:
                pass  # Silently continue if file can't be read
        
        # Add hardcoded fallback exclusions (in case CSV missing)
        excluded.update([
            "Banter",
            "Interview",  # Spoken content, equivalent to banter
            "Audience Chess Move",
            "Happy Birthday to You",
            "Soundcheck",
            "Tuning",
            "Intro",
            "Intro (Friday the 13th Theme)",
            "Outro",
            "Jam",  # Generic jam, not Big Ball Jam
            "Narration",
        ])
        
        return excluded

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
        max_segues_per_set: Optional[int] = None,
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
            max_segues_per_set: Maximum number of mandatory segue patterns allowed per
                segment. When ``None``, no additional cap is enforced at the generator
                level (service layer defaults still apply).
        """

        if num_sets not in (2, 3):
            raise ValueError("num_sets must be 2 or 3")

        if era and era not in ERA_DEFINITIONS:
            raise ValueError(f"Unsupported era '{era}'. Known eras: {', '.join(ERA_DEFINITIONS)}")

        # Store era context for era-aware song filtering
        self._current_era = era

        reference = reference_date or self._latest_show_date()
        cutoff = reference
        if year and cutoff.year > year:
            cutoff = date(year, 12, 31)

        lengths = {**DEFAULT_SET_LENGTHS, **(set_lengths or {})}
        # Reset per-segment segue counters for this generation run
        self._segment_segue_counts = {}

        # Adjust song counts based on jamminess level
        # High jamminess (extended jams) → fewer songs needed to fill duration
        # Low jamminess uses default counts (duration capping handles it naturally)
        if self._jamminess is not None and self._jamminess >= 0.75:
            # High jamminess: fewer songs, longer jams
            lengths["set1"] = max(8, lengths.get("set1", 10) - 1)
            lengths["set2"] = max(9, lengths.get("set2", 11) - 1)
            lengths["set3"] = max(5, lengths.get("set3", 6) - 1)

        duration_targets = self._resolve_duration_targets(
            num_sets=num_sets,
            include_encore=include_encore,
        )

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

        # Era filtering diagnostics - warn if pool is too restricted
        eligible_count = len(seen_songs)
        if eligible_count < 50:
            logger.warning(
                f"Era filtering resulted in only {eligible_count} eligible songs "
                f"(era={era}, year={year}). This may cause incomplete sets."
            )
        elif eligible_count < 100:
            logger.info(
                f"Era filtering resulted in {eligible_count} eligible songs "
                f"(era={era}, year={year}). Set variety may be limited."
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

        # Add note if era filtering significantly restricts the pool
        if eligible_count < 50:
            metadata_notes.append(
                f"Limited to {eligible_count} eligible songs due to era/year filtering. "
                "Sets may be shorter than typical."
            )

        sets: List[SetSegment] = []
        completed_sets_songs: Dict[str, List[str]] = {}  # Track songs in completed sets for cross-set dependencies
        
        for idx in range(1, num_sets + 1):
            canonical_set = f"set{idx}"
            set_label = f"Set {idx}"
            desired = lengths.get(canonical_set, 8)

            set_stats = segment_stats_map.get(canonical_set)
            set_longform = segment_longform_titles.get(canonical_set, set())

            adjacency_map = set_stats.adjacency_map if set_stats else None

            self._segment_segue_counts[set_label] = 0
            set_songs, set_notes = self._compose_segment(
                canonical_set=canonical_set,
                segment_label=set_label,
                desired_count=desired,
                frequencies_by_set=frequencies_by_set,
                stats=set_stats,
                used_songs=used_songs,
                eligible_songs=seen_songs,
                allow_sequences=False,
                allow_single_song=False,
                longform_titles=set_longform,
                adjacency_map=adjacency_map,
                duration_target=duration_targets.get(canonical_set),
                previous_sets_songs=completed_sets_songs,  # Pass previous sets for cross-set dependencies
                max_segues_per_set=max_segues_per_set,
            )
            metadata_notes.extend(set_notes)
            sets.append(SetSegment(label=set_label, songs=set_songs))
            completed_sets_songs[canonical_set] = set_songs  # Track this set's songs

        encore_segment: Optional[SetSegment] = None
        if include_encore:
            desired_encore = lengths.get("encore", DEFAULT_SET_LENGTHS["encore"])
            encore_stats = segment_stats_map.get("encore")
            encore_longform = segment_longform_titles.get("encore", set())
            encore_adjacency = encore_stats.adjacency_map if encore_stats else None

            self._segment_segue_counts["Encore"] = 0
            encore_songs, encore_notes = self._compose_segment(
                canonical_set="encore",
                segment_label="Encore",
                desired_count=desired_encore,
                frequencies_by_set=frequencies_by_set,
                stats=encore_stats,
                used_songs=used_songs,
                eligible_songs=seen_songs,
                allow_sequences=False,
                allow_single_song=True,
                longform_titles=encore_longform,
                adjacency_map=encore_adjacency,
                duration_target=duration_targets.get("encore"),
                previous_sets_songs=completed_sets_songs,  # Pass all previous sets for cross-set dependencies
                max_segues_per_set=max_segues_per_set,
            )
            metadata_notes.extend(encore_notes)
            encore_segment = SetSegment(label="Encore", songs=encore_songs)

        # Only use old rules-based segue handling when ML features are disabled
        # When ML features are enabled, segues are handled in generation.py with feature store
        if not self._use_ml_features:
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

    def _resolve_duration_targets(
        self,
        *,
        num_sets: int,
        include_encore: bool,
    ) -> Dict[str, Tuple[int, int]]:
        targets: Dict[str, Tuple[int, int]] = dict(DEFAULT_SET_DURATION_TARGETS)
        if num_sets == 3:
            targets.update(THREE_SET_DURATION_OVERRIDES)
        if not include_encore:
            targets.pop("encore", None)
        return targets

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
        duration_target: Optional[Tuple[int, int]],
        previous_sets_songs: Optional[Dict[str, List[str]]] = None,
        max_segues_per_set: Optional[int] = None,
    ) -> Tuple[List[str], List[str]]:
        notes: List[str] = []
        songs: List[str] = []
        self._segment_segue_counts.setdefault(segment_label, 0)

        duration_capped = False
        song_stats = stats.song_durations if stats else {}
        estimated_duration = 0.0

        if allow_sequences and stats is not None and desired_count > 0:
            remaining = max(0, desired_count - len(songs))
        else:
            remaining = desired_count

        if remaining > 0:
            previous_song = songs[-1] if songs else None
            additional, capped, estimated_duration = self._select_with_duration_budget(
                base_songs=tuple(songs),
                desired_count=remaining,
                frequencies_by_set=frequencies_by_set,
                target_set=canonical_set,
                segment_label=segment_label,
                used_songs=used_songs,
                eligible_songs=eligible_songs,
                previous_song=previous_song,
                adjacency_map=adjacency_map,
                stats=stats,
                duration_target=duration_target,
                previous_sets_songs=previous_sets_songs,
                max_segues_per_set=max_segues_per_set,
            )
            if additional:
                songs.extend(additional)
            duration_capped = duration_capped or capped

        if (
            not allow_single_song
            and desired_count > 1
            and len(songs) == 1
            and songs[0] not in longform_titles
        ):
            previous_song = songs[-1] if songs else None
            extra, capped, estimated_duration = self._select_with_duration_budget(
                base_songs=tuple(songs),
                desired_count=1,
                frequencies_by_set=frequencies_by_set,
                target_set=canonical_set,
                segment_label=segment_label,
                used_songs=used_songs,
                eligible_songs=eligible_songs,
                previous_song=previous_song,
                adjacency_map=adjacency_map,
                stats=stats,
                duration_target=duration_target,
                previous_sets_songs=previous_sets_songs,
                max_segues_per_set=max_segues_per_set,
            )
            if extra:
                songs.extend(extra)
            duration_capped = duration_capped or capped

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

        # NEW: Try to replace last song with a set-ending song (for Set 1 and Set 2)
        if (
            self._use_ml_features
            and self._feature_store
            and canonical_set in ["set1", "set2"]
            and len(songs) > 0
        ):
            set_ender = self._select_set_ender(
                canonical_set=canonical_set,
                eligible_songs=eligible_songs,
                used_songs=used_songs,
            )
            if set_ender and set_ender not in songs:
                # Replace last song with set ender
                last_song = songs[-1]
                songs[-1] = set_ender
                used_songs.discard(last_song)
                used_songs.add(set_ender)
                notes.append(
                    f"Selected {set_ender} as {segment_label} closer (weighted by historical ending probability)"
                )

        estimated_duration = self._estimate_segment_duration(
            songs,
            song_stats,
            duration_target,
        )

        if not songs:
            notes.append(f"No songs selected for {segment_label}; limited historical data.")
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
        if songs:
            if len(songs) < desired_count:
                if duration_capped and duration_target:
                    notes.append(
                        f"Capped {segment_label} at {len(songs)} songs (~{self._format_duration(estimated_duration)})"
                        " to respect duration target."
                    )
                else:
                    notes.append(
                        f"Only selected {len(songs)}/{desired_count} songs for {segment_label}; limited historical data."
                    )
            elif duration_capped and duration_target:
                notes.append(
                    f"Capped {segment_label} at {len(songs)} songs (~{self._format_duration(estimated_duration)})"
                    " to respect duration target."
                )

        return songs, notes

    def _select_duration_map_by_intensity(
        self,
        stats: Optional[SegmentStatistics],
        current_duration: float,
        duration_target: Optional[Tuple[int, int]],
    ) -> Dict[str, float]:
        """Select appropriate duration percentile based on jam intensity.

        If user specified jamminess, use that as override.
        Otherwise, use dynamic selection based on remaining budget.

        Jamminess scale:
        - 0.0-0.25: Tight/concise (30th percentile)
        - 0.25-0.5: Balanced (50th percentile)
        - 0.5-0.75: Jammy (70th percentile)
        - 0.75-1.0: Maximum jam (90th percentile)
        """
        if not stats:
            return {}

        # User-specified jamminess overrides dynamic selection
        if self._jamminess is not None:
            if self._jamminess < 0.25:
                return stats.song_durations_p30  # Tight/concise
            elif self._jamminess < 0.5:
                return stats.song_durations_p50  # Balanced
            elif self._jamminess < 0.75:
                return stats.song_durations_p70  # Jammy
            else:
                return stats.song_durations_p90  # Maximum jam

        # Dynamic selection based on remaining budget (original behavior)
        if not duration_target:
            return stats.song_durations_p50  # Safe default

        lower, upper = duration_target
        target_mid = (lower + upper) / 2

        # Calculate how full the set is (0.0 = empty, 1.0 = full)
        # This is the INVERSE of remaining budget - when set is empty, we need to be conservative
        filled_ratio = current_duration / target_mid if target_mid > 0 else 0.0

        # Be conservative early (leave room), can be jammier later
        # Early in set (0-40% full): Use tight/median versions to leave room
        # Middle (40-70% full): Use median/above-average
        # Late (70%+ full): Committed to the duration, adjust as needed
        if filled_ratio < 0.4:
            # Early in set - be conservative, use median or lower
            return stats.song_durations_p50  # Median/average
        elif filled_ratio < 0.7:
            # Middle of set - can use above-average
            return stats.song_durations_p70  # Above-average jams
        else:
            # Late in set - adjust based on how close we are to target
            remaining = max(0, target_mid - current_duration)
            if remaining > 600:  # More than 10 minutes left
                return stats.song_durations_p70  # Can still fit above-average
            elif remaining > 300:  # 5-10 minutes left
                return stats.song_durations_p50  # Median
            else:
                return stats.song_durations_p30  # Need tight versions

    def _select_with_duration_budget(
        self,
        *,
        base_songs: Sequence[str],
        desired_count: int,
        frequencies_by_set: Dict[str, List[SongFrequency]],
        target_set: str,
        segment_label: str,
        used_songs: Set[str],
        eligible_songs: Iterable[str],
        previous_song: Optional[str],
        adjacency_map: Optional[Dict[str, Dict[str, int]]],
        stats: Optional[SegmentStatistics],
        duration_target: Optional[Tuple[int, int]],
        previous_sets_songs: Optional[Dict[str, List[str]]] = None,
        max_segues_per_set: Optional[int] = None,
    ) -> Tuple[List[str], bool, float]:
        # Use 80th percentile for fallback calculations (backward compat)
        song_durations = stats.song_durations if stats else {}
        safety_factor = self._duration_safety_factor if duration_target else 1.0

        if desired_count <= 0:
            current = self._estimate_segment_duration(
                base_songs,
                song_durations,
                duration_target,
                multiplier=safety_factor,
            )
            return [], False, current

        pool = self._build_candidate_pool(frequencies_by_set, target_set, eligible_songs)
        fallback_duration = self._fallback_duration(
            song_durations,
            max(desired_count, 1),
            duration_target,
        )
        current_duration = self._estimate_segment_duration(
            base_songs,
            song_durations,
            duration_target,
            fallback_duration,
            multiplier=safety_factor,
        )

        max_duration: Optional[float] = None
        if duration_target:
            lower, upper = duration_target
            window = max(upper - lower, 0)

            # Relax duration constraints based on jamminess level
            if self._jamminess is not None and self._jamminess >= 0.9:
                # At very high jamminess (0.9+), be VERY permissive - add 50% to upper bound
                # User explicitly wants extended jams, duration targets are soft suggestions
                adjusted_upper = upper * 1.5
            elif self._jamminess is not None and self._jamminess >= 0.75:
                # At high jamminess (0.75-0.9), be more permissive - add 25% to upper bound
                adjusted_upper = upper * 1.25
            else:
                # Default behavior - use upper bound as target (safety_factor provides conservatism)
                # The safety_factor (1.05) already builds in headroom for estimation error
                adjusted_upper = upper

            max_duration = float(adjusted_upper)

        base_song_count = len(base_songs)
        duration_capped = False
        selection: List[str] = []
        prev = previous_song

        while len(selection) < desired_count:
            pool = [freq for freq in pool if freq.title not in used_songs]
            
            # PHASE 4.1A: Filter segue-only songs from pool BEFORE picking
            # These songs should NEVER appear alone (e.g., Weekapaug, Hydrogen)
            if self._use_ml_features and self._feature_store:
                filtered_pool = []
                for freq in pool:
                    is_segue_only = False
                    mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)
                    for segue in mandatory_segues:
                        songs = segue.get('songs', [])
                        if len(songs) > 1 and freq.title in songs and songs[0] != freq.title:
                            # This song appears mid/end of a segue pattern - it's segue-only
                            is_segue_only = True
                            break
                    
                    if not is_segue_only:
                        filtered_pool.append(freq)
                
                pool = filtered_pool if filtered_pool else pool
            
            if not pool:
                break

            choice = self._weighted_pick(
                pool,
                used_songs,
                previous_song=prev,
                adjacency_map=adjacency_map,
                target_set=target_set,
            )
            if not choice:
                break
            
            # PHASE 4.1B: Check if choice starts a mandatory segue pattern
            # If so, add ALL songs in the segue as a group (not just next song)
            if self._use_ml_features and self._feature_store:
                mandatory_segues = self._feature_store.get_mandatory_segues(choice)
                if mandatory_segues:
                    # This song starts (or continues) a mandatory segue
                    # Find the complete pattern and add all songs
                    segue_pattern = self._find_complete_segue_pattern(choice, mandatory_segues)
                    if segue_pattern and len(segue_pattern) > 1:
                        current_segues = self._segment_segue_counts.get(segment_label, 0)
                        if max_segues_per_set is not None and current_segues >= max_segues_per_set:
                            # Already hit the cap for this segment; skip additional patterns
                            pool = [freq for freq in pool if freq.title != choice]
                            continue
                        # Check if we have room for the full pattern
                        remaining_slots = desired_count - len(selection)
                        if len(segue_pattern) <= remaining_slots:
                            # Add entire segue pattern
                            for song_in_pattern in segue_pattern:
                                if song_in_pattern not in used_songs:
                                    selection.append(song_in_pattern)
                                    used_songs.add(song_in_pattern)
                            
                            # Update prev to last song in pattern
                            prev = segue_pattern[-1]
                            if max_segues_per_set is not None:
                                current_segues += 1
                                self._segment_segue_counts[segment_label] = current_segues
                            
                            # Continue to next iteration (skip normal single-song logic below)
                            continue
                        else:
                            # Not enough room for full pattern, skip this song entirely
                            pool = [freq for freq in pool if freq.title != choice]
                            continue

            # NEW: Check ordering constraints (Phase 2.2)
            if self._use_ml_features and self._feature_store:
                # Check if adding this song would violate ordering
                # (e.g., trying to add Mike's after Weekapaug already in set)
                all_songs_so_far = list(base_songs) + selection
                if self._feature_store.violates_ordering_constraint(all_songs_so_far, choice):
                    # Skip this song, try another
                    pool = [freq for freq in pool if freq.title != choice]
                    continue

                # NEW: Check cross-set dependencies (Phase 2.2b - Tweezer Reprise)
                # Example: Tweezer Reprise in encore requires Tweezer in earlier sets
                if previous_sets_songs:
                    if self._feature_store.violates_cross_set_dependency(
                        choice, target_set, previous_sets_songs
                    ):
                        # Skip this song, try another
                        pool = [freq for freq in pool if freq.title != choice]
                        continue

            # NEW: Dynamic jam intensity - select duration percentile based on remaining budget
            dynamic_durations = self._select_duration_map_by_intensity(
                stats, current_duration, duration_target
            )
            candidate_duration = dynamic_durations.get(choice, fallback_duration) * safety_factor
            estimated_total = current_duration + candidate_duration

            if (
                max_duration is not None
                and (base_song_count + len(selection)) >= 2
                and estimated_total > max_duration
            ):
                duration_capped = True
                pool = [freq for freq in pool if freq.title != choice]
                continue

            selection.append(choice)
            used_songs.add(choice)
            current_duration = estimated_total
            prev = choice
            
            # PHASE 4.2: Lottery ticket logic for rare segues
            # After adding a song, check if it has rare segues (low-frequency "lottery tickets")
            # If yes, roll the dice to see if we add the rare continuation
            if self._use_ml_features and self._feature_store:
                # Rare segues are indexed by track_id, but we need to query by song title
                # We'll need to get ALL rare segues for this song title across all performances
                # For now, skip lottery logic since we need track-level selection
                # TODO: Implement track-level selection to enable lottery tickets
                pass
            
            pool = [freq for freq in pool if freq.title not in used_songs]

        return selection, duration_capped, current_duration

    def _fallback_duration(
        self,
        song_durations: Dict[str, float],
        remaining_slots: int,
        duration_target: Optional[Tuple[int, int]],
    ) -> float:
        if song_durations:
            total = sum(song_durations.values())
            count = len(song_durations)
            if count > 0 and total > 0:
                return total / count

        if duration_target:
            lower, upper = duration_target
            count = max(remaining_slots, 1)
            per_slot_upper = upper / count
            return max(per_slot_upper, 60.0)

        return 600.0

    def _estimate_segment_duration(
        self,
        songs: Sequence[str],
        song_durations: Dict[str, float],
        duration_target: Optional[Tuple[int, int]],
        fallback_duration: Optional[float] = None,
        *,
        multiplier: float = 1.0,
    ) -> float:
        if not songs:
            return 0.0

        fallback = fallback_duration
        if fallback is None:
            fallback = self._fallback_duration(
                song_durations,
                len(songs),
                duration_target,
            )

        total = 0.0
        for song in songs:
            total += song_durations.get(song, fallback) * multiplier
        return total

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds <= 0:
            return "0:00"
        total_seconds = int(round(seconds))
        minutes, remainder = divmod(total_seconds, 60)
        return f"{minutes}:{remainder:02d}"

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

    def _build_candidate_pool(
        self,
        frequencies_by_set: Dict[str, List[SongFrequency]],
        target_set: str,
        eligible_songs: Iterable[str],
    ) -> List[SongFrequency]:
        eligible = set(eligible_songs)
        
        # Filter out excluded songs (situational, meta, technical)
        eligible = eligible - self._excluded_songs
        
        # Era-aware exclusions: "I Am the Walrus" only allowed in 4.0 era
        if self._current_era != "4.0" and "I Am the Walrus" in eligible:
            eligible.discard("I Am the Walrus")
        
        # PHASE 4: Filter out songs that MUST be part of mandatory segues
        # These songs should not appear unless their full segue pattern can be completed
        if self._feature_store:
            songs_in_mandatory_segues = set()
            for song in eligible:
                mandatory_segues = self._feature_store.get_mandatory_segues(song)
                if mandatory_segues:
                    # This song is part of mandatory segue(s)
                    # We'll allow selection but warn if pattern can't complete
                    songs_in_mandatory_segues.add(song)

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
        target_set: Optional[str] = None,
    ) -> Optional[str]:
        available = [freq for freq in pool if freq.title not in used_songs]
        if not available:
            return None

        weighted_candidates: List[Tuple[SongFrequency, float]] = [
            (freq, float(freq.weight)) for freq in available
        ]

        # PHASE 4: Mandatory segue enforcement moved to _select_with_duration_budget
        # We now add complete segue patterns as a group, not just enforce next song
        # Commenting out this enforcement since it's redundant with pattern completion:
        #
        # if previous_song and self._feature_store:
        #     mandatory_segues = self._feature_store.get_mandatory_segues(previous_song)
        #     if mandatory_segues:
        #         valid_next_songs = set()
        #         for segue in mandatory_segues:
        #             if previous_song in segue['songs']:
        #                 idx = segue['songs'].index(previous_song)
        #                 if idx + 1 < len(segue['songs']):
        #                     valid_next_songs.add(segue['songs'][idx + 1])
        #         if valid_next_songs:
        #             weighted_candidates = [
        #                 (freq, weight) for freq, weight in weighted_candidates
        #                 if freq.title in valid_next_songs
        #             ]
        #             if not weighted_candidates:
        #                 logger.warning(
        #                     "Mandatory segue pattern started but no continuation available: %s",
        #                     previous_song
        #                 )
        #                 return None

        # NEW: Filter out forbidden transitions (Phase 2.2)
        if self._use_ml_features and self._feature_store and previous_song:
            weighted_candidates = [
                (freq, weight)
                for freq, weight in weighted_candidates
                if not self._feature_store.is_forbidden_transition(previous_song, freq.title)
            ]
            
            # If we filtered everything, return None
            if not weighted_candidates:
                return None

        # NEW: Apply frequency caps to prevent overuse of both rare AND common songs
        if self._use_ml_features and self._feature_store:
            logger.info("🔍 BIAS FIX: Applying frequency caps (use_ml=%s, store=%s, candidates=%d)",
                       self._use_ml_features, self._feature_store is not None, len(weighted_candidates))
            # DEBUG: Show first few songs being checked
            if weighted_candidates:
                logger.info("🔍 BIAS FIX: Sample songs to check: %s", [freq.title for freq, _ in weighted_candidates[:5]])
            for idx, (freq, weight) in enumerate(weighted_candidates):
                features = self._feature_store.get_song_features(freq.title)
                if not features:
                    logger.warning("⚠️  BIAS FIX: No features found for song: %s (repr: %r)", freq.title, freq.title)
                if features:
                    # DEBUG: Log features for common segue songs
                    if freq.title in ["Mike's Song", "Runaway Jim", "Colonel Forbin's Ascent", "I Am Hydrogen"]:
                        logger.info("🔍 BIAS FIX: Found features for %s - appearances: %d", freq.title, features.total_appearances)

                    # Dampen very common songs to prevent over-representation
                    if features.total_appearances > 500:
                        # Very common: 30% weight (e.g., Mike's Song, YEM, Possum)
                        capped_weight = weight * 0.3
                        logger.info("⬇️  BIAS FIX: Reducing %s (>500 appearances): %.2f → %.2f", freq.title, weight, capped_weight)
                    elif features.total_appearances > 300:
                        # Common: 50% weight (e.g., Runaway Jim, I Am Hydrogen)
                        capped_weight = weight * 0.5
                        logger.info("⬇️  BIAS FIX: Reducing %s (>300 appearances): %.2f → %.2f", freq.title, weight, capped_weight)
                    # Scale down rare songs (historical count < 50)
                    elif features.total_appearances < 30:
                        # Very rare: 25% weight
                        capped_weight = weight * 0.25
                    elif features.total_appearances < 50:
                        # Rare: 50% weight
                        capped_weight = weight * 0.5
                    else:
                        # Normal frequency (30-500): no adjustment
                        capped_weight = weight
                    weighted_candidates[idx] = (freq, capped_weight)

        # NEW: Apply segue trigger penalty to account for pattern expansion
        # Songs with mandatory segues will add multiple songs to the set, so reduce their selection probability
        if self._use_ml_features and self._feature_store:
            for idx, (freq, weight) in enumerate(weighted_candidates):
                mandatory_segues = self._feature_store.get_mandatory_segues(freq.title)
                if mandatory_segues:
                    # Calculate average pattern length this song triggers
                    pattern_lengths = [len(seg.get('songs', [])) for seg in mandatory_segues]
                    avg_pattern_length = sum(pattern_lengths) / len(pattern_lengths) if pattern_lengths else 1

                    if avg_pattern_length > 1:
                        # Apply penalty proportional to how many songs will be added
                        # Example: 3-song pattern (Mike's > Hydrogen > Weekapaug) gets 0.33x penalty
                        penalty = 1.0 / avg_pattern_length
                        penalized_weight = weight * penalty
                        weighted_candidates[idx] = (freq, penalized_weight)
                        logger.debug(
                            "Applying segue penalty to %s (pattern length %.1f): %.2f → %.2f",
                            freq.title, avg_pattern_length, weight, penalized_weight
                        )

        # Apply ML placement probability adjustments
        if self._use_ml_features and self._feature_store and target_set:
            for idx, (freq, weight) in enumerate(weighted_candidates):
                placement_prob = self._feature_store.get_placement_probability(
                    freq.title, target_set
                )
                if placement_prob > 0:
                    # Blend historical weight with ML placement probability
                    ml_adjusted = weight * (1 - self._ml_placement_weight) + placement_prob * self._ml_placement_weight
                    weighted_candidates[idx] = (freq, ml_adjusted)

        # Apply historical adjacency bonus
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

        # Apply ML transition lift bonus
        if self._use_ml_features and self._feature_store and previous_song:
            for idx, (freq, weight) in enumerate(weighted_candidates):
                transition = self._feature_store.get_transition_lift(previous_song, freq.title)
                if transition and transition.lift > 2.0:  # Only boost strong transitions
                    # Normalize lift to reasonable range (2-10x -> 0-1)
                    normalized_lift = min((transition.lift - 2.0) / 8.0, 1.0)
                    boost = 1.0 + self._ml_transition_bonus * normalized_lift
                    weighted_candidates[idx] = (freq, weight * boost)

        # NEW: Apply STRONG boost for mandatory sequences (Phase 2.2)
        if self._use_ml_features and self._feature_store and previous_song:
            mandatory_next = self._feature_store.get_mandatory_next_songs(previous_song)
            if mandatory_next:
                for idx, (freq, weight) in enumerate(weighted_candidates):
                    if freq.title in mandatory_next:
                        # Much stronger boost than normal transitions (3× multiplier)
                        weighted_candidates[idx] = (freq, weight * 3.0)

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
    
    def _find_complete_segue_pattern(
        self,
        song: str,
        mandatory_segues: List[dict],
    ) -> Optional[List[str]]:
        """
        Given a song and its mandatory segues, find the complete pattern.
        
        For example, if song is "Mike's Song" and it's part of:
        ["Mike's Song", "I Am Hydrogen", "Weekapaug Groove"]
        
        Return the complete pattern starting from this song.
        """
        if not mandatory_segues:
            return None
        
        # Find the segue where this song appears
        for segue in mandatory_segues:
            songs_in_pattern = segue.get('songs', [])
            if song in songs_in_pattern:
                # Find position of this song in the pattern
                idx = songs_in_pattern.index(song)
                # Return from this song forward
                return songs_in_pattern[idx:]
        
        return None

    def _select_set_ender(
        self,
        *,
        canonical_set: str,
        eligible_songs: Iterable[str],
        used_songs: Set[str],
    ) -> Optional[str]:
        """
        Select a set-ending song weighted by historical ending probability.
        
        For Set 1 and Set 2, this picks songs that historically end sets,
        weighted by how often they appear as set closers.
        """
        if not self._feature_store:
            return None
        
        # Get all potential set enders for this set
        all_enders = self._feature_store.get_set_enders_for_set(canonical_set, min_probability=0.0)
        
        if not all_enders:
            return None
        
        eligible_set = set(eligible_songs)
        
        # Filter to eligible and unused songs
        candidates = [
            ender for ender in all_enders
            if ender.song_name in eligible_set
            and ender.song_name not in used_songs
            and ender.song_name not in self._excluded_songs
        ]
        
        if not candidates:
            return None
        
        # Weight by ending_probability * ending_count (favor both high probability AND frequency)
        weighted_candidates: List[Tuple[str, float]] = []
        for ender in candidates:
            # Use ending_probability as primary weight, scaled by count for tie-breaking
            weight = ender.ending_probability * (1.0 + (ender.ending_count / 100.0))
            weighted_candidates.append((ender.song_name, weight))
        
        total_weight = sum(w for _, w in weighted_candidates)
        if total_weight <= 0:
            return None
        
        # Weighted random selection
        rand = self.rng.random() * total_weight
        cumulative = 0.0
        for song, weight in weighted_candidates:
            cumulative += weight
            if rand <= cumulative:
                return song
        
        return weighted_candidates[-1][0]
