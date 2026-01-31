"""
Storage management for items and deduplication index.

Data format:
- data/items/YYYY-MM.jsonl: Monthly JSONL files (append-only)
- data/index.json: item_id -> {first_seen, source, title}
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.utils import (
    ITEMS_DIR,
    INDEX_FILE,
    BASE_RELIABILITY_SCORES,
    INGEST_VERSION,
    get_jst_now,
    get_jst_month,
    clamp,
)
from scripts.llm_client import EnrichedItem

logger = logging.getLogger(__name__)


def ensure_directories() -> None:
    """Ensure data directories exist."""
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)


def load_index() -> dict[str, dict]:
    """
    Load deduplication index.

    Returns:
        Dict mapping item_id (URL hash) to metadata
    """
    if not INDEX_FILE.exists():
        return {}

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load index, starting fresh: {e}")
        return {}


def save_index(index: dict[str, dict]) -> None:
    """
    Save deduplication index.

    Args:
        index: The index dict to save
    """
    ensure_directories()
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info(f"Index saved: {len(index)} entries")


def add_to_index(
    index: dict[str, dict],
    item_id: str,
    source_name: str,
    title: str,
) -> None:
    """
    Add entry to index.

    Args:
        index: The index dict (modified in place)
        item_id: SHA256 hash of normalized URL
        source_name: Name of the source
        title: Article title
    """
    index[item_id] = {
        "first_seen": get_jst_now().isoformat(),
        "source": source_name,
        "title": title[:100],  # Truncate for index storage
    }


def get_jsonl_path(month: str | None = None) -> Path:
    """
    Get JSONL file path for the given month.

    Args:
        month: Month string (YYYY-MM), defaults to current month

    Returns:
        Path to JSONL file
    """
    if month is None:
        month = get_jst_month()
    return ITEMS_DIR / f"{month}.jsonl"


def append_item(item: dict, month: str | None = None) -> None:
    """
    Append a processed item to the monthly JSONL file.

    Args:
        item: The complete item record
        month: Optional month string (YYYY-MM)
    """
    ensure_directories()
    jsonl_path = get_jsonl_path(month)

    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_items_for_month(month: str) -> list[dict]:
    """
    Load all items for a specific month.

    Args:
        month: Month string (YYYY-MM)

    Returns:
        List of item records
    """
    jsonl_path = get_jsonl_path(month)

    if not jsonl_path.exists():
        return []

    items = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed line {line_num} in {jsonl_path}")

    return items


def build_complete_item(
    url: str,
    url_normalized: str,
    item_id: str,
    source_group: str,
    source_key: str,
    source_name: str,
    source_type: str,
    publisher: str,
    rss_title: str,
    rss_pub_date: str | None,
    language: str,
    content_length: int,
    enrichment: EnrichedItem,
) -> dict[str, Any]:
    """
    Build complete item record for storage.

    Args:
        url: Original URL
        url_normalized: Normalized URL
        item_id: SHA256 of normalized URL
        source_group: "high" or "trend"
        source_key: Source key from config
        source_name: Source name
        source_type: Source type (ministry, consulting, etc.)
        publisher: Publisher name
        rss_title: Title from RSS feed
        rss_pub_date: Published date from RSS
        language: Language from source config
        content_length: Length of extracted content
        enrichment: LLM enrichment result

    Returns:
        Complete item record dict
    """
    # Calculate final reliability score
    base_score = BASE_RELIABILITY_SCORES.get(source_type, 40)
    final_score = clamp(base_score + enrichment.reliability_score_delta, 0, 100)

    now = get_jst_now()

    return {
        # Identification
        "item_id": item_id,
        "url": url,
        "url_normalized": url_normalized,
        # Source metadata
        "source_group": source_group,
        "source_key": source_key,
        "source_name": source_name,
        "source_type": source_type,
        "publisher": publisher,
        # Original RSS data
        "rss_title": rss_title,
        "rss_pub_date": rss_pub_date,
        # Enriched data
        "title": enrichment.title,
        "summary": enrichment.summary,
        "key_points": enrichment.key_points,
        "themes": enrichment.themes,
        "tags": enrichment.tags,
        "language": enrichment.language,
        "published_at": enrichment.published_at,
        # Reliability
        "reliability_score": final_score,
        "reliability_base": base_score,
        "reliability_delta": enrichment.reliability_score_delta,
        "reliability_reason": enrichment.reliability_reason,
        # Metadata
        "content_length": content_length,
        "observed_at": now.isoformat(),
        "retrieved_at": now.isoformat(),
        "ingest_version": INGEST_VERSION,
    }


def get_items_for_date(date_str: str) -> tuple[list[dict], list[dict]]:
    """
    Get items collected on a specific date.

    Args:
        date_str: Date string (YYYY-MM-DD)

    Returns:
        Tuple of (high_items, trend_items)
    """
    # Determine the month from date
    month = date_str[:7]  # YYYY-MM
    items = load_items_for_month(month)

    high_items = []
    trend_items = []

    for item in items:
        # Check if observed on this date
        observed_at = item.get("observed_at", "")
        if observed_at.startswith(date_str):
            if item.get("source_group") == "high":
                high_items.append(item)
            else:
                trend_items.append(item)

    return high_items, trend_items
