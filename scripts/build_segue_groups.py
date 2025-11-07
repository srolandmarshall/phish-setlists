"""Build segue groups from database track data.

Extracts all adjacent track pairs and separates them into:
1. Mandatory segues (≥50 occurrences) - Always enforced
2. Rare segues (<50 occurrences) - Lottery tickets

Outputs:
- data/analytics/features/segue_groups.parquet
- data/analytics/features/rare_segues.parquet
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from phish_setlist_maker.db import session_scope


def extract_adjacent_pairs(session: Session) -> List[dict]:
    """
    Extract all adjacent track pairs from database.
    
    Returns list of dicts with track pair information.
    """
    query = text("""
        SELECT 
            s.id as show_id,
            s.date as show_date,
            t1.id as track1_id,
            t1.title as song1,
            t1.duration as duration1,
            t1.likes_count as likes1,
            t1."set" as set_label,
            t2.id as track2_id,
            t2.title as song2,
            t2.duration as duration2,
            t2.likes_count as likes2
        FROM tracks t1
        JOIN tracks t2 ON t2.show_id = t1.show_id 
            AND t2."set" = t1."set" 
            AND t2.position = t1.position + 1
        JOIN shows s ON s.id = t1.show_id
        ORDER BY s.date DESC
    """)
    
    results = session.execute(query).fetchall()
    
    pairs = []
    for row in results:
        pairs.append({
            'show_id': row.show_id,
            'show_date': row.show_date,
            'set_label': row.set_label,
            'track1_id': row.track1_id,
            'track2_id': row.track2_id,
            'song1': row.song1,
            'song2': row.song2,
            'duration1': row.duration1 or 0,
            'duration2': row.duration2 or 0,
            'likes1': row.likes1 or 0,
            'likes2': row.likes2 or 0,
        })
    
    return pairs


def calculate_frequencies(pairs: List[dict]) -> Dict[Tuple[str, str], int]:
    """
    Calculate how many times each song pair appears.
    
    Returns dict mapping (song1, song2) -> count.
    """
    frequencies = {}
    
    for pair in pairs:
        key = (pair['song1'], pair['song2'])
        frequencies[key] = frequencies.get(key, 0) + 1
    
    return frequencies


def separate_by_frequency(
    pairs: List[dict],
    frequencies: Dict[Tuple[str, str], int],
    threshold: int = 50
) -> Tuple[List[dict], List[dict]]:
    """
    Separate pairs into mandatory (≥threshold) and rare (<threshold).
    
    Returns (mandatory_records, rare_records).
    """
    mandatory_records = []
    rare_records = []
    
    # Calculate total shows for rarity score
    unique_shows = len(set(p['show_id'] for p in pairs))
    
    for pair in pairs:
        key = (pair['song1'], pair['song2'])
        occurrences = frequencies[key]
        
        # Build base record
        segue_id = f"{pair['song1']}_{pair['song2']}_{pair['show_date']}_{pair['set_label']}"
        segue_id = segue_id.lower().replace(' ', '_').replace("'", '')
        
        record = {
            'segue_id': segue_id,
            'segue_type': 'pair',
            'pattern': f"{pair['song1']} -> {pair['song2']}",
            'show_id': pair['show_id'],
            'show_date': pair['show_date'],
            'set_label': pair['set_label'],
            'tracks': [pair['track1_id'], pair['track2_id']],
            'songs': [pair['song1'], pair['song2']],
            'total_duration': pair['duration1'] + pair['duration2'],
            'likes_count': pair['likes1'] + pair['likes2'],
            'historical_occurrences': occurrences,
        }
        
        if occurrences >= threshold:
            # Mandatory segue
            record['frequency'] = 'mandatory'
            record['confidence'] = 0.95
            mandatory_records.append(record)
        else:
            # Rare segue (lottery ticket)
            record['frequency'] = 'rare'
            record['rarity_score'] = occurrences / max(unique_shows, 1)
            record['is_lottery_ticket'] = True
            record['lottery_weight'] = record['likes_count']
            rare_records.append(record)
    
    return mandatory_records, rare_records


def build_dataframe(records: List[dict]) -> pd.DataFrame:
    """Build pandas DataFrame from records."""
    df = pd.DataFrame(records)
    
    # Convert date objects to strings for parquet compatibility
    if 'show_date' in df.columns:
        df['show_date'] = df['show_date'].astype(str)
    
    return df


def build_all_segues(
    session: Session,
    output_dir: Path,
    threshold: int = 50
) -> Tuple[int, int]:
    """
    Build both mandatory and rare segue tables.
    
    Returns (num_mandatory, num_rare).
    """
    print("Extracting adjacent track pairs from database...")
    pairs = extract_adjacent_pairs(session)
    print(f"  Found {len(pairs)} adjacent track pairs")
    
    print("Calculating pair frequencies...")
    frequencies = calculate_frequencies(pairs)
    print(f"  Found {len(frequencies)} unique song pairs")
    
    print(f"Separating by frequency (threshold={threshold})...")
    mandatory, rare = separate_by_frequency(pairs, frequencies, threshold=threshold)
    print(f"  Mandatory segues: {len(mandatory)}")
    print(f"  Rare segues: {len(rare)}")
    
    print("Building DataFrames...")
    df_mandatory = build_dataframe(mandatory)
    df_rare = build_dataframe(rare)
    
    print("Saving to parquet...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    df_mandatory.to_parquet(output_dir / "segue_groups.parquet", index=False)
    df_rare.to_parquet(output_dir / "rare_segues.parquet", index=False)
    
    print(f"✓ Saved {len(mandatory)} mandatory segues to segue_groups.parquet")
    print(f"✓ Saved {len(rare)} rare segues to rare_segues.parquet")
    
    return len(mandatory), len(rare)


def main():
    """Main entry point for building segue groups."""
    with session_scope() as session:
        output_dir = Path(__file__).parent.parent / "data" / "analytics" / "features"
        build_all_segues(session, output_dir=output_dir, threshold=50)


if __name__ == "__main__":
    main()
