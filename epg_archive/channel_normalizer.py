"""
Channel normalizer - Merges duplicate channels from different sources.

Handles cases like:
- "LCI" vs "lci" vs "Lci" (case differences)
- "La Une" from different sources with different IDs
- "TF1.fr" vs "tf1.nouvelobs" (same channel, different source IDs)
"""

import re
import unicodedata
from typing import List, Dict, Tuple
from collections import defaultdict

from .models import Channel, Programme
from .overlap_detector import validate_channel_merge


def normalize_channel_name(name: str) -> str:
    """
    Normalize a channel name for comparison.
    
    - Lowercase
    - Remove accents
    - Remove special characters except alphanumeric
    - Remove common suffixes like HD, +1, Channel, TV, etc.
    """
    if not name:
        return ""
    
    # Lowercase
    normalized = name.lower().strip()
    
    # Remove accents
    normalized = unicodedata.normalize('NFKD', normalized)
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    
    # Remove common suffixes/prefixes that don't affect identity
    # Order matters: remove longer patterns first
    suffixes_to_remove = [
        r'\s*channel$',
        r'\s*television$',
        r'\s*tv$',
        r'\s*hd$',
        r'\s*sd$',
        r'\s*uhd$',
        r'\s*4k$',
        r'\s*\+1$',
        r'\s*\+2$',
        r'\s*france$',
        r'\s*fr$',
    ]
    for suffix in suffixes_to_remove:
        normalized = re.sub(suffix, '', normalized, flags=re.IGNORECASE)
    
    # Remove all non-alphanumeric characters
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    
    return normalized


def get_channel_priority_score(channel: Channel, source_id: str) -> int:
    """
    Calculate priority score for a channel.
    Lower score = higher priority.
    
    Prefer:
    - Channels with icons
    - Channels with proper display names (not just IDs)
    - Channels from primary sources (shorter IDs often = main sources)
    """
    score = 0
    
    # Penalize if no icon
    if not channel.icon:
        score += 10
    
    # Penalize if display_name looks like an ID
    if channel.display_name == channel.id:
        score += 5
    
    # Penalize long source-specific IDs (like "lci.nouvelobs")
    if '.' in channel.id or len(channel.id) > 20:
        score += 3
    
    # Prefer numeric IDs (often from primary sources)
    if channel.id.isdigit():
        score -= 2
    
    return score


class ChannelNormalizer:
    """
    Normalizes and merges channels from multiple sources.
    """
    
    def __init__(self):
        self.channel_mapping: Dict[str, str] = {}  # old_id -> canonical_id
        self.canonical_channels: Dict[str, Channel] = {}  # canonical_id -> Channel
    
    def normalize_channels(
        self, 
        channels: List[Channel],
        programmes: List[Programme] = None
    ) -> Tuple[List[Channel], Dict[str, str]]:
        """
        Normalize a list of channels, merging duplicates.
        
        Args:
            channels: List of channels to normalize
            programmes: Optional list of programmes to validate merges
        
        Returns:
            - List of unique channels
            - Mapping from original channel IDs to canonical IDs
        """
        # Group channels by normalized name
        by_normalized_name: Dict[str, List[Channel]] = defaultdict(list)
        
        for channel in channels:
            normalized_name = normalize_channel_name(channel.display_name)
            if normalized_name:
                by_normalized_name[normalized_name].append(channel)
        
        # For each group, select the best channel and create mapping
        self.channel_mapping = {}
        self.canonical_channels = {}
        
        for normalized_name, channel_group in by_normalized_name.items():
            if len(channel_group) == 1:
                # Only one channel with this name, keep as-is
                channel = channel_group[0]
                self.canonical_channels[channel.id] = channel
                self.channel_mapping[channel.id] = channel.id
            else:
                # Multiple channels with same normalized name - validate merge
                channel_ids = [ch.id for ch in channel_group]
                
                # If programmes provided, validate the merge won't create overlaps
                channels_to_merge = channel_ids
                excluded_channels = []
                
                if programmes:
                    is_valid, reason, compatible_ids = validate_channel_merge(
                        channel_ids, programmes, max_overlap_percent=15.0
                    )
                    
                    if compatible_ids:
                        channels_to_merge = compatible_ids
                        excluded_channels = [ch for ch in channel_ids if ch not in compatible_ids]
                    else:
                        # No compatible channels found
                        from .console import console
                        merged_names = [ch.display_name for ch in channel_group]
                        console.print(f"[dim yellow]   Skipping merge of {merged_names}: {reason}[/dim yellow]")
                        # Keep all separate
                        for channel in channel_group:
                            self.canonical_channels[channel.id] = channel
                            self.channel_mapping[channel.id] = channel.id
                        continue
                
                # Merge the compatible channels
                mergeable_channels = [ch for ch in channel_group if ch.id in channels_to_merge]
                if len(mergeable_channels) >= 2:
                    best_channel = self._select_best_channel(mergeable_channels)
                    canonical_id = best_channel.id
                    
                    self.canonical_channels[canonical_id] = best_channel
                    
                    # Map merged channel IDs to the canonical one
                    for channel in mergeable_channels:
                        self.channel_mapping[channel.id] = canonical_id
                elif len(mergeable_channels) == 1:
                    channel = mergeable_channels[0]
                    self.canonical_channels[channel.id] = channel
                    self.channel_mapping[channel.id] = channel.id
                
                # Keep excluded channels separate
                for channel in channel_group:
                    if channel.id in excluded_channels:
                        self.canonical_channels[channel.id] = channel
                        self.channel_mapping[channel.id] = channel.id
        
        return list(self.canonical_channels.values()), self.channel_mapping
    
    def _select_best_channel(self, channels: List[Channel]) -> Channel:
        """
        Select the best channel from a group of duplicates.
        Uses source priority for logo selection.
        """
        # Sort by priority score (lower = better)
        scored = [(ch, get_channel_priority_score(ch, ch.id)) for ch in channels]
        scored.sort(key=lambda x: x[1])
        
        best = scored[0][0]
        
        # Find the best icon based on priority
        # Channels with icons, sorted by their priority score
        channels_with_icons = [(ch, score) for ch, score in scored if ch.icon]
        
        best_icon = None
        if channels_with_icons:
            # Take icon from highest priority channel that has one
            best_icon = channels_with_icons[0][0].icon
        
        # Create final channel with best attributes
        if best_icon and best_icon != best.icon:
            best = Channel(
                id=best.id,
                display_name=best.display_name,
                icon=best_icon
            )
        
        return best
    
    def normalize_programmes(
        self, 
        programmes: List[Programme], 
        channel_mapping: Dict[str, str]
    ) -> List[Programme]:
        """
        Update programme channel IDs to use canonical channel IDs.
        """
        normalized = []
        
        for prog in programmes:
            canonical_id = channel_mapping.get(prog.channel, prog.channel)
            
            if canonical_id != prog.channel:
                # Create new programme with updated channel ID
                normalized.append(Programme(
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
                ))
            else:
                normalized.append(prog)
        
        return normalized


def merge_duplicate_channels(
    channels: List[Channel], 
    programmes: List[Programme]
) -> Tuple[List[Channel], List[Programme], Dict[str, str]]:
    """
    Convenience function to normalize channels and programmes.
    
    Returns:
        - Deduplicated channels
        - Programmes with updated channel IDs
        - Channel ID mapping
    """
    normalizer = ChannelNormalizer()
    
    # Pass programmes to validate merges
    unique_channels, mapping = normalizer.normalize_channels(channels, programmes)
    normalized_programmes = normalizer.normalize_programmes(programmes, mapping)
    
    # Logging is handled by the orchestrator for consistent UI
    merged_count = len(channels) - len(unique_channels)
    
    return unique_channels, normalized_programmes, mapping
