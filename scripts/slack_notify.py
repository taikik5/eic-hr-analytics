"""
Slack webhook notification.

Sends daily summary to Slack channel.
"""

import logging

import requests

from scripts.utils import SLACK_WEBHOOK_URL, retry_with_backoff

logger = logging.getLogger(__name__)


def build_slack_blocks(
    date_str: str,
    discussion_url: str,
    high_count: int,
    trend_count: int,
    highlights: list[dict],
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
        },
    ]

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
                item_text += f" | {', '.join(themes[:3])}"
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
