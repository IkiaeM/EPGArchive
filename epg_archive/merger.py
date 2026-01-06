from typing import List, Dict, Tuple
from collections import defaultdict
from datetime import datetime
import logging

from .models import Programme

logger = logging.getLogger(__name__)


class EPGMerger:
    
    def __init__(self, time_tolerance_seconds: int = 300):
        self.time_tolerance_seconds = time_tolerance_seconds
    
    def merge_programmes(self, all_programmes: List[Programme]) -> List[Programme]:
        if not all_programmes:
            return []
        
        # Group by channel first
        by_channel = defaultdict(list)
        for prog in all_programmes:
            by_channel[prog.channel].append(prog)
        
        merged = []
        for channel, channel_progs in by_channel.items():
            # Sort by start time
            channel_progs.sort(key=lambda p: p.start)
            
            # Merge similar programmes within tolerance
            merged_channel_progs = self._merge_similar_programmes(channel_progs)
            
            # Remove overlapping programmes (keep higher priority)
            cleaned_progs = self._remove_overlaps(merged_channel_progs)
            merged.extend(cleaned_progs)
        
        return sorted(merged, key=lambda p: (p.channel, p.start))
    
    def _merge_similar_programmes(self, programmes: List[Programme]) -> List[Programme]:
        """
        Merge programmes that are similar (same title, close start times).
        Programmes must already be sorted by start time.
        """
        if not programmes:
            return []
        
        merged = []
        i = 0
        
        while i < len(programmes):
            current = programmes[i]
            similar_group = [current]
            
            # Look ahead for similar programmes within tolerance
            j = i + 1
            while j < len(programmes):
                candidate = programmes[j]
                
                # Check if candidate is similar to current
                time_diff = abs((candidate.start - current.start).total_seconds())
                
                if time_diff <= self.time_tolerance_seconds:
                    # Same title (case insensitive)?
                    if candidate.title.lower() == current.title.lower():
                        similar_group.append(candidate)
                        j += 1
                    else:
                        # Different title but within time window - check next
                        j += 1
                else:
                    # Beyond tolerance window, stop looking
                    break
            
            # Merge the similar group
            if len(similar_group) == 1:
                merged.append(current)
            else:
                best = self._select_best_programme(similar_group)
                merged.append(best)
                logger.debug(
                    f"Merged {len(similar_group)} similar programmes: '{best.title}' "
                    f"on {best.channel} at {best.start.strftime('%H:%M')}"
                )
            
            # Skip all programmes in the similar group
            i += len(similar_group)
        
        return merged
    
    def _remove_overlaps(self, programmes: List[Programme]) -> List[Programme]:
        """
        Remove overlapping programmes, keeping the one with higher priority.
        Programmes must already be sorted by start time.
        """
        if not programmes:
            return []
        
        cleaned = []
        i = 0
        
        while i < len(programmes):
            current = programmes[i]
            
            # Check if current overlaps with any already accepted programme
            overlaps_with_accepted = False
            for accepted in cleaned:
                # Check if they overlap
                if (current.start < accepted.stop and current.stop > accepted.start):
                    # They overlap - keep the one with better priority
                    if current.source_priority < accepted.source_priority:
                        # Current has better priority, remove accepted and add current
                        cleaned.remove(accepted)
                        logger.debug(
                            f"Replaced '{accepted.title}' ({accepted.start.strftime('%H:%M')}) "
                            f"with '{current.title}' ({current.start.strftime('%H:%M')}) - better priority"
                        )
                    else:
                        # Accepted has better priority, skip current
                        overlaps_with_accepted = True
                        logger.debug(
                            f"Skipped '{current.title}' ({current.start.strftime('%H:%M')}) - "
                            f"overlaps with '{accepted.title}' (lower priority)"
                        )
                        break
            
            if not overlaps_with_accepted:
                cleaned.append(current)
            
            i += 1
        
        return cleaned
    
    def _select_best_programme(self, programmes: List[Programme]) -> Programme:
        if len(programmes) == 1:
            return programmes[0]
        
        title_votes = defaultdict(list)
        for prog in programmes:
            title_votes[prog.title.lower()].append(prog)
        
        if len(title_votes) > 1:
            vote_counts = [(title, len(progs)) for title, progs in title_votes.items()]
            vote_counts.sort(key=lambda x: x[1], reverse=True)
            
            if vote_counts[0][1] >= 2:
                winning_title = vote_counts[0][0]
                candidates = title_votes[winning_title]
                logger.debug(f"Consensus found: {vote_counts[0][1]} sources agree on '{winning_title}'")
            else:
                candidates = programmes
        else:
            candidates = programmes
        
        candidates.sort(key=lambda p: p.source_priority)
        best = candidates[0]
        
        for candidate in candidates[1:]:
            if candidate.description and not best.description:
                best.description = candidate.description
            if candidate.category and not best.category:
                best.category = candidate.category
            if candidate.episode_num and not best.episode_num:
                best.episode_num = candidate.episode_num
            if candidate.icon and not best.icon:
                best.icon = candidate.icon
        
        return best
