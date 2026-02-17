from datetime import datetime
from pathlib import Path
from typing import List, Dict
from lxml import etree

from .models import Programme, Channel
from .utils import parse_xmltv_datetime, format_xmltv_datetime


class XMLTVExporter:
    
    def __init__(self, archive_dir: Path):
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def export_by_day(self, programmes: List[Programme], channels: List[Channel]):
        if not programmes:
            return
        
        by_date = {}
        channel_ids_by_date = {}
        
        for prog in programmes:
            date_key = prog.start.strftime('%Y-%m-%d')
            if date_key not in by_date:
                by_date[date_key] = []
                channel_ids_by_date[date_key] = set()
            by_date[date_key].append(prog)
            channel_ids_by_date[date_key].add(prog.channel)
        
        channels_dict = {ch.id: ch for ch in channels}
        
        for date_key, progs in by_date.items():
            channel_ids = channel_ids_by_date[date_key]
            day_channels = [channels_dict[ch_id] for ch_id in channel_ids if ch_id in channels_dict]
            self._export_day(date_key, progs, day_channels)
    
    def _get_year_dir(self, date_key: str) -> Path:
        """Get year-based directory for a date."""
        year = date_key[:4]
        year_dir = self.archive_dir / year
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir
    
    def _export_day(self, date_key: str, programmes: List[Programme], channels: List[Channel]):
        year_dir = self._get_year_dir(date_key)
        file_path = year_dir / f"{date_key}.xml"
        
        root = etree.Element('tv')
        root.set('generator-info-name', 'EPG Archive')
        root.set('generator-info-url', 'https://github.com/IkiaeM/EPGArchive')
        
        for channel in sorted(channels, key=lambda c: c.id):
            channel_elem = etree.SubElement(root, 'channel')
            channel_elem.set('id', channel.id)
            
            display_name = etree.SubElement(channel_elem, 'display-name')
            display_name.text = channel.display_name
            
            if channel.icon:
                icon_elem = etree.SubElement(channel_elem, 'icon')
                icon_elem.set('src', channel.icon)
        
        for prog in sorted(programmes, key=lambda p: (p.channel, p.start)):
            prog_elem = etree.SubElement(root, 'programme')
            prog_elem.set('channel', prog.channel)
            prog_elem.set('start', self._format_datetime(prog.start))
            prog_elem.set('stop', self._format_datetime(prog.stop))
            
            title_elem = etree.SubElement(prog_elem, 'title')
            title_elem.set('lang', 'fr')
            title_elem.text = prog.title
            
            if prog.description:
                desc_elem = etree.SubElement(prog_elem, 'desc')
                desc_elem.set('lang', 'fr')
                desc_elem.text = prog.description
            
            if prog.category:
                cat_elem = etree.SubElement(prog_elem, 'category')
                cat_elem.set('lang', 'fr')
                cat_elem.text = prog.category
            
            if prog.episode_num:
                ep_elem = etree.SubElement(prog_elem, 'episode-num')
                ep_elem.text = prog.episode_num
            
            if prog.icon:
                icon_elem = etree.SubElement(prog_elem, 'icon')
                icon_elem.set('src', prog.icon)
        
        tree = etree.ElementTree(root)
        tree.write(
            str(file_path),
            encoding='utf-8',
            xml_declaration=True,
            pretty_print=True
        )
    
    def _format_datetime(self, dt: datetime) -> str:
        return format_xmltv_datetime(dt)

    def load_existing_channels(self, date_key: str) -> Dict[str, Channel]:
        year_dir = self._get_year_dir(date_key)
        file_path = year_dir / f"{date_key}.xml"

        if not file_path.exists():
            return {}

        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()

            channels: Dict[str, Channel] = {}
            for channel_elem in root.findall('channel'):
                channel_id = channel_elem.get('id')
                if not channel_id:
                    continue

                display_name_elem = channel_elem.find('display-name')
                display_name = display_name_elem.text if display_name_elem is not None else channel_id

                icon_elem = channel_elem.find('icon')
                icon = icon_elem.get('src') if icon_elem is not None else None

                channels[channel_id] = Channel(
                    id=channel_id,
                    display_name=display_name,
                    icon=icon,
                )

            return channels

        except Exception:
            return {}
    
    def load_existing_programmes(self, date_key: str) -> Dict[tuple, Programme]:
        year_dir = self._get_year_dir(date_key)
        file_path = year_dir / f"{date_key}.xml"
        
        if not file_path.exists():
            return {}
        
        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()
            
            existing = {}
            for prog_elem in root.findall('programme'):
                channel = prog_elem.get('channel')
                start_str = prog_elem.get('start')
                stop_str = prog_elem.get('stop')
                
                if not all([channel, start_str, stop_str]):
                    continue
                
                start = self._parse_datetime(start_str)
                stop = self._parse_datetime(stop_str)
                
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
                
                key = (channel, start, stop)
                existing[key] = Programme(
                    channel=channel,
                    start=start,
                    stop=stop,
                    title=title,
                    description=description,
                    category=category,
                    episode_num=episode_num,
                    icon=icon,
                    last_updated=datetime.now()
                )
            
            return existing
            
        except Exception:
            return {}
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        return parse_xmltv_datetime(dt_str)
    
    def get_archive_stats(self) -> Dict:
        if not self.archive_dir.exists():
            return {"total_days": 0, "total_programmes": 0, "date_range": None}
        
        files = sorted(self.archive_dir.glob("**/*.xml"))
        if not files:
            return {"total_days": 0, "total_programmes": 0, "date_range": None}
        
        total_programmes = 0
        for file in files:
            try:
                tree = etree.parse(str(file))
                root = tree.getroot()
                total_programmes += len(root.findall('programme'))
            except Exception:
                continue
        
        first_date = files[0].stem
        last_date = files[-1].stem
        
        return {
            "total_days": len(files),
            "total_programmes": total_programmes,
            "date_range": f"{first_date} to {last_date}"
        }
    
    def merge_with_existing(self, date_key: str, new_programmes: List[Programme]) -> List[Programme]:
        existing = self.load_existing_programmes(date_key)
        
        merged = {}
        updated_count = 0
        
        for prog in new_programmes:
            key = (prog.channel, prog.start, prog.stop)
            
            if key in existing:
                old_prog = existing[key]
                if (old_prog.title != prog.title or 
                    old_prog.description != prog.description or
                    old_prog.category != prog.category):
                    updated_count += 1
                    merged[key] = prog
                else:
                    merged[key] = old_prog
            else:
                merged[key] = prog
        
        for key, prog in existing.items():
            if key not in merged:
                merged[key] = prog
        
        if updated_count > 0:
            from .console import console
            console.print(f"[dim]  → Updated {updated_count} programmes for {date_key}[/dim]")
        
        return list(merged.values())
