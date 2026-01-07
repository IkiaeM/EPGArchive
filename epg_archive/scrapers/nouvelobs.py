"""Scraper for programme-tv.nouvelobs.com archives."""

import asyncio
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup
import httpx

from ..models import Programme, Channel
from ..console import console, print_source_status, create_progress
from rich.table import Table
from rich import box
from ..utils import PARIS_TZ

BASE_URL = "https://programme-tv.nouvelobs.com"
ARCHIVE_START_DATE = date(2024, 1, 1)

TIME_SLOTS = [
    ("0-2", 0, 2),
    ("2-4", 2, 4),
    ("4-6", 4, 6),
    ("6-8", 6, 8),
    ("8-10", 8, 10),
    ("10-12", 10, 12),
    ("12-14", 12, 14),
    ("14-16", 14, 16),
    ("16-18", 16, 18),
    ("18-20", 18, 20),
    ("20-22", 20, 22),
    ("22-0", 22, 24),
]


class NouvelObsScraper:
    """Scraper for NouvelObs TV programme archives."""
    
    def __init__(self, archive_dir: Path, priority: int = 10):
        self.archive_dir = Path(archive_dir)
        self.priority = priority
        self.source_name = "NouvelObs"
        self.timeout = 30
        self._channel_cache: dict = {}
    
    def get_existing_dates(self) -> Set[str]:
        """Get dates already present in archive (supports year-based folders)."""
        existing = set()
        if self.archive_dir.exists():
            for xml_file in self.archive_dir.glob("**/*.xml"):
                existing.add(xml_file.stem)
        return existing
    
    def get_missing_dates(self) -> List[date]:
        """Get list of dates to fetch (from 2024-01-01 to today)."""
        existing = self.get_existing_dates()
        today = date.today()
        
        missing = []
        current = ARCHIVE_START_DATE
        
        while current <= today:
            date_str = current.strftime("%Y-%m-%d")
            if date_str not in existing:
                missing.append(current)
            current += timedelta(days=1)
        
        return missing
    
    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Fetch a single page."""
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except Exception:
            return None
    
    def parse_time_slot_page(
        self, 
        html: str, 
        target_date: date, 
        start_hour: int, 
        end_hour: int
    ) -> Tuple[List[Channel], List[Programme]]:
        """Parse a time slot page and extract programmes."""
        soup = BeautifulSoup(html, "lxml")
        
        channels = []
        programmes = []
        
        tables = soup.find_all("table", class_="tab_grille")
        
        for table in tables:
            row = table.find("tr")
            if not row:
                continue
            
            channel_cell = row.find("td", class_="logo_chaine_g")
            if not channel_cell:
                continue
            
            channel_link = channel_cell.find("a")
            if not channel_link:
                continue
            
            img = channel_cell.find("img")
            if not img:
                continue
            
            channel_name = img.get("alt", "").strip()
            if channel_name.lower().startswith("programme "):
                channel_name = channel_name[10:].strip()
            
            if not channel_name:
                continue
            
            channel_id = self._normalize_channel_id(channel_name)
            
            if channel_id not in self._channel_cache:
                icon_url = img.get("src")
                
                channel = Channel(
                    id=channel_id,
                    display_name=channel_name.title(),
                    icon=icon_url
                )
                self._channel_cache[channel_id] = channel
                channels.append(channel)
            
            prog_cells = row.find_all("td", class_="grille")
            
            for cell in prog_cells:
                prog = self._parse_programme_cell(cell, target_date, channel_id, start_hour)
                if prog:
                    programmes.append(prog)
        
        return channels, programmes
    
    def _parse_programme_cell(
        self, 
        cell, 
        target_date: date, 
        channel_id: str,
        slot_start_hour: int
    ) -> Optional[Programme]:
        """Parse a single programme cell."""
        title_link = cell.find("a", class_=lambda c: c and "titre" in c.split())
        if not title_link:
            return None
        
        title = title_link.get_text(strip=True)
        if not title:
            return None
        
        time_span = cell.find("span", class_=lambda c: c and "b" in c.split())
        hour = slot_start_hour
        minute = 0
        
        if time_span:
            time_text = time_span.get_text(strip=True)
            time_match = re.match(r"(\d{1,2})\.(\d{2})", time_text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
            else:
                time_match2 = re.match(r"(\d{1,2})", time_text)
                if time_match2:
                    hour = int(time_match2.group(1))
        
        if hour == 24:
            hour = 0
        
        try:
            start_dt = PARIS_TZ.localize(
                datetime(target_date.year, target_date.month, target_date.day, hour, minute)
            )
        except Exception:
            return None
        
        stop_dt = start_dt + timedelta(minutes=60)
        
        category = None
        cat_div = cell.find("div", class_=lambda c: c and c.startswith("cat-"))
        if cat_div:
            for cls in cat_div.get("class", []):
                if cls.startswith("cat-") and cls != "cat-selection-obs":
                    category = cls[4:].replace("-", " ").title()
                    break
        
        href = title_link.get("href", "")
        if not category:
            cat_match = re.match(r"/([^/]+)/", href)
            if cat_match:
                category = cat_match.group(1).replace("-", " ").title()
        
        return Programme(
            channel=channel_id,
            start=start_dt,
            stop=stop_dt,
            title=title,
            description=None,
            category=category,
            source=self.source_name,
            source_priority=self.priority,
            last_updated=datetime.now()
        )
    
    def _normalize_channel_id(self, name: str) -> str:
        """Normalize channel name to ID."""
        normalized = name.lower()
        normalized = re.sub(r"[^a-z0-9]", "", normalized)
        return f"{normalized}.nouvelobs"
    
    async def scrape_day(
        self, 
        client: httpx.AsyncClient, 
        target_date: date
    ) -> Tuple[List[Channel], List[Programme]]:
        """Scrape all time slots for a single day."""
        date_str = target_date.strftime("%Y-%m-%d")
        all_channels = []
        all_programmes = []
        
        for slot_name, start_hour, end_hour in TIME_SLOTS:
            url = f"{BASE_URL}/programme-tv/{date_str}/{slot_name}.php"
            
            html = await self.fetch_page(client, url)
            if not html:
                continue
            
            channels, programmes = self.parse_time_slot_page(
                html, target_date, start_hour, end_hour
            )
            
            all_channels.extend(channels)
            all_programmes.extend(programmes)
            
            await asyncio.sleep(0.2)
        
        self._fix_programme_durations(all_programmes)
        
        return all_channels, all_programmes
    
    def _fix_programme_durations(self, programmes: List[Programme]) -> None:
        """Fix programme stop times based on next programme start."""
        by_channel: Dict[str, List[Programme]] = {}
        for prog in programmes:
            if prog.channel not in by_channel:
                by_channel[prog.channel] = []
            by_channel[prog.channel].append(prog)
        
        for channel, progs in by_channel.items():
            progs.sort(key=lambda p: p.start)
            
            for i, prog in enumerate(progs):
                if i + 1 < len(progs):
                    next_prog = progs[i + 1]
                    prog.stop = next_prog.start
                else:
                    prog.stop = prog.start + timedelta(hours=2)
    
    async def scrape_missing_days(
        self, 
        max_days: Optional[int] = None
    ) -> Tuple[List[Channel], List[Programme]]:
        """Scrape all missing days from the archive."""
        missing_dates = self.get_missing_dates()
        
        if not missing_dates:
            console.print("[dim]📺 NouvelObs: Archive is up to date[/dim]")
            return [], []
        
        if max_days:
            missing_dates = missing_dates[:max_days]
        
        total_days = len(missing_dates)
        all_channels: List[Channel] = []
        all_programmes: List[Programme] = []
        daily_stats: List[Tuple[date, int, int]] = []
        
        console.print()
        console.print(f"[bold cyan]📺 NouvelObs Archive Scraper[/bold cyan]")
        console.print(f"[dim]   Fetching {total_days} days: {missing_dates[0]} → {missing_dates[-1]}[/dim]")
        console.print()
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "EPGArchive/1.0"}
        ) as client:
            with create_progress() as progress:
                task = progress.add_task(
                    f"[cyan]Scraping NouvelObs...", 
                    total=total_days
                )
                
                for target_date in missing_dates:
                    channels, programmes = await self.scrape_day(client, target_date)
                    all_channels.extend(channels)
                    all_programmes.extend(programmes)
                    
                    daily_stats.append((target_date, len(channels), len(programmes)))
                    
                    progress.update(
                        task, 
                        advance=1,
                        description=f"[cyan]{target_date} ({len(programmes):,} prog)"
                    )
                    
                    await asyncio.sleep(0.3)
        
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
            title="📺 NouvelObs Scrape Results",
            box=box.ROUNDED,
            border_style="cyan",
            title_style="bold cyan",
        )
        
        table.add_column("Date", style="dim", no_wrap=True)
        table.add_column("Programmes", justify="right", style="green")
        
        shown_stats = daily_stats[:5] if len(daily_stats) > 10 else daily_stats
        for target_date, ch_count, prog_count in shown_stats:
            table.add_row(
                target_date.strftime("%Y-%m-%d"),
                f"{prog_count:,}"
            )
        
        if len(daily_stats) > 10:
            table.add_row("...", "...")
            for target_date, ch_count, prog_count in daily_stats[-3:]:
                table.add_row(
                    target_date.strftime("%Y-%m-%d"),
                    f"{prog_count:,}"
                )
        elif len(daily_stats) > 5:
            for target_date, ch_count, prog_count in daily_stats[5:]:
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
