"""
GitHub Discussions management via GraphQL API.

Handles:
1. Finding/creating daily discussion threads
2. Creating/updating comments with markers for idempotency
"""

import logging
from typing import TypedDict

import requests

from scripts.utils import (
    GITHUB_TOKEN,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
    get_discussions_category_id,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


class DiscussionInfo(TypedDict):
    """Discussion information."""

    id: str
    number: int
    url: str


class CommentInfo(TypedDict):
    """Comment information."""

    id: str
    body: str


def _get_headers() -> dict[str, str]:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    }


@retry_with_backoff(max_retries=3, base_delay=2.0, exceptions=(requests.RequestException,))
def _graphql_request(query: str, variables: dict | None = None) -> dict:
    """
    Execute GraphQL request against GitHub API.

    Args:
        query: GraphQL query or mutation
        variables: Query variables

    Returns:
        Response data dict

    Raises:
        Exception: If GraphQL errors occur
    """
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(
        GITHUB_GRAPHQL_URL,
        json=payload,
        headers=_get_headers(),
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if "errors" in result:
        error_messages = [e.get("message", str(e)) for e in result["errors"]]
        raise Exception(f"GraphQL errors: {'; '.join(error_messages)}")

    return result.get("data", {})


def get_repository_id() -> str:
    """
    Get the repository node ID.

    Returns:
        Repository node ID
    """
    query = """
    query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
            id
        }
    }
    """
    data = _graphql_request(
        query,
        {"owner": GITHUB_REPO_OWNER, "name": GITHUB_REPO_NAME},
    )
    return data["repository"]["id"]


def find_daily_discussion(date_str: str) -> DiscussionInfo | None:
    """
    Find existing discussion for the given date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        DiscussionInfo or None if not found
    """
    title_pattern = f"[EIC][Daily] {date_str} (JST)"

    query = """
    query($owner: String!, $name: String!, $first: Int!) {
        repository(owner: $owner, name: $name) {
            discussions(first: $first, orderBy: {field: CREATED_AT, direction: DESC}) {
                nodes {
                    id
                    number
                    title
                    url
                }
            }
        }
    }
    """

    data = _graphql_request(
        query,
        {
            "owner": GITHUB_REPO_OWNER,
            "name": GITHUB_REPO_NAME,
            "first": 50,  # Check recent discussions
        },
    )

    for discussion in data["repository"]["discussions"]["nodes"]:
        if discussion["title"] == title_pattern:
            return DiscussionInfo(
                id=discussion["id"],
                number=discussion["number"],
                url=discussion["url"],
            )

    return None


def create_daily_discussion(date_str: str, stats: dict | None = None) -> DiscussionInfo:
    """
    Create a new daily discussion thread.

    Args:
        date_str: Date in YYYY-MM-DD format (JST)
        stats: Optional collection statistics

    Returns:
        DiscussionInfo with the created discussion
    """
    repo_id = get_repository_id()
    category_id = get_discussions_category_id()

    if not category_id:
        raise ValueError("Discussions category ID not configured in config/categories.json")

    title = f"[EIC][Daily] {date_str} (JST)"

    # Build body
    stats = stats or {}
    high_count = stats.get("high_count", 0)
    trend_count = stats.get("trend_count", 0)
    duplicates = stats.get("duplicates", 0)
    errors = stats.get("errors", [])

    body_lines = [
        f"# EIC Daily Insights - {date_str}",
        "",
        "HR関連の外部情報を自動収集しました。",
        "",
        "## 収集サマリ",
        "",
        f"- **High Trust**: {high_count}件",
        f"- **Trend**: {trend_count}件",
        f"- **重複スキップ**: {duplicates}件",
    ]

    if errors:
        body_lines.extend([
            "",
            "## エラー",
            "",
        ])
        for error in errors[:10]:  # Limit to 10 errors
            body_lines.append(f"- {error}")

    body_lines.extend([
        "",
        "---",
        "",
        "**HIGH TRUST**: 省庁・研究機関・大手メディアからの記事",
        "",
        "**TREND**: Zenn/Qiita等トレンド系メディアからの記事",
        "",
        "---",
        "",
        f"📁 データ: `data/items/{date_str[:7]}.jsonl`",
    ])

    body = "\n".join(body_lines)

    mutation = """
    mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
        createDiscussion(input: {
            repositoryId: $repositoryId
            categoryId: $categoryId
            title: $title
            body: $body
        }) {
            discussion {
                id
                number
                url
            }
        }
    }
    """

    data = _graphql_request(
        mutation,
        {
            "repositoryId": repo_id,
            "categoryId": category_id,
            "title": title,
            "body": body,
        },
    )

    discussion = data["createDiscussion"]["discussion"]
    logger.info(f"Created discussion: {discussion['url']}")

    return DiscussionInfo(
        id=discussion["id"],
        number=discussion["number"],
        url=discussion["url"],
    )


def find_comment_by_marker(discussion_id: str, marker: str) -> CommentInfo | None:
    """
    Find a comment containing the specified marker.

    Args:
        discussion_id: GraphQL node ID of the discussion
        marker: HTML comment marker (e.g., <!-- EIC:LIST:HIGH:2024-01-15 -->)

    Returns:
        CommentInfo or None if not found
    """
    query = """
    query($id: ID!) {
        node(id: $id) {
            ... on Discussion {
                comments(first: 20) {
                    nodes {
                        id
                        body
                    }
                }
            }
        }
    }
    """

    data = _graphql_request(query, {"id": discussion_id})

    for comment in data["node"]["comments"]["nodes"]:
        if marker in comment["body"]:
            return CommentInfo(id=comment["id"], body=comment["body"])

    return None


def create_discussion_comment(discussion_id: str, body: str) -> str:
    """
    Create a new comment on a discussion.

    Args:
        discussion_id: GraphQL node ID of the discussion
        body: Comment body

    Returns:
        Comment node ID
    """
    mutation = """
    mutation($discussionId: ID!, $body: String!) {
        addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
            comment {
                id
            }
        }
    }
    """

    data = _graphql_request(
        mutation,
        {"discussionId": discussion_id, "body": body},
    )

    return data["addDiscussionComment"]["comment"]["id"]


def update_discussion_comment(comment_id: str, body: str) -> None:
    """
    Update an existing comment.

    Args:
        comment_id: GraphQL node ID of the comment
        body: New comment body
    """
    mutation = """
    mutation($commentId: ID!, $body: String!) {
        updateDiscussionComment(input: {commentId: $commentId, body: $body}) {
            comment {
                id
            }
        }
    }
    """

    _graphql_request(
        mutation,
        {"commentId": comment_id, "body": body},
    )


def build_list_comment_body(
    list_type: str,
    date_str: str,
    items: list[dict],
) -> str:
    """
    Build comment body for item list.

    Args:
        list_type: "HIGH" or "TREND"
        date_str: Date in YYYY-MM-DD format
        items: List of processed items

    Returns:
        Comment body string
    """
    marker = f"<!-- EIC:LIST:{list_type}:{date_str} -->"

    if list_type == "HIGH":
        header = "## High Trust Sources"
        emoji = "🏛️"
    else:
        header = "## Trend Sources"
        emoji = "📈"

    lines = [marker, "", header, ""]

    if not items:
        lines.append("_収集アイテムなし_")
        return "\n".join(lines)

    for i, item in enumerate(items, 1):
        reliability = item.get("reliability_score", 50)

        # Reliability indicator
        if reliability >= 70:
            rel_emoji = "🟢"
        elif reliability >= 50:
            rel_emoji = "🟡"
        else:
            rel_emoji = "🔴"

        title = item.get("title", "(タイトルなし)")
        url = item.get("url", "")
        source_name = item.get("source_name", "")
        source_type = item.get("source_type", "")
        summary = item.get("summary", "")
        key_points = item.get("key_points", [])
        themes = item.get("themes", [])

        lines.append(f"### {i}. [{title}]({url})")
        lines.append("")
        lines.append(f"**{emoji} {source_name}** | `{source_type}` | {rel_emoji} {reliability}")
        lines.append("")

        if themes:
            lines.append(f"**テーマ**: {', '.join(themes)}")
            lines.append("")

        if summary:
            lines.append(summary[:500])
            lines.append("")

        if key_points:
            lines.append("**要点:**")
            for kp in key_points[:3]:
                lines.append(f"- {kp}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def upsert_list_comment(
    discussion_id: str,
    list_type: str,
    date_str: str,
    items: list[dict],
) -> None:
    """
    Create or update a list comment with idempotency marker.

    Args:
        discussion_id: GraphQL node ID
        list_type: "HIGH" or "TREND"
        date_str: Date in YYYY-MM-DD format
        items: List of processed items
    """
    marker = f"<!-- EIC:LIST:{list_type}:{date_str} -->"
    body = build_list_comment_body(list_type, date_str, items)

    # Check for existing comment
    existing = find_comment_by_marker(discussion_id, marker)

    if existing:
        logger.info(f"Updating existing {list_type} comment")
        update_discussion_comment(existing["id"], body)
    else:
        logger.info(f"Creating new {list_type} comment")
        create_discussion_comment(discussion_id, body)


def ensure_daily_discussion(
    date_str: str,
    stats: dict | None = None,
) -> DiscussionInfo:
    """
    Ensure a daily discussion exists, creating if necessary.

    Args:
        date_str: Date in YYYY-MM-DD format (JST)
        stats: Optional collection statistics

    Returns:
        DiscussionInfo for the daily thread
    """
    existing = find_daily_discussion(date_str)
    if existing:
        logger.info(f"Found existing discussion: {existing['url']}")
        return existing

    logger.info(f"Creating new discussion for {date_str}")
    return create_daily_discussion(date_str, stats)
