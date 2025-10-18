"""Special-case heuristics for refining generated setlists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, TYPE_CHECKING

from .historical import SegmentStatistics

if TYPE_CHECKING:
    from .core import SetSegment


@dataclass(frozen=True)
class SongDependencyRule:
    """Ensure prerequisite songs accompany specific appearances."""

    trigger: str
    requirements: Tuple[str, ...]
    insert_candidates: Tuple[str, ...]
    allow_insert_in_trigger_segment: bool = False
    insert_adjacent: bool = False

    def apply(self, context: "RuleContext") -> None:
        if not context.contains_song(self.trigger):
            return

        missing = [req for req in self.requirements if not context.contains_song(req)]
        if not missing:
            return

        trigger_segments = context.segments_with_song(self.trigger)

        for required in missing:
            if required not in context.eligible_songs:
                context.metadata_notes.append(
                    f"Could not add {required} required by {self.trigger}; unavailable in eligible pool."
                )
                continue

            inserted = False

            if self.allow_insert_in_trigger_segment:
                for segment in trigger_segments:
                    if context.canonical_label(segment) == "encore":
                        continue
                    if self.insert_adjacent:
                        if context.insert_after(segment, self.trigger, required):
                            context.metadata_notes.append(
                                f"Inserted {required} after {self.trigger} in {segment.label}."
                            )
                            context.remove_shortfall_note(segment.label)
                            inserted = True
                            break
                    if not inserted and context.add_song_to_segment(segment, required):
                        context.metadata_notes.append(
                            f"Inserted {required} into {segment.label} to support {self.trigger}."
                        )
                        context.remove_shortfall_note(segment.label)
                        inserted = True
                        break

            if inserted:
                continue

            for canonical in self.insert_candidates:
                segment = context.find_segment(canonical)
                if segment and context.canonical_label(segment) != "encore" and context.add_song_to_segment(segment, required):
                    context.metadata_notes.append(
                        f"Inserted {required} into {segment.label} to support {self.trigger}."
                    )
                    context.remove_shortfall_note(segment.label)
                    inserted = True
                    break

            if not inserted:
                context.metadata_notes.append(
                    f"{self.trigger} appears without {required}; no suitable segment available for insertion."
                )


@dataclass
class RuleContext:
    """Mutable context passed to rule implementations."""

    sets: List["SetSegment"]
    encore: Optional["SetSegment"]
    stats_by_segment: Dict[str, Optional[SegmentStatistics]]
    eligible_songs: Set[str]
    used_songs: Set[str]
    metadata_notes: List[str]

    def all_segments(self) -> List["SetSegment"]:
        segments: List["SetSegment"] = list(self.sets)
        if self.encore:
            segments.append(self.encore)
        return segments

    def canonical_label(self, segment: "SetSegment") -> str:
        label = segment.label.strip().lower()
        if "encore" in label:
            return "encore"
        if label.startswith("set"):
            digits = "".join(ch for ch in label if ch.isdigit())
            if digits:
                return f"set{digits}"
        return label

    def contains_song(self, title: str) -> bool:
        return any(title in segment.songs for segment in self.all_segments())

    def segments_with_song(self, title: str) -> List["SetSegment"]:
        return [segment for segment in self.all_segments() if title in segment.songs]

    def find_segment(self, canonical_label: str) -> Optional["SetSegment"]:
        canonical_label = canonical_label.lower()
        for segment in self.all_segments():
            if self.canonical_label(segment) == canonical_label:
                return segment
        return None

    def add_song_to_segment(self, segment: "SetSegment", song: str) -> bool:
        if song in self.used_songs:
            return False
        segment.songs.append(song)
        self.used_songs.add(song)
        return True

    def insert_after(self, segment: "SetSegment", anchor: str, song: str) -> bool:
        if song in self.used_songs:
            return False
        try:
            idx = segment.songs.index(anchor)
        except ValueError:
            return False
        segment.songs.insert(idx + 1, song)
        self.used_songs.add(song)
        return True

    def remove_shortfall_note(self, segment_label: str) -> None:
        suffix = f" songs for {segment_label}; limited historical data."
        self.metadata_notes[:] = [
            note for note in self.metadata_notes if suffix not in note
        ]


SONG_DEPENDENCY_RULES: Sequence[SongDependencyRule] = (
    SongDependencyRule(
        trigger="Tweezer Reprise",
        requirements=("Tweezer",),
        insert_candidates=("set2", "set1"),
        allow_insert_in_trigger_segment=False,
    ),
    SongDependencyRule(
        trigger="Mike's Song",
        requirements=("Weekapaug Groove",),
        insert_candidates=("set2", "set1"),
        allow_insert_in_trigger_segment=True,
        insert_adjacent=True,
    ),
)


def apply_rules(
    *,
    sets: List["SetSegment"],
    encore: Optional["SetSegment"],
    stats_by_segment: Dict[str, Optional[SegmentStatistics]],
    eligible_songs: Iterable[str],
    used_songs: Set[str],
    metadata_notes: List[str],
) -> None:
    """Apply all special-case rules to the generated setlist in place."""

    context = RuleContext(
        sets=sets,
        encore=encore,
        stats_by_segment=stats_by_segment,
        eligible_songs=set(eligible_songs),
        used_songs=used_songs,
        metadata_notes=metadata_notes,
    )

    for rule in SONG_DEPENDENCY_RULES:
        rule.apply(context)
