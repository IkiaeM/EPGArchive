"""
Channel normalizer - Merges duplicate channels from different sources.

Simple approach:
1. Group channels by normalized name
2. Merge all channels with same name into one
3. Use priority source for logo
4. For programmes: priority source first, fill gaps with secondary sources
"""

import re
import unicodedata
from typing import List, Dict, Tuple, Set
from collections import defaultdict

from .models import Channel, Programme


# Phrases indicating a closed/dead channel - filter these out
CLOSED_CHANNEL_PHRASES = [
    "this channel is now closed",
    "channel closed",
    "chaîne fermée",
    "arrêt de la chaîne",
    "arret de la chaine",
]


def normalize_channel_name(name: str) -> str:
    """
    Normalize a channel name for comparison.
    """
    if not name:
        return ""
    
    normalized = name.lower().strip()
    normalized = unicodedata.normalize('NFKD', normalized)
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    
    # Remove common suffixes
    for suffix in [r'\s*channel$', r'\s*television$', r'\s*tv$', r'\s*hd$', 
                   r'\s*sd$', r'\s*uhd$', r'\s*4k$', r'\s*\+1$', r'\s*\+2$',
                   r'\s*france$', r'\s*fr$']:
        normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)
    
    # Remove all non-alphanumeric
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    
    return normalized


def find_closed_channels(programmes: List[Programme]) -> Set[str]:
    """Find channels that only have 'closed channel' placeholder programmes."""
    by_channel: Dict[str, List[Programme]] = defaultdict(list)
    for prog in programmes:
        by_channel[prog.channel].append(prog)
    
    channels_to_exclude = set()
    for channel_id, progs in by_channel.items():
        if not progs:
            continue
        
        all_closed = all(
            any(phrase in (prog.title or "").lower() for phrase in CLOSED_CHANNEL_PHRASES)
            for prog in progs
        )
        if all_closed:
            channels_to_exclude.add(channel_id)
    
    return channels_to_exclude


def merge_duplicate_channels(
    channels: List[Channel], 
    programmes: List[Programme]
) -> Tuple[List[Channel], List[Programme], Dict[str, str]]:
    """
    Merge duplicate channels and their programmes.
    
    Strategy:
    - Group channels by normalized name
    - Select best channel (logo from highest priority source)
    - For programmes: priority source first, fill gaps with secondary sources
    """
    from .console import console
    
    # Filter closed channels first
    closed_channels = find_closed_channels(programmes)
    if closed_channels:
        console.print(f"[dim]   Filtered {len(closed_channels)} closed channels[/dim]")
        programmes = [p for p in programmes if p.channel not in closed_channels]
        channels = [ch for ch in channels if ch.id not in closed_channels]
    
    # Group channels by normalized name
    by_normalized: Dict[str, List[Channel]] = defaultdict(list)
    for ch in channels:
        norm_name = normalize_channel_name(ch.display_name)
        if norm_name:
            by_normalized[norm_name].append(ch)
    
    # Build channel mapping and select best channel per group
    channel_mapping: Dict[str, str] = {}
    unique_channels: List[Channel] = []
    
    for norm_name, channel_group in by_normalized.items():
        # Sort by source priority (lower = better), then by icon presence
        channel_group.sort(key=lambda c: (
            getattr(c, 'source_priority', 999),
            0 if c.icon else 1
        ))
        
        best = channel_group[0]
        
        # Find best icon from highest priority source that has one
        best_icon = None
        for ch in channel_group:
            if ch.icon:
                best_icon = ch.icon
                break
        
        # Create canonical channel with best icon
        canonical = Channel(
            id=best.id,
            display_name=best.display_name,
            icon=best_icon or best.icon
        )
        unique_channels.append(canonical)
        
        # Map all channel IDs to canonical
        for ch in channel_group:
            channel_mapping[ch.id] = canonical.id
    
    # Merge programmes: priority first, fill gaps with secondary
    merged_programmes = _merge_programmes_by_priority(programmes, channel_mapping)
    
    return unique_channels, merged_programmes, channel_mapping


def _merge_programmes_by_priority(
    programmes: List[Programme],
    channel_mapping: Dict[str, str]
) -> List[Programme]:
    """
    Merge programmes using priority-based gap filling.
    
    For each channel:
    1. Take all programmes from priority source
    2. Fill gaps with programmes from secondary sources
    """
    # Group programmes by canonical channel
    by_channel: Dict[str, List[Programme]] = defaultdict(list)
    for prog in programmes:
        canonical_id = channel_mapping.get(prog.channel, prog.channel)
        # Update channel ID to canonical
        updated_prog = Programme(
            channel=canonical_id,
            start=prog.start,
            stop=prog.stop,
            title=prog.title,
            description=prog.description,
            category=prog.category,
            episode_num=prog.episode_num,
            icon=prog.icon,
            source=prog.source,
            source_priority=prog.source_priority,
            last_updated=prog.last_updated
        )
        by_channel[canonical_id].append(updated_prog)
    
    merged: List[Programme] = []
    
    for channel_id, progs in by_channel.items():
        # Sort by priority (lower = better), then by start time
        progs.sort(key=lambda p: (p.source_priority or 999, p.start))
        
        # Use a timeline to track covered periods
        # Take programmes from priority source, fill gaps with secondary
        timeline: List[Programme] = []
        
        for prog in progs:
            if _can_add_to_timeline(prog, timeline):
                timeline.append(prog)
        
        merged.extend(timeline)
    
    return merged


def _can_add_to_timeline(prog: Programme, timeline: List[Programme]) -> bool:
    """
    Check if programme can be added without significant overlap.
    Allow adding if it fills a gap or only slightly overlaps.
    """
    if not timeline:
        return True
    
    # Check for overlap with existing programmes
    for existing in timeline:
        # Check if there's significant overlap (more than 5 minutes)
        overlap_start = max(prog.start, existing.start)
        overlap_end = min(prog.stop, existing.stop)
        
        if overlap_start < overlap_end:
            overlap_duration = (overlap_end - overlap_start).total_seconds()
            # If more than 5 minutes overlap, skip this programme
            if overlap_duration > 300:
                return False
    
    return True
