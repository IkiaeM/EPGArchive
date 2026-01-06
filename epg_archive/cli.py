import asyncio
import sys
from pathlib import Path
from argparse import ArgumentParser

from .config import Config
from .orchestrator import EPGOrchestrator
from .console import (
    setup_logging,
    console,
    print_header,
    print_stats,
    print_error,
    print_success,
    print_warning,
)


def main():
    parser = ArgumentParser(
        description="EPG Archive - Long-term EPG archiving system"
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='Create a default configuration file'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show archive statistics'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    config_path = Path(args.config)
    
    if args.init_config:
        config = Config(config_path)
        config.save_default_config()
        print_success(f"Default configuration saved to {config_path}")
        return 0
    
    if not config_path.exists():
        print_error(f"Configuration file not found: {config_path}")
        console.print("[dim]Run with --init-config to create a default configuration[/dim]")
        return 1
    
    try:
        config = Config(config_path)
        sources = config.get_sources()
        archive_dir = config.get_archive_dir()
        time_tolerance = config.get_time_tolerance()
        
        if args.stats:
            from .exporter import XMLTVExporter
            print_header()
            exporter = XMLTVExporter(archive_dir)
            stats = exporter.get_archive_stats()
            print_stats(stats)
            return 0
        
        print_header()
        
        orchestrator = EPGOrchestrator(sources, archive_dir, time_tolerance)
        stats = asyncio.run(orchestrator.run())
        
        if stats:
            print_success("EPG archive update completed successfully")
        else:
            print_warning("EPG archive update completed with warnings")
        
        return 0
        
    except Exception as e:
        print_error(str(e))
        if args.verbose:
            console.print_exception()
        return 1


if __name__ == '__main__':
    sys.exit(main())
