"""
Slack webhook notification.

Sends daily summary to Slack channel.
"""

import logging

import requests

from scripts.utils import SLACK_WEBHOOK_URL, retry_with_backoff

logger = logging.getLogger(__name__)


def build_trend_summary(all_items: list[dict]) -> str:
    """
    Build trend summary text from all collected items.

    Args:
        all_items: All items collected today

    Returns:
        Trend summary text in markdown format
    """
    if not all_items:
        return ""

    # Count themes
    theme_counts: dict[str, int] = {}
    for item in all_items:
        themes = item.get("themes", [])
        for theme in themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    if not theme_counts:
        return ""

    # Sort by count (descending)
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)

    # Build summary text
    total_articles = len(all_items)
    top_themes = sorted_themes[:5]  # Top 5 themes

    summary_lines = [f"*📊 本日のトレンド* ({total_articles}件の記事を分析)"]

    for theme, count in top_themes:
        percentage = round(count / total_articles * 100)
        bar_length = min(count, 10)  # Max 10 blocks
        bar = "█" * bar_length
        summary_lines.append(f"• `{theme}`: {count}件 ({percentage}%) {bar}")

    # Show remaining themes count if any
    remaining = len(sorted_themes) - 5
    if remaining > 0:
        other_themes = [t[0] for t in sorted_themes[5:10]]
        summary_lines.append(f"• 他: {', '.join(other_themes)}...")

    return "\n".join(summary_lines)


def build_slack_blocks(
    date_str: str,
    discussion_url: str,
    high_count: int,
    trend_count: int,
    highlights: list[dict],
    all_items: list[dict] | None = None,
    trend_summary_text: str | None = None,
    discussion_failed: bool = False,
) -> list[dict]:
    """
    Build Slack Block Kit message.

    Args:
        date_str: Date string (YYYY-MM-DD)
        discussion_url: URL to GitHub Discussion (or fallback repo URL)
        high_count: Number of HIGH trust items
        trend_count: Number of TREND items
        highlights: Top items to feature
        all_items: All items collected (for trend summary)
        trend_summary_text: LLM-generated summary text
        discussion_failed: Whether Discussion creation failed

    Returns:
        List of Block Kit blocks
    """
    total_count = high_count + trend_count

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📰 EIC Daily Insights - {date_str}",
                "emoji": True,
            },
        },
        {"type": "divider"},
    ]

    # Add trend summary at the top if all_items is provided
    if all_items:
        trend_summary = build_trend_summary(all_items)
        if trend_summary:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": trend_summary,
                    },
                }
            )
            # Add LLM-generated summary text if available
            if trend_summary_text:
                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"💡 {trend_summary_text}",
                            }
                        ],
                    }
                )
            blocks.append({"type": "divider"})

    # Add collection stats
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*収集結果*\n"
                    f"• 🏛️ High Trust: {high_count}件\n"
                    f"• 📈 Trend: {trend_count}件\n"
                    f"• 📊 合計: {total_count}件"
                ),
            },
        }
    )

    # Add warning if Discussion creation failed
    if discussion_failed:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "⚠️ GitHub Discussionの作成に失敗しました。データは正常に保存されています。",
                    }
                ],
            }
        )

    # Add highlights section
    if highlights:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📌 Today's Highlights*",
                },
            }
        )

        for item in highlights[:5]:
            reliability = item.get("reliability_score", 50)
            title = item.get("title", "(タイトルなし)")[:60]
            url = item.get("url", "")
            summary = item.get("summary", "")[:150]
            source_name = item.get("source_name", "")
            themes = item.get("themes", [])

            # Reliability emoji
            if reliability >= 70:
                rel_emoji = "🟢"
            elif reliability >= 50:
                rel_emoji = "🟡"
            else:
                rel_emoji = "🔴"

            # Build item text
            item_text = f"{rel_emoji} *<{url}|{title}>*\n"
            item_text += f"_{source_name}_"
            if themes:
                item_text += f" | {', '.join(themes)}"
            item_text += f"\n{summary}..."

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": item_text,
                    },
                }
            )

    # Add link to Discussion or Repository
    blocks.append({"type": "divider"})
    if discussion_failed:
        link_text = f"<{discussion_url}|📂 View Repository>"
    else:
        link_text = f"<{discussion_url}|📋 View Full Discussion>"
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": link_text,
            },
        }
    )

    # Add context footer
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Powered by EIC (External Insight Collector)",
                }
            ],
        }
    )

    return blocks


@retry_with_backoff(max_retries=2, base_delay=2.0, exceptions=(requests.RequestException,))
def send_daily_notification(
    date_str: str,
    discussion_url: str,
    high_count: int,
    trend_count: int,
    highlights: list[dict],
    all_items: list[dict] | None = None,
    trend_summary_text: str | None = None,
    discussion_failed: bool = False,
) -> bool:
    """
    Send daily summary to Slack.

    Args:
        date_str: Date string (YYYY-MM-DD)
        discussion_url: URL to GitHub Discussion (or fallback repo URL)
        high_count: Number of HIGH trust items
        trend_count: Number of TREND items
        highlights: Top items to feature
        all_items: All items collected (for trend summary)
        trend_summary_text: LLM-generated summary text
        discussion_failed: Whether Discussion creation failed

    Returns:
        True if sent successfully
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured, skipping notification")
        return False

    total_count = high_count + trend_count

    blocks = build_slack_blocks(
        date_str=date_str,
        discussion_url=discussion_url,
        high_count=high_count,
        trend_count=trend_count,
        highlights=highlights,
        trend_summary_text=trend_summary_text,
        all_items=all_items,
        discussion_failed=discussion_failed,
    )

    payload = {
        "text": f"EIC Daily: {total_count} articles collected ({date_str})",
        "blocks": blocks,
    }

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return True
        else:
            logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
            return False

    except requests.RequestException as e:
        logger.error(f"Slack notification request failed: {e}")
        raise  # Re-raise for retry


def send_no_updates_notification(date_str: str) -> bool:
    """
    Send notification when no new articles were found.

    Args:
        date_str: Date string (YYYY-MM-DD)

    Returns:
        True if sent successfully
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack webhook URL not configured, skipping notification")
        return False

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📰 EIC Daily Insights - {date_str}",
                "emoji": True,
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*収集結果*\n"
                    "本日の更新はありませんでした。\n\n"
                    "_新しい記事が見つからなかったか、すべて既に収集済みでした。_"
                ),
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Powered by EIC (External Insight Collector)",
                }
            ],
        },
    ]

    payload = {
        "text": f"EIC Daily: No new articles ({date_str})",
        "blocks": blocks,
    }

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            logger.info("Slack 'no updates' notification sent successfully")
            return True
        else:
            logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
            return False

    except requests.RequestException as e:
        logger.error(f"Slack notification request failed: {e}")
        return False


def send_error_notification(date_str: str, error_message: str) -> bool:
    """
    Send error notification to Slack.

    Args:
        date_str: Date string (YYYY-MM-DD)
        error_message: Error message to send

    Returns:
        True if sent successfully
    """
    if not SLACK_WEBHOOK_URL:
        return False

    payload = {
        "text": f"⚠️ EIC Error ({date_str}): {error_message}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚠️ EIC Error - {date_str}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{error_message[:1000]}```",
                },
            },
        ],
    }

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
        return False
