"""
Programme overlap detector - Identifies overlapping programmes on the same channel.

This helps detect incorrect channel merges where programmes from different channels
were incorrectly merged together.
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict
from datetime import datetime

from .models import Programme


def detect_overlaps(programmes: List[Programme]) -> Dict[str, List[Tuple[Programme, Programme]]]:
    """
    Detect overlapping programmes on each channel.
    
    Returns:
        Dictionary mapping channel IDs to list of overlapping programme pairs.
    """
    overlaps_by_channel: Dict[str, List[Tuple[Programme, Programme]]] = defaultdict(list)
    
    # Group programmes by channel
    by_channel: Dict[str, List[Programme]] = defaultdict(list)
    for prog in programmes:
        by_channel[prog.channel].append(prog)
    
    # Check each channel for overlaps
    for channel_id, channel_progs in by_channel.items():
        # Sort by start time
        sorted_progs = sorted(channel_progs, key=lambda p: p.start)
        
        # Check consecutive programmes for overlaps
        for i in range(len(sorted_progs) - 1):
            prog1 = sorted_progs[i]
            prog2 = sorted_progs[i + 1]
            
            # Check if prog1 ends after prog2 starts (overlap)
            if prog1.stop > prog2.start:
                overlap_duration = (prog1.stop - prog2.start).total_seconds()
                # Only report significant overlaps (> 1 minute)
                if overlap_duration > 60:
                    overlaps_by_channel[channel_id].append((prog1, prog2))
    
    return dict(overlaps_by_channel)


def has_significant_overlaps(
    programmes: List[Programme], 
    threshold_percent: float = 5.0
) -> bool:
    """
    Check if a list of programmes has significant overlaps.
    
    Args:
        programmes: List of programmes to check
        threshold_percent: Percentage of programmes that can overlap before it's considered significant
    
    Returns:
        True if overlaps exceed threshold
    """
    if not programmes:
        return False
    
    overlaps = detect_overlaps(programmes)
    
    # Count total overlapping programmes
    overlapping_progs: Set[int] = set()
    for pairs in overlaps.values():
        for prog1, prog2 in pairs:
            overlapping_progs.add(id(prog1))
            overlapping_progs.add(id(prog2))
    
    overlap_percent = (len(overlapping_progs) / len(programmes)) * 100
    
    return overlap_percent > threshold_percent


def check_pairwise_compatibility(
    channel_ids: List[str],
    programmes: List[Programme],
    max_overlap_percent: float = 15.0
) -> Dict[Tuple[str, str], float]:
    """
    Check compatibility between each pair of channels.
    
    Returns:
        Dictionary mapping channel pairs to their overlap percentage.
    """
    compatibility = {}
    
    for i, ch1 in enumerate(channel_ids):
        for ch2 in channel_ids[i+1:]:
            # Get programmes for this pair only
            pair_progs = [p for p in programmes if p.channel in (ch1, ch2)]
            
            if not pair_progs:
                compatibility[(ch1, ch2)] = 0.0
                continue
            
            overlaps = detect_overlaps(pair_progs)
            
            if not overlaps:
                compatibility[(ch1, ch2)] = 0.0
                continue
            
            overlapping_progs: Set[int] = set()
            for pairs in overlaps.values():
                for prog1, prog2 in pairs:
                    overlapping_progs.add(id(prog1))
                    overlapping_progs.add(id(prog2))
            
            overlap_percent = (len(overlapping_progs) / len(pair_progs)) * 100
            compatibility[(ch1, ch2)] = overlap_percent
    
    return compatibility


def validate_channel_merge(
    channel_ids: List[str],
    programmes: List[Programme],
    max_overlap_percent: float = 15.0
) -> Tuple[bool, str, List[str]]:
    """
    Validate if merging channels would create too many overlaps.
    Uses pairwise analysis to find the best subset to merge.
    
    Args:
        channel_ids: List of channel IDs being merged
        programmes: All programmes from these channels
        max_overlap_percent: Maximum acceptable overlap percentage
    
    Returns:
        (is_valid, reason, channels_to_merge)
        - channels_to_merge: list of channel IDs that should be merged
    """
    if len(channel_ids) <= 1:
        return True, "Single channel, no merge needed", channel_ids
    
    # Filter programmes for these channels
    channel_progs = [p for p in programmes if p.channel in channel_ids]
    
    if not channel_progs:
        return True, "No programmes to validate", channel_ids
    
    # Check pairwise compatibility
    pairwise = check_pairwise_compatibility(channel_ids, channel_progs, max_overlap_percent)
    
    # If only 2 channels, simple check
    if len(channel_ids) == 2:
        overlap = list(pairwise.values())[0]
        if overlap <= max_overlap_percent:
            return True, f"Acceptable overlap: {overlap:.1f}%", channel_ids
        else:
            return False, f"{overlap:.1f}% overlap - likely different channels", []
    
    # For 3+ channels: find the largest compatible subset
    # First, find all compatible pairs (low overlap = same channel)
    compatible_pairs = [(pair, ovl) for pair, ovl in pairwise.items() if ovl <= max_overlap_percent]
    
    if not compatible_pairs:
        # No compatible pairs - all channels are different
        total_progs = len(channel_progs)
        overlaps = detect_overlaps(channel_progs)
        overlap_count = sum(len(pairs) for pairs in overlaps.values())
        return False, f"No compatible pairs found ({overlap_count} overlaps)", []
    
    # Count how many times each channel appears in compatible pairs
    channel_compat_count: Dict[str, int] = defaultdict(int)
    for (ch1, ch2), _ in compatible_pairs:
        channel_compat_count[ch1] += 1
        channel_compat_count[ch2] += 1
    
    # Find channels that are compatible with each other (form a cluster)
    # Start with channels that have the most compatible connections
    sorted_channels = sorted(channel_ids, key=lambda c: channel_compat_count.get(c, 0), reverse=True)
    
    # Build a compatible set starting from the most connected channel
    compatible_set = set()
    for ch in sorted_channels:
        if not compatible_set:
            compatible_set.add(ch)
        else:
            # Check if this channel is compatible with all channels in the set
            is_compatible = True
            for existing_ch in compatible_set:
                pair = (min(ch, existing_ch), max(ch, existing_ch))
                if pair in pairwise and pairwise[pair] > max_overlap_percent:
                    is_compatible = False
                    break
            if is_compatible:
                compatible_set.add(ch)
    
    if len(compatible_set) >= 2:
        excluded = set(channel_ids) - compatible_set
        if excluded:
            return True, f"Merging {len(compatible_set)} compatible channels, excluding {len(excluded)}", list(compatible_set)
        else:
            return True, f"All {len(compatible_set)} channels are compatible", list(compatible_set)
    
    # Fallback: no good merge possible
    return False, "Could not find compatible channel subset", []


def log_overlap_summary(programmes: List[Programme]) -> None:
    """
    Log a summary of programme overlaps for debugging.
    """
    from .console import console
    
    overlaps = detect_overlaps(programmes)
    
    if not overlaps:
        return
    
    total_overlaps = sum(len(pairs) for pairs in overlaps.values())
    affected_channels = len(overlaps)
    
    if total_overlaps > 0:
        console.print(f"[dim yellow]⚠ Found {total_overlaps} programme overlaps across {affected_channels} channels[/dim yellow]")
