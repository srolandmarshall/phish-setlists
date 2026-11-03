"""Pure transformations for historical segue-chain feature artifacts."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd


def complete_chains_from_rows(rows: Iterable[Any]) -> List[dict]:
    """Build contiguous same-show, same-set chains from ordered track rows."""
    chains = []
    current_chain = None

    for row in rows:
        if current_chain is not None:
            if (
                row.show_id == current_chain["show_id"]
                and row.set_label == current_chain["set_label"]
                and row.position == current_chain["last_position"] + 1
            ):
                current_chain["tracks"].append(row.track_id)
                current_chain["songs"].append(row.song)
                current_chain["durations"].append(row.duration or 0)
                current_chain["likes"].append(row.likes_count or 0)
                current_chain["last_position"] = row.position
            else:
                if len(current_chain["tracks"]) >= 2:
                    chains.append(current_chain)
                current_chain = _start_chain(row)
        else:
            current_chain = _start_chain(row)

    if current_chain and len(current_chain["tracks"]) >= 2:
        chains.append(current_chain)

    return chains


def _start_chain(row: Any) -> dict:
    return {
        "show_id": row.show_id,
        "show_date": row.show_date,
        "set_label": row.set_label,
        "tracks": [row.track_id],
        "songs": [row.song],
        "durations": [row.duration or 0],
        "likes": [row.likes_count or 0],
        "last_position": row.position,
    }


def adjacent_pairs_from_rows(rows: Iterable[Any]) -> List[dict]:
    """Normalize adjacent-pair query rows into feature records."""
    return [
        {
            "show_id": row.show_id,
            "show_date": row.show_date,
            "set_label": row.set_label,
            "track1_id": row.track1_id,
            "track2_id": row.track2_id,
            "song1": row.song1,
            "song2": row.song2,
            "duration1": row.duration1 or 0,
            "duration2": row.duration2 or 0,
            "likes1": row.likes1 or 0,
            "likes2": row.likes2 or 0,
        }
        for row in rows
    ]


def extract_subchains(chains: List[dict], max_length: int = 5, min_total_likes: int = 5) -> List[dict]:
    """
    Extract all sub-chains of length 2 to max_length from complete chains.

    This allows us to find interesting sequences like "Light > Manteca -> No Quarter"
    even if they're part of a longer chain.

    NOTE: For lottery tickets, we filter for chains with segue notation (>).
    Tracks with ">" in title indicate intentional segues from phish.net.

    For mandatory segues, we keep all consecutive tracks (by position) since
    we care about the pattern (e.g., Mike's -> Hydrogen -> Weekapaug) regardless
    of whether every performance had perfect segues.

    Args:
        chains: Complete chains from extract_complete_chains()
        max_length: Maximum sub-chain length
        min_total_likes: Minimum total likes to reduce memory usage

    Returns:
        List of sub-chain dicts
    """
    subchains = []

    for chain in chains:
        chain_length = len(chain['tracks'])

        # Extract all sub-chains of length 2 to max_length
        for length in range(2, min(chain_length + 1, max_length + 1)):
            for start_idx in range(chain_length - length + 1):
                end_idx = start_idx + length

                # Pre-filter by likes to reduce memory usage
                likes_subset = chain['likes'][start_idx:end_idx]
                if sum(likes_subset) < min_total_likes:
                    continue

                # Pre-filter for segue notation (>) to only capture true segues
                songs_subset = chain['songs'][start_idx:end_idx]
                has_segue_notation = any('>' in song for song in songs_subset)
                if not has_segue_notation:
                    continue

                subchain = {
                    'show_id': chain['show_id'],
                    'show_date': chain['show_date'],
                    'set_label': chain['set_label'],
                    'tracks': chain['tracks'][start_idx:end_idx],
                    'songs': chain['songs'][start_idx:end_idx],
                    'durations': chain['durations'][start_idx:end_idx],
                    'likes': likes_subset,
                }
                subchains.append(subchain)

    return subchains


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
    threshold: int = 50,
    max_rare_chain_length: int = 5,
    min_lottery_likes: int = 5
) -> Tuple[List[dict], List[dict]]:
    """
    Separate into mandatory pairs (≥threshold) and rare complete chains (<threshold).

    Mandatory segues are stored as pairs for flexibility in generation.
    Rare segues are stored as complete chains to preserve lottery ticket sequences.

    Args:
        max_rare_chain_length: Maximum songs in a rare chain (to avoid capturing entire sets)

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
    # Only include chains up to max_rare_chain_length to avoid capturing entire sets
    # IMPORTANT: Filter for chains with segue notation (>) to ensure true segues
    for chain in chains:
        pattern = tuple(chain['songs'])
        occurrences = chain_frequencies[pattern]
        total_likes = sum(chain['likes'])

        # Check if any track in the chain has ">" segue notation
        # This filters for intentional segues (not just consecutive plays)
        has_segue_notation = any('>' in song for song in chain['songs'])

        if (occurrences < threshold and
            len(chain['tracks']) <= max_rare_chain_length and
            total_likes >= min_lottery_likes and
            has_segue_notation):
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

