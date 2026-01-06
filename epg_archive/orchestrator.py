import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .models import EPGSource, Programme, Channel
from .fetcher import EPGFetcher
from .parser import XMLTVParser
from .merger import EPGMerger
from .exporter import XMLTVExporter
from .console import console, create_progress, print_source_status, print_summary

logger = logging.getLogger(__name__)


class EPGOrchestrator:
    
    def __init__(self, sources: List[EPGSource], archive_dir: Path, time_tolerance: int = 300):
        self.sources = [s for s in sources if s.enabled]
        self.sources.sort(key=lambda s: s.priority)
        self.fetcher = EPGFetcher()
        self.parser = XMLTVParser()
        self.merger = EPGMerger(time_tolerance_seconds=time_tolerance)
        self.exporter = XMLTVExporter(archive_dir)
    
    async def _fetch_source(self, source: EPGSource) -> Optional[Tuple[EPGSource, bytes]]:
        """Fetch a single source, return None on failure."""
        xml_content = await self.fetcher.fetch(source.url)
        if xml_content:
            return (source, xml_content)
        return None
    
    async def run(self) -> Optional[Dict[str, Any]]:
        logger.info(f"Starting EPG archive update with {len(self.sources)} sources")
        
        all_programmes: List[Programme] = []
        all_channels: List[Channel] = []
        sources_ok = 0
        sources_failed = 0
        
        console.print()
        console.print("[bold cyan]Fetching sources...[/bold cyan]")
        
        fetch_tasks = [self._fetch_source(source) for source in self.sources]
        results = await asyncio.gather(*fetch_tasks)
        
        for result in results:
            if result is None:
                sources_failed += 1
                continue
            
            source, xml_content = result
            
            try:
                channels, programmes = self.parser.parse_xml(
                    xml_content,
                    source.name,
                    source.priority
                )
                
                print_source_status(
                    source.name,
                    "success",
                    f"{len(channels)} channels, {len(programmes):,} programmes"
                )
                
                all_channels.extend(channels)
                all_programmes.extend(programmes)
                sources_ok += 1
                
            except Exception as e:
                logger.error(f"Error parsing {source.name}: {e}")
                print_source_status(source.name, "error", str(e))
                sources_failed += 1
        
        if not all_programmes:
            logger.warning("No programmes fetched from any source")
            return None
        
        programmes_before = len(all_programmes)
        console.print()
        console.print(f"[dim]Merging {programmes_before:,} programmes...[/dim]")
        
        merged_programmes = self.merger.merge_programmes(all_programmes)
        programmes_after = len(merged_programmes)
        
        unique_channels = {ch.id: ch for ch in all_channels}
        channels_list = list(unique_channels.values())
        
        by_date: Dict[str, List[Programme]] = {}
        for prog in merged_programmes:
            date_key = prog.start.strftime('%Y-%m-%d')
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(prog)
        
        console.print(f"[dim]Exporting {len(by_date)} days to archive...[/dim]")
        
        for date_key, progs in by_date.items():
            self.exporter.merge_with_existing(date_key, progs)
        
        self.exporter.export_by_day(merged_programmes, channels_list)
        
        stats = self.exporter.get_archive_stats()
        
        print_summary(
            sources_ok=sources_ok,
            sources_failed=sources_failed,
            programmes_before=programmes_before,
            programmes_after=programmes_after,
            days_exported=len(by_date),
        )
        
        return stats
