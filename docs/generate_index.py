#!/usr/bin/env python3
"""Generate dates.json index for the EPG Viewer."""

import json
from pathlib import Path


def generate_dates_index():
    """Scan archive directory and generate dates.json."""
    script_dir = Path(__file__).parent
    archive_dir = script_dir.parent / "archive"
    
    if not archive_dir.exists():
        print(f"Archive directory not found: {archive_dir}")
        return
    
    dates = []
    years = {}
    
    for year_dir in sorted(archive_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        
        year = year_dir.name
        year_dates = []
        
        for xml_file in sorted(year_dir.glob("*.xml")):
            date_str = xml_file.stem
            dates.append(date_str)
            year_dates.append(date_str)
        
        if year_dates:
            years[year] = {
                "count": len(year_dates),
                "first": year_dates[0],
                "last": year_dates[-1]
            }
    
    index = {
        "generated": str(Path(__file__).stat().st_mtime),
        "total_dates": len(dates),
        "years": years,
        "dates": dates
    }
    
    output_path = script_dir / "dates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {output_path}")
    print(f"Total dates: {len(dates)}")
    for year, info in years.items():
        print(f"  {year}: {info['count']} days ({info['first']} → {info['last']})")


if __name__ == "__main__":
    generate_dates_index()
