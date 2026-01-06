from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Programme:
    channel: str
    start: datetime
    stop: datetime
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    episode_num: Optional[str] = None
    icon: Optional[str] = None
    source: Optional[str] = None
    source_priority: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __hash__(self):
        return hash((self.channel, self.start, self.stop))
    
    def get_key(self) -> tuple:
        return (self.channel, self.start, self.stop)
    
    def is_similar(self, other: 'Programme', tolerance_seconds: int = 300) -> bool:
        if self.channel != other.channel:
            return False
        
        time_diff = abs((self.start - other.start).total_seconds())
        return time_diff <= tolerance_seconds and self.title.lower() == other.title.lower()


@dataclass
class Channel:
    id: str
    display_name: str
    icon: Optional[str] = None
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class EPGSource:
    name: str
    url: str
    priority: int
    enabled: bool = True
    
    def __hash__(self):
        return hash(self.name)
