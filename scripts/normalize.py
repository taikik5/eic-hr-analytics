"""
URL normalization and hashing for deduplication.

Provides functions to:
- Normalize URLs (remove tracking params, fragments, etc.)
- Generate SHA256 hash as item_id
"""

import hashlib
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


# Tracking parameters to remove
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "ref",
    "source",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
    "yclid",
    "twclid",
}


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent deduplication.

    Rules:
    1. Convert scheme and host to lowercase
    2. Remove www. prefix
    3. Remove trailing slash (except root)
    4. Remove tracking parameters (utm_*, fbclid, etc.)
    5. Sort remaining query parameters
    6. Remove fragment

    Args:
        url: The original URL

    Returns:
        Normalized URL string
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove www. prefix for consistency
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Normalize path: remove trailing slash except for root
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not path:
        path = "/"

    # Filter out tracking parameters
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = {}
    for k, v in query_params.items():
        if k.lower() not in TRACKING_PARAMS:
            filtered_params[k] = v

    # Sort and rebuild query string
    if filtered_params:
        sorted_items = sorted(filtered_params.items())
        sorted_query = urlencode(sorted_items, doseq=True)
    else:
        sorted_query = ""

    # Rebuild URL without fragment
    normalized = urlunparse(
        (
            scheme,
            netloc,
            path,
            "",  # params
            sorted_query,
            "",  # fragment
        )
    )

    return normalized


def compute_item_id(url: str) -> str:
    """
    Compute SHA256 hash of normalized URL as item_id.

    Args:
        url: The original URL

    Returns:
        64-character hex string (SHA256 hash)
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_duplicate(url: str, index: dict) -> bool:
    """
    Check if URL already exists in the index.

    Args:
        url: The URL to check
        index: The deduplication index (item_id -> metadata)

    Returns:
        True if duplicate, False otherwise
    """
    item_id = compute_item_id(url)
    return item_id in index
