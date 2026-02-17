import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .models import EPGSource, Programme, Channel
from .fetcher import EPGFetcher
from .parser import XMLTVParser
from .merger import EPGMerger
from .exporter import XMLTVExporter
from .console import console, create_progress, print_source_status, print_summary
from .scrapers import NouvelObsScraper, OQEEScraper
from .channel_normalizer import merge_duplicate_channels


class EPGOrchestrator:
    
    def __init__(
        self, 
        sources: List[EPGSource], 
        archive_dir: Path, 
        time_tolerance: int = 300,
        html_sources: Optional[List[dict]] = None,
        json_sources: Optional[List[dict]] = None
    ):
        self.sources = [s for s in sources if s.enabled]
        self.sources.sort(key=lambda s: s.priority)
        self.archive_dir = archive_dir
        self.html_sources = html_sources or []
        self.json_sources = json_sources or []
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
        total_sources = len(self.sources) + len([s for s in self.html_sources if s.get('enabled')]) + len([s for s in self.json_sources if s.get('enabled')])
        console.print(f"[dim]Starting update with {total_sources} sources...[/dim]")
        
        all_programmes: List[Programme] = []
        all_channels: List[Channel] = []
        sources_ok = 0
        sources_failed = 0
        
        console.print()
        console.print("[bold cyan]Fetching sources...[/bold cyan]")
        
        fetch_tasks = [self._fetch_source(source) for source in self.sources]
        results = await asyncio.gather(*fetch_tasks)
        
        for i, result in enumerate(results):
            if result is None:
                source = self.sources[i]
                print_source_status(source.name, "error", "Failed to fetch")
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
                print_source_status(source.name, "error", str(e))
                sources_failed += 1
        
        for json_source in self.json_sources:
            try:
                if json_source.get("type") == "oqee":
                    scraper = OQEEScraper(
                        archive_dir=self.archive_dir,
                        priority=json_source.get("priority", 1)
                    )
                    max_days = json_source.get("max_days_per_run")
                    channels, programmes = await scraper.scrape_all_days(max_days)
                    
                    all_channels.extend(channels)
                    all_programmes.extend(programmes)
                    
                    if programmes:
                        sources_ok += 1
            except Exception as e:
                print_source_status(json_source.get("name", "JSON source"), "error", str(e))
                sources_failed += 1
        
        for html_source in self.html_sources:
            try:
                if html_source.get("type") == "nouvelobs":
                    scraper = NouvelObsScraper(
                        archive_dir=self.archive_dir,
                        priority=html_source.get("priority", 10)
                    )
                    max_days = html_source.get("max_days_per_run")
                    channels, programmes = await scraper.scrape_missing_days(max_days)
                    
                    all_channels.extend(channels)
                    all_programmes.extend(programmes)
                    
                    if programmes:
                        sources_ok += 1
            except Exception as e:
                print_source_status(html_source.get("name", "HTML source"), "error", str(e))
                sources_failed += 1
        
        if not all_programmes:
            console.print("[yellow]No programmes fetched from any source[/yellow]")
            return None
        
        programmes_before = len(all_programmes)
        channels_before = len(set(ch.id for ch in all_channels))
        console.print()
        
        # Normalize channels first (merge duplicates like "LCI" vs "lci")
        with console.status(f"[dim]Normalizing {channels_before} channels...[/dim]"):
            unique_channels, all_programmes, channel_mapping = merge_duplicate_channels(
                all_channels, all_programmes
            )
        
        channels_list = unique_channels
        merged_count = channels_before - len(channels_list)
        if merged_count > 0:
            console.print(f"[dim]→ Merged {merged_count} duplicate channels ({channels_before} → {len(channels_list)})[/dim]")
        console.print(f"[dim]Merged to {len(channels_list)} unique channels[/dim]")
        console.print(f"[dim]Merging {programmes_before:,} programmes...[/dim]")
        
        merged_programmes = self.merger.merge_programmes(all_programmes)
        programmes_after = len(merged_programmes)
        
        by_date: Dict[str, List[Programme]] = {}
        for prog in merged_programmes:
            date_key = prog.start.strftime('%Y-%m-%d')
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(prog)
        
        console.print()
        with console.status(f"[cyan]Exporting {len(by_date)} days to archive...[/cyan]"):
            merged_with_archive: List[Programme] = []
            export_channels: Dict[str, Channel] = {ch.id: ch for ch in channels_list}

            for date_key, progs in by_date.items():
                merged_day_programmes = self.exporter.merge_with_existing(date_key, progs)
                merged_with_archive.extend(merged_day_programmes)

                existing_channels = self.exporter.load_existing_channels(date_key)
                for channel_id, channel in existing_channels.items():
                    if channel_id not in export_channels:
                        export_channels[channel_id] = channel
            
            self.exporter.export_by_day(merged_with_archive, list(export_channels.values()))
            programmes_after = len(merged_with_archive)
        
        stats = self.exporter.get_archive_stats()
        
        print_summary(
            sources_ok=sources_ok,
            sources_failed=sources_failed,
            programmes_before=programmes_before,
            programmes_after=programmes_after,
            days_exported=len(by_date),
        )
        
        return stats
