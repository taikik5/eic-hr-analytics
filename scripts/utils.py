"""
Shared utilities for EIC.

Provides:
- Configuration loading
- Date/time utilities
- Logging setup
- Retry decorator
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
ITEMS_DIR = DATA_DIR / "items"
INDEX_FILE = DATA_DIR / "index.json"

# Environment variables with defaults
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
EIC_TIMEZONE = os.getenv("EIC_TIMEZONE", "Asia/Tokyo")

# Collection limits
MAX_HIGH_TRUST_ITEMS = 20
MAX_TREND_ITEMS = 20
CONTENT_FETCH_TIMEOUT = 20
CONTENT_MAX_CHARS = 12000
CONTENT_MIN_CHARS = 100

# Base reliability scores by source_type
BASE_RELIABILITY_SCORES = {
    "ministry": 80,
    "intl_org": 80,
    "consulting": 70,
    "paper": 70,
    "news": 60,
    "tech": 50,
    "blog": 50,
    "other": 40,
}

# Ingest version for tracking schema changes
INGEST_VERSION = "1.0.0"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Root logger
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("eic")


def get_jst_now() -> datetime:
    """Get current datetime in JST."""
    return datetime.now(ZoneInfo(EIC_TIMEZONE))


def get_jst_today() -> str:
    """Get today's date string in JST (YYYY-MM-DD)."""
    return get_jst_now().strftime("%Y-%m-%d")


def get_jst_month() -> str:
    """Get current month string in JST (YYYY-MM)."""
    return get_jst_now().strftime("%Y-%m")


def get_collection_window() -> tuple[datetime, datetime]:
    """
    Get the collection window (previous day in JST).

    Returns:
        Tuple of (start_datetime, end_datetime) in UTC
    """
    jst = ZoneInfo(EIC_TIMEZONE)
    now = datetime.now(jst)

    # Yesterday 00:00:00 JST to today 00:00:00 JST
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    return yesterday_start, today_start


def load_yaml_config(filename: str) -> dict:
    """
    Load YAML configuration file.

    Args:
        filename: Config filename (e.g., "themes.yaml")

    Returns:
        Parsed YAML content as dict
    """
    config_path = CONFIG_DIR / filename
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json_config(filename: str) -> dict:
    """
    Load JSON configuration file.

    Args:
        filename: Config filename (e.g., "categories.json")

    Returns:
        Parsed JSON content as dict
    """
    config_path = CONFIG_DIR / filename
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_themes_config() -> dict:
    """Load themes configuration."""
    return load_yaml_config("themes.yaml")


def load_sources_config(source_type: str) -> list[dict]:
    """
    Load sources configuration.

    Args:
        source_type: "high" or "trend"

    Returns:
        List of source definitions
    """
    config = load_yaml_config(f"sources_{source_type}.yaml")
    return config.get("sources", [])


def get_discussions_category_id() -> str:
    """Get Discussions category ID from config."""
    config = load_json_config("categories.json")
    return config.get("daily_digest_category_id", "")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logging.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
            raise last_exception

        return wrapper

    return decorator


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(value, max_val))


def truncate_text(text: str, max_chars: int) -> str:
    """
    Truncate text to maximum characters.

    Args:
        text: Input text
        max_chars: Maximum character count

    Returns:
        Truncated text
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
