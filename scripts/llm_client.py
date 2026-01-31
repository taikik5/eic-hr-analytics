"""
OpenAI Responses API client with JSON Schema strict mode.

Analyzes articles and returns structured enrichment data.
"""

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from scripts.utils import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    load_themes_config,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


# JSON Schema for enriched item output (Strict Mode)
ENRICHMENT_SCHEMA = {
    "name": "enriched_item",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {
                "type": "string",
                "description": "Article title, cleaned and normalized",
            },
            "summary": {
                "type": "string",
                "description": "Summary in Japanese, 200-400 characters",
            },
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 3 key takeaways",
            },
            "themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Theme keys from config (e.g., recruiting, attrition)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relevant tags for categorization",
            },
            "language": {
                "type": "string",
                "enum": ["ja", "en", "unknown"],
                "description": "Primary language of the article",
            },
            "published_at": {
                "type": ["string", "null"],
                "description": "ISO 8601 date string or null if unknown",
            },
            "reliability_score_delta": {
                "type": "integer",
                "description": "Adjustment to base reliability score (-10 to +10)",
            },
            "reliability_reason": {
                "type": "string",
                "description": "Brief explanation for reliability adjustment",
            },
        },
        "required": [
            "title",
            "summary",
            "key_points",
            "themes",
            "tags",
            "language",
            "published_at",
            "reliability_score_delta",
            "reliability_reason",
        ],
    },
}


@dataclass
class EnrichedItem:
    """Structured result from LLM analysis."""

    title: str
    summary: str
    key_points: list[str]
    themes: list[str]
    tags: list[str]
    language: str
    published_at: str | None
    reliability_score_delta: int
    reliability_reason: str


def build_themes_list() -> str:
    """Build themes list string for system prompt."""
    config = load_themes_config()
    themes = config.get("themes", [])

    lines = []
    for theme in themes:
        key = theme.get("key", "")
        name = theme.get("name", "")
        keywords = ", ".join(theme.get("keywords", [])[:5])
        lines.append(f"- {key}: {name} (例: {keywords})")

    return "\n".join(lines)


def build_system_prompt() -> str:
    """Build system prompt for article analysis."""
    themes_list = build_themes_list()

    return f"""あなたはHR（人事）領域の専門アナリストです。
記事を分析し、構造化されたJSON形式で結果を出力してください。

## 利用可能なテーマキー（themes）
以下のキーからのみ選択してください：
{themes_list}

## 分析ガイドライン

### summary（要約）
- 日本語で200〜400文字程度
- 記事の主要な内容を簡潔にまとめる
- 本文が空または短い場合は、タイトルから推測して短く要約し「※本文未取得のため推測」と付記

### key_points（要点）
- 必ず3つ
- 各要点は1文で簡潔に
- 日本語で記述

### themes（テーマ）
- 上記の利用可能なテーマキーから該当するものを選択
- 複数選択可
- 該当なしの場合は空配列

### tags（タグ）
- 記事の内容を表す自由タグ
- 3〜8個程度

### language（言語）
- ja: 日本語記事
- en: 英語記事
- unknown: 判別不能

### published_at（公開日）
- 記事本文から公開日が確実に特定できる場合のみISO 8601形式で記載
- 不明な場合はnull

### reliability_score_delta（信頼度調整）
- -10〜+10の整数
- 基準：
  - 高品質な調査データ・研究結果あり: +5〜+10
  - 標準的な内容: 0
  - 主観的・根拠が薄い: -3〜-7
  - 宣伝目的が強い・誤情報の可能性: -8〜-10

### reliability_reason（信頼度理由）
- reliability_score_deltaの根拠を1文で簡潔に説明
"""


def build_user_prompt(
    content: str,
    source_name: str,
    source_type: str,
    publisher: str,
    original_title: str | None,
    language: str,
) -> str:
    """Build user prompt with article information."""
    return f"""## 記事情報
ソース名: {source_name}
発行元: {publisher}
ソースタイプ: {source_type}
言語: {language}
元タイトル: {original_title or "(不明)"}

## 記事本文
{content if content else "(本文取得失敗)"}
"""


class LLMClient:
    """
    OpenAI Responses API client for article enrichment.

    Uses JSON Schema strict mode for guaranteed structured output.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize LLM client.

        Args:
            api_key: OpenAI API key (default: from env)
            model: Model name (default: from env)
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model or OPENAI_MODEL
        self._system_prompt = build_system_prompt()

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def analyze_article(
        self,
        content: str,
        source_name: str,
        source_type: str,
        publisher: str,
        original_title: str | None = None,
        language: str = "unknown",
    ) -> EnrichedItem | None:
        """
        Analyze article content using OpenAI Responses API.

        Args:
            content: Full article text (or empty string if unavailable)
            source_name: Name of the source
            source_type: Type for base reliability
            publisher: Publisher name
            original_title: Title from RSS feed
            language: Language hint from source config

        Returns:
            EnrichedItem or None on failure
        """
        user_prompt = build_user_prompt(
            content=content,
            source_name=source_name,
            source_type=source_type,
            publisher=publisher,
            original_title=original_title,
            language=language,
        )

        try:
            # Use Chat Completions API with structured outputs
            # (OpenAI Responses API may use different syntax)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": ENRICHMENT_SCHEMA,
                },
                temperature=0.3,
                max_tokens=2000,
            )

            # Parse the structured output
            result_text = response.choices[0].message.content
            if not result_text:
                logger.error("Empty response from LLM")
                return None

            result = json.loads(result_text)

            # Validate key_points count
            key_points = result.get("key_points", [])
            if len(key_points) != 3:
                # Adjust to exactly 3 key points
                if len(key_points) < 3:
                    key_points.extend(["(要点なし)"] * (3 - len(key_points)))
                else:
                    key_points = key_points[:3]
                result["key_points"] = key_points

            # Clamp reliability_score_delta
            delta = result.get("reliability_score_delta", 0)
            result["reliability_score_delta"] = max(-10, min(10, delta))

            return EnrichedItem(
                title=result["title"],
                summary=result["summary"],
                key_points=result["key_points"],
                themes=result["themes"],
                tags=result["tags"],
                language=result["language"],
                published_at=result["published_at"],
                reliability_score_delta=result["reliability_score_delta"],
                reliability_reason=result["reliability_reason"],
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            raise  # Re-raise for retry decorator

    def test_connection(self) -> bool:
        """Test API connectivity."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
