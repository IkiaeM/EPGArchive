"""Shared utilities for EPG Archive."""

from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')


def parse_xmltv_datetime(dt_str: str) -> datetime:
    """Parse XMLTV datetime format to Python datetime with timezone."""
    dt_str = dt_str.strip()
    
    if ' ' in dt_str:
        parts = dt_str.split(' ')
        dt_part = parts[0]
        tz_part = parts[1] if len(parts) > 1 else None
        
        if len(dt_part) == 14:
            dt = datetime.strptime(dt_part, '%Y%m%d%H%M%S')
            
            if tz_part:
                try:
                    offset_hours = int(tz_part[:3])
                    offset_minutes = int(tz_part[0] + tz_part[3:5]) if len(tz_part) >= 5 else 0
                    tz_offset = timezone(timedelta(hours=offset_hours, minutes=offset_minutes))
                    return dt.replace(tzinfo=tz_offset)
                except (ValueError, IndexError):
                    pass
            
            return PARIS_TZ.localize(dt)
        else:
            return date_parser.parse(dt_str)
    
    if len(dt_str) == 14:
        dt = datetime.strptime(dt_str, '%Y%m%d%H%M%S')
        return PARIS_TZ.localize(dt)
    elif len(dt_str) > 14:
        base_dt = dt_str[:14]
        dt = datetime.strptime(base_dt, '%Y%m%d%H%M%S')
        return PARIS_TZ.localize(dt)
    else:
        return date_parser.parse(dt_str)


def format_xmltv_datetime(dt: datetime) -> str:
    """Format datetime to XMLTV format with timezone."""
    if dt.tzinfo is None:
        dt = PARIS_TZ.localize(dt)
    
    tz_str = dt.strftime('%z')
    if tz_str:
        tz_formatted = tz_str[:3] + tz_str[3:]
    else:
        tz_formatted = '+0100'
    
    return dt.strftime('%Y%m%d%H%M%S') + ' ' + tz_formatted
