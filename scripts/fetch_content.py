"""
Content fetching and extraction using trafilatura.

Fetches HTML from URLs and extracts main article text.
"""

import logging

import requests
import trafilatura

from scripts.utils import (
    CONTENT_FETCH_TIMEOUT,
    CONTENT_MAX_CHARS,
    CONTENT_MIN_CHARS,
    retry_with_backoff,
    truncate_text,
)

logger = logging.getLogger(__name__)

# User-Agent for requests
USER_AGENT = "Mozilla/5.0 (compatible; EIC-Bot/1.0; +https://github.com/eic-hr-analytics)"

# Request headers
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}


@retry_with_backoff(max_retries=2, base_delay=2.0, exceptions=(requests.RequestException,))
def fetch_html(url: str) -> str | None:
    """
    Fetch HTML content from URL.

    Args:
        url: The URL to fetch

    Returns:
        HTML content as string, or None on failure
    """
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=CONTENT_FETCH_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower() and "application/xhtml" not in content_type.lower():
            logger.warning(f"Non-HTML content type: {content_type} for {url[:50]}")
            # Still try to process it

        return response.text

    except requests.Timeout:
        logger.warning(f"Timeout fetching {url[:50]}")
        return None
    except requests.RequestException as e:
        logger.warning(f"Request error for {url[:50]}: {e}")
        raise  # Re-raise for retry decorator
    except Exception as e:
        logger.error(f"Unexpected error fetching {url[:50]}: {e}")
        return None


def extract_content(html: str) -> str | None:
    """
    Extract main content from HTML using trafilatura.

    Args:
        html: Raw HTML content

    Returns:
        Extracted text content, or None if extraction fails
    """
    try:
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
        )

        if not content:
            return None

        # Clean up whitespace
        content = " ".join(content.split())

        return content

    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return None


def fetch_and_extract(url: str) -> str | None:
    """
    Fetch URL and extract main content.

    Args:
        url: The article URL

    Returns:
        Extracted and trimmed text content, or None on failure
    """
    # Fetch HTML
    html = fetch_html(url)
    if not html:
        logger.warning(f"No HTML content from {url[:50]}")
        return None

    # Extract content
    content = extract_content(html)
    if not content:
        logger.warning(f"No content extracted from {url[:50]}")
        return None

    # Check minimum length
    if len(content) < CONTENT_MIN_CHARS:
        logger.warning(f"Content too short ({len(content)} chars) from {url[:50]}")
        return None

    # Truncate to max length
    content = truncate_text(content, CONTENT_MAX_CHARS)

    logger.debug(f"Extracted {len(content)} chars from {url[:50]}")
    return content
