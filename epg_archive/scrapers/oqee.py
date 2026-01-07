"""Scraper for OQEE API (Free/Iliad EPG source)."""

import asyncio
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import httpx

from ..models import Programme, Channel
from ..console import console, print_source_status, create_progress
from ..utils import PARIS_TZ
from rich.table import Table
from rich import box

BASE_URL = "https://api.oqee.net/api/v1/epg/all"
DAYS_BACK = 7
DAYS_FORWARD = 14


class OQEEScraper:
    """Scraper for OQEE (Free/Iliad) EPG API."""
    
    def __init__(self, archive_dir: Path, priority: int = 1):
        self.archive_dir = Path(archive_dir)
        self.priority = priority
        self.source_name = "OQEE"
        self.timeout = 30
        self._channel_cache: Dict[str, Channel] = {}
    
    def get_existing_dates(self) -> Set[str]:
        """Get dates already present in archive (supports year-based folders)."""
        existing = set()
        if self.archive_dir.exists():
            for xml_file in self.archive_dir.glob("**/*.xml"):
                existing.add(xml_file.stem)
        return existing
    
    def get_fetchable_date_range(self) -> Tuple[date, date]:
        """Get the date range that can be fetched from OQEE API."""
        today = date.today()
        start_date = today - timedelta(days=DAYS_BACK)
        end_date = today + timedelta(days=DAYS_FORWARD)
        return start_date, end_date
    
    def get_all_available_dates(self) -> List[date]:
        """Get all dates available from OQEE API (always fetch all 22 days)."""
        start_date, end_date = self.get_fetchable_date_range()
        
        dates = []
        current = start_date
        
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    def _get_hour_timestamps(self, target_date: date) -> List[int]:
        """Get all hour timestamps for a given date (24 hours)."""
        timestamps = []
        
        dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
        dt = PARIS_TZ.localize(dt)
        
        for hour in range(24):
            hour_dt = dt + timedelta(hours=hour)
            ts = int(hour_dt.timestamp())
            timestamps.append(ts)
        
        return timestamps
    
    async def fetch_hour(self, client: httpx.AsyncClient, timestamp: int) -> Optional[dict]:
        """Fetch EPG data for a single hour."""
        url = f"{BASE_URL}/{timestamp}"
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                return data["result"]
            else:
                return None
                
        except Exception:
            return None
    
    def _parse_programme(self, prog_data: dict, channel_id: str) -> Optional[Programme]:
        """Parse a programme from OQEE API response."""
        live = prog_data.get("live", prog_data)
        
        title = live.get("title")
        if not title:
            return None
        
        start_ts = live.get("start")
        end_ts = live.get("end")
        
        if not start_ts or not end_ts:
            return None
        
        try:
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc).astimezone(PARIS_TZ)
            stop_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc).astimezone(PARIS_TZ)
        except Exception:
            return None
        
        description = live.get("description") or live.get("short_description")
        category = live.get("category")
        sub_category = live.get("sub_category")
        
        if sub_category and category:
            category = f"{category} / {sub_category}"
        
        return Programme(
            channel=channel_id,
            start=start_dt,
            stop=stop_dt,
            title=title,
            description=description,
            category=category,
            source=self.source_name,
            source_priority=self.priority,
            last_updated=datetime.now()
        )
    
    def _normalize_channel_id(self, oqee_id: str) -> str:
        """Normalize OQEE channel ID."""
        return f"oqee.{oqee_id}"
    
    async def scrape_day(
        self, 
        client: httpx.AsyncClient, 
        target_date: date
    ) -> Tuple[List[Channel], List[Programme]]:
        """Scrape all hours for a single day."""
        timestamps = self._get_hour_timestamps(target_date)
        
        all_programmes: Dict[Tuple[str, int], Programme] = {}
        
        for i, ts in enumerate(timestamps):
            result = await self.fetch_hour(client, ts)
            
            if result:
                entries = result.get("entries", {})
                
                for oqee_ch_id, progs in entries.items():
                    channel_id = self._normalize_channel_id(oqee_ch_id)
                    
                    if channel_id not in self._channel_cache:
                        channel = Channel(
                            id=channel_id,
                            display_name=f"Channel {oqee_ch_id}",
                            icon=None
                        )
                        self._channel_cache[channel_id] = channel
                    
                    for prog_data in progs:
                        prog = self._parse_programme(prog_data, channel_id)
                        if prog:
                            key = (prog.channel, int(prog.start.timestamp()))
                            if key not in all_programmes:
                                all_programmes[key] = prog
            
            await asyncio.sleep(0.05)
        
        channels = list(self._channel_cache.values())
        programmes = list(all_programmes.values())
        
        return channels, programmes
    
    async def scrape_all_days(
        self, 
        max_days: Optional[int] = None
    ) -> Tuple[List[Channel], List[Programme]]:
        """Scrape all available days from OQEE API (always refreshes data)."""
        available_dates = self.get_all_available_dates()
        
        if max_days:
            available_dates = available_dates[:max_days]
        
        if not available_dates:
            console.print("[dim]📡 OQEE: No dates to fetch[/dim]")
            return [], []
        
        total_days = len(available_dates)
        
        all_channels: List[Channel] = []
        all_programmes: List[Programme] = []
        daily_stats: List[Tuple[date, int, int]] = []
        
        console.print()
        console.print("[bold cyan]📡 OQEE API Scraper[/bold cyan]")
        console.print(f"[dim]   Fetching {total_days} days: {available_dates[0]} → {available_dates[-1]}[/dim]")
        console.print()
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "EPGArchive/1.0"}
        ) as client:
            with create_progress() as progress:
                task = progress.add_task(
                    "[cyan]Scraping OQEE...", 
                    total=total_days
                )
                
                for target_date in available_dates:
                    day_start_progs = len(all_programmes)
                    
                    channels, programmes = await self.scrape_day(
                        client, target_date
                    )
                    
                    new_channels = [ch for ch in channels if ch.id not in 
                                   {c.id for c in all_channels}]
                    all_channels.extend(new_channels)
                    all_programmes.extend(programmes)
                    
                    day_progs = len(all_programmes) - day_start_progs
                    daily_stats.append((target_date, len(new_channels), day_progs))
                    
                    progress.update(
                        task,
                        advance=1,
                        description=f"[cyan]{target_date} ({day_progs:,} prog)"
                    )
        
        unique_channels = list({ch.id: ch for ch in all_channels}.values())
        
        self._print_scrape_summary(daily_stats, unique_channels, all_programmes)
        
        return unique_channels, all_programmes
    
    def _print_scrape_summary(
        self, 
        daily_stats: List[Tuple[date, int, int]], 
        channels: List[Channel],
        programmes: List[Programme]
    ) -> None:
        """Print a summary table of the scraping results."""
        console.print()
        
        table = Table(
            title="📡 OQEE Scrape Results",
            box=box.ROUNDED,
            border_style="cyan",
            title_style="bold cyan",
        )
        
        table.add_column("Date", style="dim", no_wrap=True)
        table.add_column("Programmes", justify="right", style="green")
        
        if len(daily_stats) <= 10:
            for target_date, ch_count, prog_count in daily_stats:
                table.add_row(
                    target_date.strftime("%Y-%m-%d"),
                    f"{prog_count:,}"
                )
        else:
            for target_date, ch_count, prog_count in daily_stats[:5]:
                table.add_row(
                    target_date.strftime("%Y-%m-%d"),
                    f"{prog_count:,}"
                )
            table.add_row("...", "...")
            for target_date, ch_count, prog_count in daily_stats[-3:]:
                table.add_row(
                    target_date.strftime("%Y-%m-%d"),
                    f"{prog_count:,}"
                )
        
        table.add_section()
        table.add_row(
            f"[bold]Total ({len(daily_stats)} days)[/bold]",
            f"[bold]{len(programmes):,}[/bold]"
        )
        
        console.print(table)
        
        print_source_status(
            self.source_name,
            "success",
            f"{len(channels)} channels, {len(programmes):,} programmes"
        )
