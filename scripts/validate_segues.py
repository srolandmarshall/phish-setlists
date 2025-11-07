#!/usr/bin/env python3
"""Validate segue groups are working correctly by generating setlists and analyzing patterns."""

import sys
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from phish_setlist_maker.config import get_database_settings
from phish_setlist_maker.service import generate_show

# Famous segue songs that should almost never appear alone
FAMOUS_SEGUE_PATTERNS = {
    "Mike's Song": ["I Am Hydrogen", "Weekapaug Groove"],
    "I Am Hydrogen": ["Mike's Song", "Weekapaug Groove"],
    "Weekapaug Groove": ["Mike's Song", "I Am Hydrogen"],
    "The Horse": ["Silent in the Morning"],
    "Silent in the Morning": ["The Horse"],
}


def get_all_songs(result):
    """Extract all songs from generation result with their origins."""
    songs = []
    for segment in result.segments:
        for track in segment.tracks:
            songs.append((track.title, track.origin or "unknown"))
    if result.encore:
        for track in result.encore.tracks:
            songs.append((track.title, track.origin or "unknown"))
    return songs


def check_violations(songs):
    """Check for segue violations (famous segue songs appearing without partners)."""
    violations = []
    song_titles = [s[0] for s in songs]

    for i, (song, origin) in enumerate(songs):
        if song not in FAMOUS_SEGUE_PATTERNS:
            continue

        expected = FAMOUS_SEGUE_PATTERNS[song]
        has_partner = False

        if i > 0 and song_titles[i - 1] in expected:
            has_partner = True
        if i < len(song_titles) - 1 and song_titles[i + 1] in expected:
            has_partner = True

        if not has_partner:
            violations.append(
                {
                    "song": song,
                    "origin": origin,
                    "position": i + 1,
                    "context": song_titles[
                        max(0, i - 2) : min(len(song_titles), i + 3)
                    ],
                }
            )

    return violations


def check_completions(songs):
    """Check for completed segues."""
    completions = []
    song_titles = [s[0] for s in songs]

    for i in range(len(song_titles) - 1):
        if song_titles[i] == "Mike's Song" and song_titles[i + 1] == "I Am Hydrogen":
            if i + 2 < len(song_titles) and song_titles[i + 2] == "Weekapaug Groove":
                completions.append(
                    {
                        "pattern": "Mike's -> Hydrogen -> Weekapaug",
                        "origins": [songs[i][1], songs[i + 1][1], songs[i + 2][1]],
                    }
                )
            else:
                completions.append(
                    {
                        "pattern": "Mike's -> Hydrogen (incomplete)",
                        "origins": [songs[i][1], songs[i + 1][1]],
                    }
                )
        elif (
            song_titles[i] == "The Horse"
            and song_titles[i + 1] == "Silent in the Morning"
        ):
            completions.append(
                {
                    "pattern": "Horse -> Silent",
                    "origins": [songs[i][1], songs[i + 1][1]],
                }
            )

    return completions


def main():
    print("=" * 80)
    print("SEGUE VALIDATION TEST")
    print("=" * 80)

    db_settings = get_database_settings()
    engine = create_engine(db_settings.url(hide_password=False))
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    NUM = 200
    print(f"\nGenerating {NUM} setlists with use_ml_features=True...\n")

    all_violations = []
    all_completions = []
    counts = Counter()

    for i in range(NUM):
        try:
            from phish_setlist_maker.service.generation import GenerationRequest

            request = GenerationRequest(
                reference_date=date(2024, 12, 31),
                num_sets=2,
                include_encore=True,
                use_ml_features=True,
                include_playlist=False,
                prefetch_track_metadata=False,  # Don't hit phish.in API
            )

            result = generate_show(session, request)

            songs = get_all_songs(result)
            violations = check_violations(songs)
            all_violations.extend(violations)

            completions = check_completions(songs)
            all_completions.extend(completions)

            for song, _ in songs:
                if song in FAMOUS_SEGUE_PATTERNS:
                    counts[song] += 1

            if (i + 1) % 10 == 0:
                print(f"  Generated {i+1}/{NUM}...")

        except Exception as e:
            print(f"  Error {i+1}: {e}")

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80 + "\n")

    print("📊 SEGUE SONG APPEARANCES:")
    print("-" * 80)
    for song, count in counts.most_common():
        print(f"  {song:30s} : {count:3d} times")
    print()

    print("❌ VIOLATIONS (segue songs appearing alone):")
    print("-" * 80)
    if all_violations:
        by_song = defaultdict(list)
        for v in all_violations:
            by_song[v["song"]].append(v)

        for song, vios in sorted(
            by_song.items(), key=lambda x: len(x[1]), reverse=True
        ):
            print(f"  {song}: {len(vios)} violations")
            for v in vios[:2]:
                print(f"    Origin: {v['origin']}")
                print(f"    Context: {' | '.join(v['context'])}")

        print(f"\n  TOTAL VIOLATIONS: {len(all_violations)}")
        if sum(counts.values()) > 0:
            rate = len(all_violations) / sum(counts.values()) * 100
            print(f"  VIOLATION RATE: {rate:.1f}%")
        print(f"\n  ⚠️  SEGUE LOGIC NOT WORKING - songs appearing without partners")
    else:
        print("  ✅ NO VIOLATIONS!")
    print()

    print("✅ COMPLETED SEGUES:")
    print("-" * 80)
    if all_completions:
        by_pattern = defaultdict(list)
        for c in all_completions:
            by_pattern[c["pattern"]].append(c)

        for pattern, comps in sorted(by_pattern.items()):
            print(f"  {pattern}: {len(comps)} times")
            # Check if origins match
            same_show = sum(1 for c in comps if len(set(c["origins"])) == 1)
            if same_show < len(comps):
                print(f"    ⚠️  {len(comps) - same_show} from different shows")
    else:
        print("  No completed segues found")
    print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if all_violations:
        print(
            f"⚠️  Found {len(all_violations)} violations - generator NOT using segue data"
        )
    else:
        print(f"✅ No violations - segue logic working!")
    print()

    session.close()


if __name__ == "__main__":
    main()
