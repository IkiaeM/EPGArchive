import yaml
from pathlib import Path
from typing import List
from .models import EPGSource


class Config:
    
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.data = self._load_config()
    
    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return self._get_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _get_default_config(self) -> dict:
        return {
            "archive_dir": "./archive",
            "time_tolerance_seconds": 300,
            "json_sources": [
                {
                    "name": "OQEE",
                    "type": "oqee",
                    "priority": 1,
                    "enabled": True,
                    "max_days_per_run": 22
                }
            ],
            "sources": [
                {
                    "name": "EPG.pw",
                    "url": "https://epg.pw/xmltv/epg_FR.xml",
                    "priority": 5,
                    "enabled": True
                },
                {
                    "name": "XMLTV.fr",
                    "url": "https://xmltvfr.fr/xmltv/xmltv.xml",
                    "priority": 6,
                    "enabled": True
                }
            ],
            "html_sources": [
                {
                    "name": "NouvelObs",
                    "type": "nouvelobs",
                    "priority": 10,
                    "enabled": False,
                    "max_days_per_run": 30
                }
            ]
        }
    
    def save_default_config(self):
        config = self._get_default_config()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    def get_sources(self) -> List[EPGSource]:
        sources = []
        for source_data in self.data.get("sources", []):
            sources.append(EPGSource(
                name=source_data["name"],
                url=source_data["url"],
                priority=source_data["priority"],
                enabled=source_data.get("enabled", True)
            ))
        return sources
    
    def get_archive_dir(self) -> Path:
        return Path(self.data.get("archive_dir", "./archive"))
    
    def get_time_tolerance(self) -> int:
        return self.data.get("time_tolerance_seconds", 300)
    
    def get_html_sources(self) -> list:
        """Get HTML-based sources configuration."""
        sources = []
        for source_data in self.data.get("html_sources", []):
            if source_data.get("enabled", True):
                sources.append(source_data)
        return sources
    
    def get_json_sources(self) -> list:
        """Get JSON API sources configuration."""
        sources = []
        for source_data in self.data.get("json_sources", []):
            if source_data.get("enabled", True):
                sources.append(source_data)
        return sources
