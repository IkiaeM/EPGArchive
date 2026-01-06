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
import logging

from .models import Channel, Programme

logger = logging.getLogger(__name__)


def normalize_channel_name(name: str) -> str:
    """
    Normalize a channel name for comparison.
    
    - Lowercase
    - Remove accents
    - Remove special characters except alphanumeric
    - Remove common suffixes like HD, +1, etc.
    """
    if not name:
        return ""
    
    # Lowercase
    normalized = name.lower().strip()
    
    # Remove accents
    normalized = unicodedata.normalize('NFKD', normalized)
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    
    # Remove common suffixes/prefixes that don't affect identity
    suffixes_to_remove = [
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
        channels: List[Channel]
    ) -> Tuple[List[Channel], Dict[str, str]]:
        """
        Normalize a list of channels, merging duplicates.
        
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
                # Multiple channels with same normalized name - merge them
                best_channel = self._select_best_channel(channel_group)
                canonical_id = best_channel.id
                
                self.canonical_channels[canonical_id] = best_channel
                
                # Map all channel IDs to the canonical one
                for channel in channel_group:
                    self.channel_mapping[channel.id] = canonical_id
                    
                if len(channel_group) > 1:
                    merged_names = [ch.display_name for ch in channel_group]
                    logger.debug(
                        f"Merged {len(channel_group)} channels into '{best_channel.display_name}': "
                        f"{merged_names}"
                    )
        
        return list(self.canonical_channels.values()), self.channel_mapping
    
    def _select_best_channel(self, channels: List[Channel]) -> Channel:
        """
        Select the best channel from a group of duplicates.
        """
        # Sort by priority score (lower = better)
        scored = [(ch, get_channel_priority_score(ch, ch.id)) for ch in channels]
        scored.sort(key=lambda x: x[1])
        
        best = scored[0][0]
        
        # Enrich best channel with data from others
        for channel, _ in scored[1:]:
            if channel.icon and not best.icon:
                best = Channel(
                    id=best.id,
                    display_name=best.display_name,
                    icon=channel.icon
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
    
    unique_channels, mapping = normalizer.normalize_channels(channels)
    normalized_programmes = normalizer.normalize_programmes(programmes, mapping)
    
    # Logging is handled by the orchestrator for consistent UI
    merged_count = len(channels) - len(unique_channels)
    if merged_count > 0:
        logger.debug(f"Merged {merged_count} duplicate channels ({len(channels)} → {len(unique_channels)})")
    
    return unique_channels, normalized_programmes, mapping
