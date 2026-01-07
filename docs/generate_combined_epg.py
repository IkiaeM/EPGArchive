#!/usr/bin/env python3
"""Generate a combined EPG XML file with last 7 days + next 14 days."""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path


def merge_xml_files(xml_files):
    """Merge multiple EPG XML files into one, combining channels and programmes."""
    if not xml_files:
        return None
    
    channels = {}
    programmes = []
    
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            for channel in root.findall('channel'):
                channel_id = channel.get('id')
                if channel_id and channel_id not in channels:
                    channels[channel_id] = channel
            
            for programme in root.findall('programme'):
                programmes.append(programme)
        
        except Exception as e:
            print(f"Error parsing {xml_file}: {e}")
            continue
    
    combined_root = ET.Element('tv')
    combined_root.set('generator-info-name', 'EPG Archive')
    combined_root.set('generator-info-url', 'https://github.com/IkiaeM/epg-archive')
    
    for channel in channels.values():
        combined_root.append(channel)
    
    for programme in programmes:
        combined_root.append(programme)
    
    return combined_root


def generate_combined_epg():
    """Generate epg.xml with last 7 days + next 14 days."""
    script_dir = Path(__file__).parent
    archive_dir = script_dir.parent / "archive"
    
    if not archive_dir.exists():
        print(f"Archive directory not found: {archive_dir}")
        return
    
    today = datetime.now().date()
    start_date = today - timedelta(days=7)
    end_date = today + timedelta(days=14)
    
    xml_files = []
    current_date = start_date
    
    while current_date <= end_date:
        year = current_date.year
        date_str = current_date.strftime('%Y-%m-%d')
        xml_path = archive_dir / str(year) / f"{date_str}.xml"
        
        if xml_path.exists():
            xml_files.append(xml_path)
            print(f"Including: {date_str}")
        else:
            print(f"Missing: {date_str}")
        
        current_date += timedelta(days=1)
    
    if not xml_files:
        print("No XML files found to merge")
        return
    
    print(f"\nMerging {len(xml_files)} files...")
    combined_root = merge_xml_files(xml_files)
    
    if combined_root is None:
        print("Failed to merge XML files")
        return
    
    tree = ET.ElementTree(combined_root)
    ET.indent(tree, space='  ')
    
    output_path = script_dir / "epg.xml"
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)
    
    print(f"\n✓ Generated {output_path}")
    print(f"  Channels: {len(combined_root.findall('channel'))}")
    print(f"  Programmes: {len(combined_root.findall('programme'))}")
    print(f"  Date range: {start_date} to {end_date}")


if __name__ == "__main__":
    generate_combined_epg()
