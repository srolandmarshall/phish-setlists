"""Resolve and cache rare and mandatory segue continuations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from random import Random
from typing import Dict, List, Set, Tuple

from sqlalchemy.orm import Session

from .catalog import SongCatalog, determine_origin_from_entry, normalize_title
from .models import SongDisplay
from .playlist_queries import _load_track_song_metadata
from .tracks import CandidateTrack, query_tracks_for_song, resolve_track_metadata

logger = logging.getLogger("uvicorn.error")


@dataclass
class SegueInjection:
    """Request-scoped state shared by rare and mandatory segue injection."""

    db_session: Session
    catalog: SongCatalog
    rng: Random
    feature_store: object
    track_cache: Dict[str, SongDisplay | None] = field(default_factory=dict)
    injected_track_ids: Set[int] = field(default_factory=set)
    mandatory_injected_songs: Set[Tuple[str, str]] = field(default_factory=set)
    continuation_records: Dict[int, object] = field(default_factory=dict)
    continuation_lookup_ids: Set[int] = field(default_factory=set)
    attempted_continuation_ids: Set[int] = field(default_factory=set)
    notes: List[str] = field(default_factory=list)

    def load_track_records(self, track_ids: List[int]) -> None:
        missing = [
            track_id
            for track_id in dict.fromkeys(track_ids)
            if track_id not in self.continuation_lookup_ids
        ]
        self.continuation_records.update(_load_track_song_metadata(self.db_session, missing))
        self.continuation_lookup_ids.update(missing)

    def inject_rare(self, source: SongDisplay) -> None:
        """Resolve every distinct rare continuation referenced by a source track."""
        track_ids = source.rare_segue_next_tracks or []
        if not track_ids or not self.feature_store:
            return
        self.load_track_records(track_ids)

        for track_id in track_ids:
            if track_id in self.injected_track_ids:
                continue
            self.injected_track_ids.add(track_id)
            metadata = self.continuation_records.get(track_id)
            if metadata is None or metadata.song_id is None:
                continue

            candidate = self._candidate(track_id, metadata)
            self.attempted_continuation_ids.add(track_id)
            mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                self.db_session,
                candidate,
                song_slug=metadata.song_slug,
                rng=self.rng,
                strict=False,
            )
            if not mp3_url:
                continue

            duration = self._duration(candidate.duration, remote_duration)
            show_date = remote_show_date or "unknown date"
            note = f"🎰 Lottery ticket! Rare {source.title} → {metadata.song_title} from {show_date}"
            if note not in self.notes:
                self.notes.append(note)
            self.track_cache[normalize_title(metadata.song_title)] = SongDisplay(
                title=metadata.song_title,
                mp3_url=mp3_url,
                duration_seconds=duration,
                origin=None,
                show_date=show_date,
                track_id=track_id,
                is_segue=True,
                segue_type="lottery_ticket",
                segue_pattern=f"{source.title} -> {metadata.song_title}",
                segue_position=2,
                segue_group_id=source.segue_group_id,
                historical_occurrences=source.historical_occurrences,
                rarity_score=source.rarity_score,
                likes_count=candidate.likes_count,
            )

    def inject_mandatory(self, source: SongDisplay, song_title: str, segment_label: str) -> None:
        """Resolve mandatory continuations and cache their response displays."""
        patterns = source.mandatory_pattern_songs or []
        if not patterns:
            return
        self.load_track_records(source.mandatory_next_tracks or [])

        for index, pattern_song in enumerate(patterns):
            self.mandatory_injected_songs.add((segment_label, pattern_song))
            track_id = self._mandatory_track_id(source, index, pattern_song)
            if track_id is None or track_id in self.injected_track_ids:
                continue
            self.injected_track_ids.add(track_id)
            metadata = self.continuation_records.get(track_id)
            if metadata is None:
                self.load_track_records([track_id])
                metadata = self.continuation_records.get(track_id)
            if metadata is None or metadata.song_id is None:
                continue

            candidate = self._candidate(track_id, metadata)
            self.attempted_continuation_ids.add(track_id)
            mp3_url, remote_duration, remote_show_date = resolve_track_metadata(
                self.db_session,
                candidate,
                song_slug=metadata.song_slug,
                rng=self.rng,
                strict=False,
            )
            if not mp3_url:
                continue

            duration = self._duration(candidate.duration, remote_duration)
            show_date = remote_show_date or "unknown"
            entry = self.catalog.by_title.get(normalize_title(metadata.song_title))
            self.track_cache[normalize_title(metadata.song_title)] = SongDisplay(
                title=metadata.song_title,
                mp3_url=mp3_url,
                duration_seconds=duration,
                origin=determine_origin_from_entry(entry) if entry else None,
                show_date=show_date,
                track_id=track_id,
                is_segue=True,
                segue_type="mandatory",
                segue_pattern=f"{song_title} -> {' -> '.join(patterns)}",
                segue_position=index + 2,
            )

    def _mandatory_track_id(
        self, source: SongDisplay, index: int, pattern_song: str
    ) -> int | None:
        if source.mandatory_next_tracks and index < len(source.mandatory_next_tracks):
            return source.mandatory_next_tracks[index]

        entry = self.catalog.by_title.get(normalize_title(pattern_song))
        if not entry:
            logger.warning("Could not find catalog entry for mandatory pattern song: %s", pattern_song)
            return None
        candidates = query_tracks_for_song(self.db_session, entry.slug)
        if not candidates:
            logger.warning("No tracks found for mandatory pattern song: %s", pattern_song)
            return None
        return self.rng.choice(candidates).track_id

    @staticmethod
    def _candidate(track_id: int, metadata: object) -> CandidateTrack:
        return CandidateTrack(
            track_id=track_id,
            slug=metadata.track_slug,
            duration=metadata.duration,
            show_date=None,
            likes_count=metadata.likes_count or 0,
            metadata_cache=metadata.metadata_cache,
        )

    @staticmethod
    def _duration(database_duration: int | None, remote_duration: int | None) -> int | None:
        duration = database_duration if database_duration else remote_duration
        return duration // 1000 if duration and duration > 6000 else duration
