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
        
        grouped = self._group_by_timeslot(all_programmes)
        
        merged = []
        for key, programmes in grouped.items():
            if len(programmes) == 1:
                merged.append(programmes[0])
            else:
                best_programme = self._select_best_programme(programmes)
                merged.append(best_programme)
        
        return sorted(merged, key=lambda p: (p.channel, p.start))
    
    def _group_by_timeslot(self, programmes: List[Programme]) -> Dict[Tuple, List[Programme]]:
        grouped = defaultdict(list)
        
        for prog in programmes:
            key = (prog.channel, prog.start, prog.stop)
            grouped[key].append(prog)
        
        return grouped
    
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
