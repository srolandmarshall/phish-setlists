"""Build segue groups from database track data.

Extracts complete segue chains (not just pairs!) and separates them into:
1. Mandatory segues (≥50 occurrences) - Always enforced (stored as pairs for flexibility)
2. Rare segues (<50 occurrences) - Lottery tickets (stored as complete chains!)

Outputs:
- data/analytics/features/segue_groups.parquet (pairs for mandatory)
- data/analytics/features/rare_segues.parquet (complete chains!)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from phish_setlist_maker.db import session_scope


def extract_complete_chains(session: Session) -> List[dict]:
    """
    Extract complete segue chains by following consecutive tracks.

    Returns list of chains where each chain is a dict with:
    - show_id, show_date, set_label
    - tracks: list of track IDs in sequence
    - songs: list of song titles in sequence
    - durations: list of durations
    - likes: list of likes
    """
    # Get all tracks ordered by show, set, position
    query = text("""
        SELECT
            t.id as track_id,
            t.title as song,
            t.duration,
            t.likes_count,
            t.show_id,
            t."set" as set_label,
            t.position,
            s.date as show_date
        FROM tracks t
        JOIN shows s ON s.id = t.show_id
        ORDER BY t.show_id, t."set", t.position
    """)

    results = session.execute(query).fetchall()

    chains = []
    current_chain = None

    for row in results:
        # Check if this continues the current chain
        if current_chain is not None:
            # Same show, same set, consecutive position?
            if (row.show_id == current_chain['show_id']
                and row.set_label == current_chain['set_label']
                and row.position == current_chain['last_position'] + 1):
                # Continue the chain
                current_chain['tracks'].append(row.track_id)
                current_chain['songs'].append(row.song)
                current_chain['durations'].append(row.duration or 0)
                current_chain['likes'].append(row.likes_count or 0)
                current_chain['last_position'] = row.position
            else:
                # Chain ended, save it if it has 2+ songs
                if len(current_chain['tracks']) >= 2:
                    chains.append(current_chain)

                # Start new chain
                current_chain = {
                    'show_id': row.show_id,
                    'show_date': row.show_date,
                    'set_label': row.set_label,
                    'tracks': [row.track_id],
                    'songs': [row.song],
                    'durations': [row.duration or 0],
                    'likes': [row.likes_count or 0],
                    'last_position': row.position,
                }
        else:
            # Start first chain
            current_chain = {
                'show_id': row.show_id,
                'show_date': row.show_date,
                'set_label': row.set_label,
                'tracks': [row.track_id],
                'songs': [row.song],
                'durations': [row.duration or 0],
                'likes': [row.likes_count or 0],
                'last_position': row.position,
            }

    # Don't forget the last chain
    if current_chain and len(current_chain['tracks']) >= 2:
        chains.append(current_chain)

    return chains


def extract_pairs_from_chains(chains: List[dict]) -> List[dict]:
    """Extract all adjacent pairs from complete chains."""
    pairs = []

    for chain in chains:
        # Extract each consecutive pair from the chain
        for i in range(len(chain['tracks']) - 1):
            pairs.append({
                'show_id': chain['show_id'],
                'show_date': chain['show_date'],
                'set_label': chain['set_label'],
                'track1_id': chain['tracks'][i],
                'track2_id': chain['tracks'][i + 1],
                'song1': chain['songs'][i],
                'song2': chain['songs'][i + 1],
                'duration1': chain['durations'][i],
                'duration2': chain['durations'][i + 1],
                'likes1': chain['likes'][i],
                'likes2': chain['likes'][i + 1],
            })

    return pairs


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


def calculate_chain_pattern_frequencies(chains: List[dict]) -> Dict[Tuple[str, ...], int]:
    """
    Calculate how many times each complete chain pattern appears.

    Returns dict mapping (song1, song2, ..., songN) -> count.
    """
    frequencies = {}

    for chain in chains:
        # Create a tuple of all songs in the chain
        pattern = tuple(chain['songs'])
        frequencies[pattern] = frequencies.get(pattern, 0) + 1

    return frequencies


def separate_chains_by_frequency(
    chains: List[dict],
    chain_frequencies: Dict[Tuple[str, ...], int],
    pairs: List[dict],
    pair_frequencies: Dict[Tuple[str, str], int],
    threshold: int = 50
) -> Tuple[List[dict], List[dict]]:
    """
    Separate into mandatory pairs (≥threshold) and rare complete chains (<threshold).

    Mandatory segues are stored as pairs for flexibility in generation.
    Rare segues are stored as complete chains to preserve lottery ticket sequences.

    Returns (mandatory_records, rare_records).
    """
    mandatory_records = []
    rare_records = []

    # Calculate total shows for rarity score
    unique_shows = len(set(c['show_id'] for c in chains))

    # Process pairs for mandatory segues
    for pair in pairs:
        key = (pair['song1'], pair['song2'])
        occurrences = pair_frequencies[key]

        if occurrences >= threshold:
            # Mandatory segue - store as pair
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
                'frequency': 'mandatory',
                'confidence': 0.95,
            }
            mandatory_records.append(record)

    # Process complete chains for rare segues (lottery tickets!)
    for chain in chains:
        pattern = tuple(chain['songs'])
        occurrences = chain_frequencies[pattern]

        if occurrences < threshold:
            # Rare segue - store as complete chain!
            pattern_str = ' -> '.join(chain['songs'])
            segue_id = '_'.join(chain['songs']) + f"_{chain['show_date']}_{chain['set_label']}"
            segue_id = segue_id.lower().replace(' ', '_').replace("'", '')

            # Use '>' for jam segues (no pause), '->' for song changes
            # For now, use '->' for all (we could enhance this with gap detection later)
            pattern_display = ' -> '.join(chain['songs'])

            record = {
                'segue_id': segue_id,
                'segue_type': 'chain',
                'pattern': pattern_display,
                'show_id': chain['show_id'],
                'show_date': chain['show_date'],
                'set_label': chain['set_label'],
                'tracks': chain['tracks'],
                'songs': chain['songs'],
                'total_duration': sum(chain['durations']),
                'likes_count': sum(chain['likes']),
                'historical_occurrences': occurrences,
                'frequency': 'rare',
                'rarity_score': occurrences / max(unique_shows, 1),
                'is_lottery_ticket': True,
                'lottery_weight': sum(chain['likes']),
            }
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

    Mandatory segues (≥threshold): Stored as pairs for generation flexibility
    Rare segues (<threshold): Stored as complete chains for lottery tickets!

    Returns (num_mandatory, num_rare).
    """
    print("Extracting complete segue chains from database...")
    chains = extract_complete_chains(session)
    print(f"  Found {len(chains)} complete segue chains")

    print("Extracting pairs from chains...")
    pairs = extract_pairs_from_chains(chains)
    print(f"  Extracted {len(pairs)} adjacent track pairs")

    print("Calculating frequencies...")
    pair_frequencies = calculate_frequencies(pairs)
    chain_frequencies = calculate_chain_pattern_frequencies(chains)
    print(f"  Found {len(pair_frequencies)} unique song pairs")
    print(f"  Found {len(chain_frequencies)} unique chain patterns")

    print(f"Separating by frequency (threshold={threshold})...")
    mandatory, rare = separate_chains_by_frequency(
        chains, chain_frequencies, pairs, pair_frequencies, threshold=threshold
    )
    print(f"  Mandatory segues (pairs): {len(mandatory)}")
    print(f"  Rare segues (complete chains): {len(rare)}")

    # Show some stats about rare chains
    if rare:
        chain_lengths = [len(r['tracks']) for r in rare]
        print(f"  Rare chain lengths: min={min(chain_lengths)}, max={max(chain_lengths)}, avg={sum(chain_lengths)/len(chain_lengths):.1f}")

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
