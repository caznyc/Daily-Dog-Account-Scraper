#!/usr/bin/env python3
"""
TikTok Dog Account Growth Intelligence Scraper

Scrapes TikTok for dog content repost accounts, analyzes their growth
patterns, and outputs a ranked CSV + HTML dashboard.

Usage:
    python main.py                          # Run with default keywords
    python main.py --keywords "funny dogs" "cute puppies"
    python main.py --headless false         # Run with visible browser
    python main.py --max-accounts 20        # Limit total accounts scraped
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import config
from scraper import run_scraper
from scorer import score_accounts
from output_gen import write_csv, write_html


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="TikTok Dog Account Growth Intelligence Scraper",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        help="Custom search keywords (default: uses config.py list)",
    )
    parser.add_argument(
        "--max-accounts",
        type=int,
        default=None,
        help="Maximum number of accounts to scrape per keyword",
    )
    parser.add_argument(
        "--headless",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Run browser in headless mode (default: true)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for CSV and HTML files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Apply CLI overrides to config
    config.HEADLESS = args.headless.lower() == "true"
    if args.max_accounts:
        config.ACCOUNTS_PER_KEYWORD = args.max_accounts

    output_dir = Path(args.output_dir)
    csv_path = str(output_dir / "dog_accounts_ranked.csv")
    html_path = str(output_dir / "dashboard.html")

    logger.info("=" * 60)
    logger.info("  TikTok Dog Account Growth Intelligence Scraper")
    logger.info("=" * 60)

    keywords = args.keywords or config.SEARCH_KEYWORDS
    logger.info(f"Keywords: {', '.join(keywords)}")
    logger.info(f"Headless: {config.HEADLESS}")
    logger.info(f"Max accounts/keyword: {config.ACCOUNTS_PER_KEYWORD}")
    logger.info("")

    # Phase 1 & 2: Scrape
    accounts = await run_scraper(keywords)

    if not accounts:
        logger.error("No accounts were scraped. This may be due to:")
        logger.error("  - TikTok blocking automated access (try --headless false)")
        logger.error("  - Network issues")
        logger.error("  - CAPTCHA challenges")
        sys.exit(1)

    # Phase 3: Score and rank
    logger.info("\n=== Phase 3: Scoring and ranking ===")
    scored = score_accounts(accounts)

    # Phase 4: Output
    logger.info("\n=== Phase 4: Generating output ===")
    write_csv(scored, csv_path)
    write_html(scored, html_path)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("  COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Accounts scraped: {len(scored)}")
    hp = [s for s in scored if s["high_priority"]]
    if hp:
        logger.info(f"  HIGH PRIORITY accounts: {len(hp)}")
        for h in hp:
            logger.info(f"    @{h['username']} - {h['followers']:,} followers, score: {h['composite_score']}")
    logger.info(f"\n  CSV:  {csv_path}")
    logger.info(f"  HTML: {html_path}")

    # Print top 5
    logger.info("\n  Top 5 accounts:")
    for s in scored[:5]:
        flag = " [HIGH PRIORITY]" if s["high_priority"] else ""
        logger.info(
            f"    #{s['rank']} @{s['username']} "
            f"- {s['followers']:,} followers, "
            f"{s['virality_pct']}% virality, "
            f"score: {s['composite_score']}{flag}"
        )


if __name__ == "__main__":
    asyncio.run(main())
