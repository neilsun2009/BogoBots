#!/usr/bin/env python
"""
Standalone script for running news crawl via cronjob.

Usage:
    # Run all active sources
    python -m BogoBots.crawlers.scripts.run_news_crawl
    
    # Run specific source
    python -m BogoBots.crawlers.scripts.run_news_crawl --source-id 1
    
    # Run with lookback period
    python -m BogoBots.crawlers.scripts.run_news_crawl --days 7
    
    # Generate summaries with LLM
    python -m BogoBots.crawlers.scripts.run_news_crawl --summarize
    
    # Dry run (don't save to database)
    python -m BogoBots.crawlers.scripts.run_news_crawl --dry-run
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from BogoBots.database.session import get_session
from BogoBots.models.news_source import NewsSource
from BogoBots.services.news_source_service import NewsSourceService
from BogoBots.crawlers.adapters.rss_adapter import RSSAdapter


def run_crawl_for_source(source: NewsSource, since: datetime, 
                         summarize: bool = False, dry_run: bool = False) -> Dict:
    """
    Run crawl for a single source.
    
    Args:
        source: NewsSource to crawl
        since: Lookback datetime
        summarize: Whether to generate LLM summaries
        dry_run: If True, don't save to database
    
    Returns:
        Dict with crawl statistics
    """
    stats = {
        'source_name': source.name,
        'source_type': source.source_type,
        'fetched': 0,
        'saved': 0,
        'duplicates': 0,
        'errors': 0,
        'summarized': 0
    }
    
    print(f"\n[CRAWL] Starting crawl for '{source.name}' ({source.source_type})")
    print(f"        URL: {source.url}")
    print(f"        Since: {since}")
    
    try:
        # RSS-only fetching for now
        if source.source_type != 'RSS':
            print(f"[SKIP] source_type '{source.source_type}' is disabled. RSS only for now.")
            return stats
        try:
            crawler = RSSAdapter(source)
        except Exception as e:
            print(f"[ERROR] Failed to initialize RSS adapter: {e}")
            stats['errors'] += 1
            return stats
        
        # Run crawl
        crawl_stats = crawler.crawl_with_retry(since=since, skip_summary=not summarize)
        stats.update(crawl_stats)
        
        print(f"[DONE] Fetched: {stats['fetched']}, Saved: {stats['saved']}, "
              f"Duplicates: {stats['duplicates']}, Errors: {stats['errors']}")
        
        if stats['errors'] > 0:
            print(f"[WARN] {stats['errors']} errors occurred")
        
    except Exception as e:
        print(f"[ERROR] Failed to crawl {source.name}: {e}")
        import traceback
        traceback.print_exc()
        stats['errors'] += 1
    
    return stats


def run_source_in_subprocess(source: NewsSource, args) -> Dict:
    """
    Run a single source crawl in a child Python process.
    This isolates memory usage so RSS parsing/LLM work is released per source.
    """
    stats = {
        'source_name': source.name,
        'source_type': source.source_type,
        'fetched': 0,
        'saved': 0,
        'duplicates': 0,
        'errors': 0,
        'summarized': 0
    }

    temp_stats_file = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f"aihub_source_{source.id}_", suffix=".json", delete=False) as tf:
            temp_stats_file = tf.name

        cmd = [
            sys.executable,
            "-u",
            "-P",
            "-m",
            "BogoBots.crawlers.scripts.run_news_crawl",
            "--source-id",
            str(source.id),
            "--days",
            str(args.days),
            "--stats-file",
            temp_stats_file,
        ]
        if args.summarize:
            cmd.append("--summarize")
        if args.dry_run:
            cmd.append("--dry-run")
        if args.verbose:
            cmd.append("--verbose")

        print(f"\n[ISOLATED] Launching subprocess for source #{source.id} '{source.name}'")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if proc.stdout:
            for line in proc.stdout:
                print(f"[source:{source.id}] {line}", end="")
        return_code = proc.wait()

        if temp_stats_file and os.path.exists(temp_stats_file):
            with open(temp_stats_file, "r", encoding="utf-8") as f:
                child_stats = json.load(f)
                if isinstance(child_stats, dict):
                    stats.update(child_stats)

        if return_code != 0 and stats.get("errors", 0) == 0:
            stats["errors"] = 1

    except Exception as e:
        print(f"[ERROR] Subprocess crawl failed for source #{source.id} '{source.name}': {e}")
        stats["errors"] += 1
    finally:
        if temp_stats_file and os.path.exists(temp_stats_file):
            try:
                os.remove(temp_stats_file)
            except Exception:
                pass

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Crawl AI news sources and save to database'
    )
    parser.add_argument(
        '--source-id', '-s',
        type=int,
        help='Specific source ID to crawl (default: all active)'
    )
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=1,
        help='Lookback period in days (default: 1)'
    )
    parser.add_argument(
        '--summarize',
        action='store_true',
        help='Generate LLM summaries for new items'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run - fetch but do not save to database'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--isolated-sources',
        action='store_true',
        help='Run each source in a separate Python process to reduce peak memory'
    )
    parser.add_argument(
        '--stats-file',
        type=str,
        help='Internal use: write run stats as JSON to this file'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("BogoBots AI Hub - News Crawler")
    print("=" * 60)
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(
        f"Options: days={args.days}, summarize={args.summarize}, dry_run={args.dry_run}, "
        f"isolated_sources={args.isolated_sources}"
    )
    
    # Calculate lookback period, set hour/minute/second/microsecond to 00:00
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get sources to crawl
    if args.source_id:
        source = NewsSourceService.get_source_by_id(args.source_id)
        if not source:
            print(f"[ERROR] Source with ID {args.source_id} not found")
            sys.exit(1)
        sources = [source]
    else:
        sources = NewsSourceService.get_active_sources()
    
    if not sources:
        print("[WARN] No sources configured or active")
        sys.exit(0)
    
    print(f"\nFound {len(sources)} source(s) to crawl")
    
    # Run crawl for each source
    all_stats = []
    if args.isolated_sources and not args.source_id:
        print("[MODE] Isolated per-source subprocess mode enabled")
        for source in sources:
            stats = run_source_in_subprocess(source, args)
            all_stats.append(stats)
    else:
        for source in sources:
            stats = run_crawl_for_source(
                source, since, 
                summarize=args.summarize,
                dry_run=args.dry_run
            )
            all_stats.append(stats)
    
    # Summary
    print("\n" + "=" * 60)
    print("CRAWL SUMMARY")
    print("=" * 60)
    
    total_fetched = sum(s['fetched'] for s in all_stats)
    total_saved = sum(s['saved'] for s in all_stats)
    total_dupes = sum(s['duplicates'] for s in all_stats)
    total_errors = sum(s['errors'] for s in all_stats)
    
    print(f"Total fetched:   {total_fetched}")
    print(f"Total saved:     {total_saved}")
    print(f"Total dupes:     {total_dupes}")
    print(f"Total errors:    {total_errors}")
    
    # Per-source breakdown
    print("\nPer-source breakdown:")
    for stats in all_stats:
        status = "✓" if stats['errors'] == 0 else "✗"
        print(f"  {status} {stats['source_name']}: "
              f"{stats['saved']} saved, {stats['duplicates']} dupes")

    if args.stats_file:
        try:
            with open(args.stats_file, "w", encoding="utf-8") as f:
                if all_stats:
                    if len(all_stats) == 1:
                        json.dump(all_stats[0], f, ensure_ascii=False)
                    else:
                        json.dump(
                            {
                                "source_name": "all_sources",
                                "source_type": "mixed",
                                "fetched": total_fetched,
                                "saved": total_saved,
                                "duplicates": total_dupes,
                                "errors": total_errors,
                                "summarized": sum(s.get("summarized", 0) for s in all_stats),
                            },
                            f,
                            ensure_ascii=False,
                        )
                else:
                    json.dump(
                        {
                            "source_name": "none",
                            "source_type": "none",
                            "fetched": 0,
                            "saved": 0,
                            "duplicates": 0,
                            "errors": 0,
                            "summarized": 0,
                        },
                        f,
                        ensure_ascii=False,
                    )
        except Exception as e:
            print(f"[WARN] Failed to write stats file '{args.stats_file}': {e}")
    
    print(f"\nFinished at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Exit with error code if any errors
    if total_errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
