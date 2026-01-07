"""Scrapers for non-XMLTV EPG sources (HTML, JSON APIs)."""

from .nouvelobs import NouvelObsScraper
from .oqee import OQEEScraper

__all__ = ["NouvelObsScraper", "OQEEScraper"]
