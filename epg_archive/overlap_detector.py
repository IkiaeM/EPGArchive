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


def validate_channel_merge(
    channel_ids: List[str],
    programmes: List[Programme],
    max_overlap_percent: float = 10.0
) -> Tuple[bool, str]:
    """
    Validate if merging channels would create too many overlaps.
    
    Args:
        channel_ids: List of channel IDs being merged
        programmes: All programmes from these channels
        max_overlap_percent: Maximum acceptable overlap percentage
    
    Returns:
        (is_valid, reason)
    """
    if len(channel_ids) <= 1:
        return True, "Single channel, no merge needed"
    
    # Filter programmes for these channels
    channel_progs = [p for p in programmes if p.channel in channel_ids]
    
    if not channel_progs:
        return True, "No programmes to validate"
    
    overlaps = detect_overlaps(channel_progs)
    
    if not overlaps:
        return True, "No overlaps detected"
    
    # Count overlapping programmes
    overlapping_progs: Set[int] = set()
    total_overlap_duration = 0
    
    for channel_id, pairs in overlaps.items():
        for prog1, prog2 in pairs:
            overlapping_progs.add(id(prog1))
            overlapping_progs.add(id(prog2))
            overlap_duration = (prog1.stop - prog2.start).total_seconds()
            total_overlap_duration += overlap_duration
    
    overlap_percent = (len(overlapping_progs) / len(channel_progs)) * 100
    
    if overlap_percent > max_overlap_percent:
        avg_overlap = total_overlap_duration / len(overlapping_progs) / 60  # minutes
        return False, (
            f"{overlap_percent:.1f}% of programmes overlap "
            f"(avg {avg_overlap:.0f}min) - likely different channels"
        )
    
    return True, f"Acceptable overlap: {overlap_percent:.1f}%"


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
