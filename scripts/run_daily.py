"""
Daily collection orchestrator.

Runs the complete EIC pipeline:
1. Collect candidates from RSS feeds
2. Normalize URLs and filter duplicates
3. Fetch content via trafilatura
4. Analyze with LLM (OpenAI)
5. Store in JSONL + update index
6. Post to GitHub Discussions
7. Send Slack notification
"""

import argparse
import logging
import sys
from typing import NamedTuple

from scripts.utils import (
    setup_logging,
    get_jst_today,
    OPENAI_API_KEY,
    GITHUB_TOKEN,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
    MAX_HIGH_TRUST_ITEMS,
    MAX_TREND_ITEMS,
)
from scripts.collect_candidates import collect_from_sources
from scripts.normalize import compute_item_id, normalize_url, is_duplicate
from scripts.fetch_content import fetch_and_extract
from scripts.llm_client import LLMClient
from scripts.store import (
    load_index,
    save_index,
    add_to_index,
    append_item,
    build_complete_item,
    get_items_for_date,
)
from scripts.github_discussions import (
    ensure_daily_discussion,
    upsert_list_comment,
)
from scripts.slack_notify import send_daily_notification, send_no_updates_notification

logger = logging.getLogger(__name__)


class ProcessingStats(NamedTuple):
    """Statistics from processing a source group."""

    processed: list[dict]
    duplicates: int
    errors: list[str]


def validate_config() -> list[str]:
    """
    Validate required configuration.

    Returns:
        List of error messages (empty if all OK)
    """
    errors = []

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is not set")

    if not GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN is not set")

    return errors


def process_source_group(
    source_group: str,
    max_items: int,
    index: dict,
    llm: LLMClient,
) -> ProcessingStats:
    """
    Process one source group (high or trend).

    Args:
        source_group: "high" or "trend"
        max_items: Maximum items to process
        index: Deduplication index
        llm: LLM client instance

    Returns:
        ProcessingStats with processed items, duplicate count, and errors
    """
    processed = []
    duplicates = 0
    errors = []

    # Collect candidates from RSS
    candidates = collect_from_sources(source_group)
    logger.info(f"Collected {len(candidates)} candidates from {source_group} sources")

    for candidate in candidates:
        # Check if we've reached the limit
        if len(processed) >= max_items:
            logger.info(f"Reached max items ({max_items}) for {source_group}")
            break

        url = candidate["url"]

        # Normalize URL and compute item_id
        url_normalized = normalize_url(url)
        item_id = compute_item_id(url)

        # Skip duplicates
        if is_duplicate(url, index):
            duplicates += 1
            logger.debug(f"Skipping duplicate: {url[:60]}...")
            continue

        try:
            # Fetch and extract content
            content = fetch_and_extract(url)
            content_length = len(content) if content else 0

            if not content:
                logger.warning(f"No content extracted: {url[:60]}...")
                # Continue with empty content (LLM will handle it)
                content = ""

            # Analyze with LLM
            enrichment = llm.analyze_article(
                content=content,
                source_name=candidate["source_name"],
                source_type=candidate["source_type"],
                publisher=candidate["publisher"],
                original_title=candidate["title"],
                language=candidate["language"],
            )

            if not enrichment:
                error_msg = f"LLM analysis failed: {url[:50]}"
                errors.append(error_msg)
                logger.warning(error_msg)
                continue

            # Build complete item
            item = build_complete_item(
                url=url,
                url_normalized=url_normalized,
                item_id=item_id,
                source_group=source_group,
                source_key=candidate["source_key"],
                source_name=candidate["source_name"],
                source_type=candidate["source_type"],
                publisher=candidate["publisher"],
                rss_title=candidate["title"],
                rss_pub_date=candidate["pub_date"],
                language=candidate["language"],
                content_length=content_length,
                enrichment=enrichment,
            )

            # Store item
            append_item(item)
            add_to_index(index, item_id, candidate["source_name"], item["title"])

            processed.append(item)
            logger.info(f"Processed: {item['title'][:50]}...")

        except Exception as e:
            error_msg = f"Error processing {url[:40]}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            # Continue with next item (partial failure OK)

    return ProcessingStats(
        processed=processed,
        duplicates=duplicates,
        errors=errors,
    )


def select_highlights(
    high_items: list[dict],
    trend_items: list[dict],
    max_count: int = 5,
) -> list[dict]:
    """
    Select top items for highlights.

    Prioritizes by reliability_score, mixing high and trend.

    Args:
        high_items: High trust items
        trend_items: Trend items
        max_count: Maximum highlights to select

    Returns:
        List of highlight items
    """
    # Combine and sort by reliability
    all_items = high_items + trend_items
    sorted_items = sorted(
        all_items,
        key=lambda x: x.get("reliability_score", 0),
        reverse=True,
    )

    # Take top items, ensuring mix if possible
    highlights = []
    high_count = 0
    trend_count = 0
    max_per_group = (max_count + 1) // 2  # At least half from each group

    for item in sorted_items:
        if len(highlights) >= max_count:
            break

        is_high = item.get("source_group") == "high"

        if is_high and high_count < max_per_group:
            highlights.append(item)
            high_count += 1
        elif not is_high and trend_count < max_per_group:
            highlights.append(item)
            trend_count += 1
        elif len(highlights) < max_count:
            # Fill remaining slots
            highlights.append(item)

    return highlights


def run_daily(date_override: str | None = None) -> int:
    """
    Execute daily collection pipeline.

    Args:
        date_override: Optional date string (YYYY-MM-DD) for testing

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("EIC Daily Collection Started")
    logger.info("=" * 60)

    # Validate configuration
    config_errors = validate_config()
    if config_errors:
        for error in config_errors:
            logger.error(f"Config error: {error}")
        return 1

    # Determine date (JST)
    date_str = date_override or get_jst_today()
    logger.info(f"Processing date: {date_str}")

    # Initialize
    index = load_index()
    logger.info(f"Loaded index: {len(index)} existing entries")

    try:
        llm = LLMClient()
        logger.info(f"LLM client initialized (model: {llm.model})")
    except Exception as e:
        logger.error(f"Failed to initialize LLM client: {e}")
        return 1

    all_errors = []

    # Process HIGH TRUST sources
    logger.info("-" * 40)
    logger.info("Processing HIGH TRUST sources")
    high_stats = process_source_group("high", MAX_HIGH_TRUST_ITEMS, index, llm)
    all_errors.extend(high_stats.errors)
    logger.info(
        f"HIGH: processed={len(high_stats.processed)}, "
        f"duplicates={high_stats.duplicates}, "
        f"errors={len(high_stats.errors)}"
    )

    # Process TREND sources
    logger.info("-" * 40)
    logger.info("Processing TREND sources")
    trend_stats = process_source_group("trend", MAX_TREND_ITEMS, index, llm)
    all_errors.extend(trend_stats.errors)
    logger.info(
        f"TREND: processed={len(trend_stats.processed)}, "
        f"duplicates={trend_stats.duplicates}, "
        f"errors={len(trend_stats.errors)}"
    )

    # Save index
    save_index(index)

    # Prepare stats for Discussion
    stats = {
        "high_count": len(high_stats.processed),
        "trend_count": len(trend_stats.processed),
        "duplicates": high_stats.duplicates + trend_stats.duplicates,
        "errors": all_errors[:10],  # Limit errors shown
    }

    # Get all items for this date (including any from previous runs)
    high_items, trend_items = get_items_for_date(date_str)
    logger.info(f"Total items for {date_str}: HIGH={len(high_items)}, TREND={len(trend_items)}")

    # GitHub Discussions
    discussion_url = None
    if high_items or trend_items:
        logger.info("-" * 40)
        logger.info("Updating GitHub Discussions")
        try:
            discussion = ensure_daily_discussion(date_str, stats)
            discussion_url = discussion["url"]

            # Update HIGH list comment
            upsert_list_comment(
                discussion["id"],
                "HIGH",
                date_str,
                high_items,
            )

            # Update TREND list comment
            upsert_list_comment(
                discussion["id"],
                "TREND",
                date_str,
                trend_items,
            )

            logger.info(f"Discussion updated: {discussion_url}")

        except Exception as e:
            logger.error(f"GitHub Discussions error: {e}")
            all_errors.append(f"Discussions: {str(e)}")
    else:
        logger.info("No new items collected, skipping Discussions")

    # Slack notification
    if high_items or trend_items:
        # Send regular notification with highlights
        logger.info("-" * 40)
        logger.info("Sending Slack notification")

        highlights = select_highlights(high_items, trend_items, max_count=5)

        # Fallback URL if Discussion creation failed
        fallback_url = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
        notification_url = discussion_url or fallback_url

        try:
            send_daily_notification(
                date_str=date_str,
                discussion_url=notification_url,
                high_count=len(high_items),
                trend_count=len(trend_items),
                highlights=highlights,
                discussion_failed=(discussion_url is None),
            )
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            # Don't fail the job for Slack errors
    else:
        # No new articles - send "no updates" notification to Slack only
        logger.info("-" * 40)
        logger.info("Sending 'no updates' Slack notification")
        try:
            send_no_updates_notification(date_str)
        except Exception as e:
            logger.error(f"Slack notification error: {e}")

    # Summary
    logger.info("=" * 60)
    logger.info("EIC Daily Collection Complete")
    logger.info(f"  HIGH items: {len(high_items)}")
    logger.info(f"  TREND items: {len(trend_items)}")
    logger.info(f"  Duplicates skipped: {stats['duplicates']}")
    logger.info(f"  Errors: {len(all_errors)}")
    if discussion_url:
        logger.info(f"  Discussion: {discussion_url}")
    logger.info("=" * 60)

    # Return success even with partial errors
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="EIC Daily Collection Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.run_daily
  python -m scripts.run_daily --date 2024-01-15
        """,
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override date (YYYY-MM-DD format, for testing)",
    )

    args = parser.parse_args()
    return run_daily(args.date)


if __name__ == "__main__":
    sys.exit(main())
