"""
RSS feed collection from configured sources.

Collects candidate URLs from High Trust and Trend sources.
"""

import logging
from datetime import datetime, timedelta
from typing import TypedDict
from zoneinfo import ZoneInfo

import feedparser

from scripts.utils import (
    EIC_TIMEZONE,
    load_sources_config,
    get_collection_window,
)

logger = logging.getLogger(__name__)


class Candidate(TypedDict):
    """Candidate article from RSS feed."""

    url: str
    title: str
    pub_date: str | None
    source_key: str
    source_name: str
    source_type: str
    publisher: str
    language: str


def parse_pub_date(entry: feedparser.FeedParserDict) -> datetime | None:
    """
    Parse publication date from RSS entry.

    Args:
        entry: feedparser entry object

    Returns:
        datetime object or None if parsing fails
    """
    # Try published_parsed first
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=ZoneInfo("UTC"))
        except (TypeError, ValueError):
            pass

    # Try updated_parsed
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=ZoneInfo("UTC"))
        except (TypeError, ValueError):
            pass

    return None


def collect_from_single_source(source: dict) -> list[Candidate]:
    """
    Collect candidates from a single RSS source.

    Args:
        source: Source configuration dict

    Returns:
        List of Candidate items
    """
    candidates = []
    url = source.get("url", "")

    if not url:
        logger.warning(f"Source {source.get('key')} has no URL")
        return candidates

    try:
        # Parse RSS feed
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse feed: {source.get('name')} - {feed.bozo_exception}")
            return candidates

        # Get collection window for filtering
        window_start, window_end = get_collection_window()

        for entry in feed.entries[:30]:  # Limit per source
            # Get entry URL
            entry_url = getattr(entry, "link", None)
            if not entry_url:
                continue

            # Get entry title
            entry_title = getattr(entry, "title", "")
            if not entry_title:
                entry_title = "(No Title)"

            # Parse publication date
            pub_datetime = parse_pub_date(entry)

            # Format pub_date as ISO string
            pub_date_str = None
            if pub_datetime:
                pub_date_str = pub_datetime.isoformat()

            candidates.append(
                Candidate(
                    url=entry_url,
                    title=entry_title,
                    pub_date=pub_date_str,
                    source_key=source.get("key", ""),
                    source_name=source.get("name", ""),
                    source_type=source.get("source_type", "other"),
                    publisher=source.get("publisher", ""),
                    language=source.get("language", "unknown"),
                )
            )

        logger.info(f"Collected {len(candidates)} candidates from {source.get('name')}")

    except Exception as e:
        logger.error(f"Error collecting from {source.get('name')}: {e}")

    return candidates


def collect_from_sources(source_group: str) -> list[Candidate]:
    """
    Collect candidates from all sources of a given group.

    Args:
        source_group: "high" or "trend"

    Returns:
        List of all Candidate items, sorted by pub_date (newest first)
    """
    sources = load_sources_config(source_group)
    all_candidates = []

    logger.info(f"Collecting from {len(sources)} {source_group} sources...")

    for source in sources:
        candidates = collect_from_single_source(source)
        all_candidates.extend(candidates)

    # Sort by publication date (newest first)
    # Items without pub_date go to the end
    all_candidates.sort(
        key=lambda x: x["pub_date"] or "0000-00-00",
        reverse=True,
    )

    logger.info(f"Total {source_group} candidates: {len(all_candidates)}")
    return all_candidates
