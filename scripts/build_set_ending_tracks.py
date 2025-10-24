#!/usr/bin/env python3
"""Build lookup table of track IDs for set-ending performances."""

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

from phish_setlist_maker.db import session_scope
from phish_setlist_maker.models import Track, Show, Song, SongTrack
from phish_setlist_maker.generator.historical import normalize_set_label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/analytics/features"),
        help="Output directory for set-ending tracks lookup",
    )
    args = parser.parse_args()
    
    args.out_dir.mkdir(parents=True, exist_ok=True)
    
    print("Building set-ending tracks lookup...")
    print("=" * 80)
    
    with session_scope() as session:
        # Subquery: find max position for each show/set
        max_position_subq = (
            select(
                Track.show_id,
                Track.set,
                func.max(Track.position).label("max_position")
            )
            .group_by(Track.show_id, Track.set)
            .subquery()
        )
        
        # Main query: get all set-ending tracks with song info
        stmt = (
            select(
                Track.id.label("track_id"),
                Track.slug.label("track_slug"),
                Track.set.label("set_label"),
                Track.show_id,
                Track.duration,
                Track.likes_count,
                Show.date.label("show_date"),
                Song.title.label("song_name"),
                Song.slug.label("song_slug"),
            )
            .join(
                max_position_subq,
                (Track.show_id == max_position_subq.c.show_id) &
                (Track.set == max_position_subq.c.set) &
                (Track.position == max_position_subq.c.max_position)
            )
            .join(Show, Show.id == Track.show_id)
            .join(SongTrack, SongTrack.track_id == Track.id)
            .join(Song, Song.id == SongTrack.song_id)
            .order_by(Track.show_id, Track.set)
        )
        
        print("Executing query...")
        results = session.execute(stmt).all()
        
        print(f"Found {len(results)} set-ending tracks")
        
        # Build dataframe
        data = []
        for row in results:
            canonical = normalize_set_label(row.set_label) if row.set_label else None
            data.append({
                "track_id": row.track_id,
                "track_slug": row.track_slug,
                "song_name": row.song_name,
                "song_slug": row.song_slug,
                "set_label": row.set_label,
                "canonical_set": canonical,
                "show_id": row.show_id,
                "show_date": row.show_date,
                "duration": row.duration,
                "likes_count": row.likes_count or 0,
            })
        
        df = pd.DataFrame(data)
        
        # Convert show_date to proper datetime
        df["show_date"] = pd.to_datetime(df["show_date"])
        
        # Save to parquet
        output_path = args.out_dir / "set_ending_tracks.parquet"
        df.to_parquet(output_path, index=False)
        
        print(f"\n✅ Saved to {output_path}")
        print(f"   Total tracks: {len(df)}")
        
        # Show breakdown by set
        print("\nBreakdown by canonical set:")
        for canonical_set in ["set1", "set2", "set3", "encore"]:
            count = len(df[df["canonical_set"] == canonical_set])
            unique_songs = df[df["canonical_set"] == canonical_set]["song_slug"].nunique()
            print(f"  {canonical_set}: {count} tracks, {unique_songs} unique songs")
        
        # Show top set enders
        print("\nTop 10 Set 1 enders by frequency:")
        set1_enders = df[df["canonical_set"] == "set1"]["song_name"].value_counts().head(10)
        for song, count in set1_enders.items():
            print(f"  {song}: {count} times")


if __name__ == "__main__":
    main()
