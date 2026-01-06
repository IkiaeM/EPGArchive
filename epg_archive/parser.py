from datetime import datetime
from typing import List, Tuple
from lxml import etree

from .models import Programme, Channel
from .utils import parse_xmltv_datetime


class XMLTVParser:
    
    @staticmethod
    def parse_xml(xml_content: bytes, source_name: str, source_priority: int) -> Tuple[List[Channel], List[Programme]]:
        try:
            root = etree.fromstring(xml_content)
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Invalid XML content from {source_name}: {e}")
        
        channels = []
        programmes = []
        
        for channel_elem in root.findall('channel'):
            channel_id = channel_elem.get('id')
            if not channel_id:
                continue
            
            display_name_elem = channel_elem.find('display-name')
            display_name = display_name_elem.text if display_name_elem is not None else channel_id
            
            icon_elem = channel_elem.find('icon')
            icon = icon_elem.get('src') if icon_elem is not None else None
            
            channels.append(Channel(
                id=channel_id,
                display_name=display_name,
                icon=icon
            ))
        
        for prog_elem in root.findall('programme'):
            try:
                channel = prog_elem.get('channel')
                start_str = prog_elem.get('start')
                stop_str = prog_elem.get('stop')
                
                if not all([channel, start_str, stop_str]):
                    continue
                
                start = parse_xmltv_datetime(start_str)
                stop = parse_xmltv_datetime(stop_str)
                
                duration = (stop - start).total_seconds()
                if duration <= 0 or duration > 86400:
                    continue
                
                title_elem = prog_elem.find('title')
                title = title_elem.text if title_elem is not None else "Unknown"
                
                desc_elem = prog_elem.find('desc')
                description = desc_elem.text if desc_elem is not None else None
                
                category_elem = prog_elem.find('category')
                category = category_elem.text if category_elem is not None else None
                
                episode_elem = prog_elem.find('episode-num')
                episode_num = episode_elem.text if episode_elem is not None else None
                
                icon_elem = prog_elem.find('icon')
                icon = icon_elem.get('src') if icon_elem is not None else None
                
                programmes.append(Programme(
                    channel=channel,
                    start=start,
                    stop=stop,
                    title=title,
                    description=description,
                    category=category,
                    episode_num=episode_num,
                    icon=icon,
                    source=source_name,
                    source_priority=source_priority,
                    last_updated=datetime.now()
                ))
            except Exception as e:
                continue
        
        return channels, programmes
