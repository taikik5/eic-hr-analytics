# EIC - External Insight Collector for HR Analytics

HR分析向けの外部情報自動収集システム。毎日9:00 JSTにGitHub Actionsで実行し、HR関連の記事を収集・分析・蓄積します。

## 機能

- **自動収集**: RSSフィードからHR関連記事を毎日自動収集
- **LLM分析**: OpenAI APIで記事を要約・分類・信頼度評価
- **構造化保存**: JSONL形式でデータを蓄積、重複を自動排除
- **GitHub Discussions**: 日次ダイジェストを自動投稿
- **Slack通知**: ハイライトを1日1通通知

## 収集対象

### High Trust（最大20件/日）
- 省庁・公的機関（厚労省、経産省等）
- 研究機関（JILPT、RIETI等）
- コンサルティング・シンクタンク
- 大手メディア

### Trend（最大20件/日）
- Zenn / Qiita
- 企業Tech Blog
- note
- 海外HRメディア

## セットアップ

### 1. リポジトリの準備

```bash
# クローン
git clone https://github.com/your-org/eic-hr-analytics.git
cd eic-hr-analytics

# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
```

### 2. GitHub Discussionsの設定

1. リポジトリの Settings > Features で Discussions を有効化
2. Discussions タブで「Daily Digest」カテゴリを作成
3. カテゴリIDを取得（下記GraphQLクエリを使用）
4. `config/categories.json` にIDを設定

```graphql
# GitHub GraphQL Explorer (https://docs.github.com/en/graphql/overview/explorer) で実行
query {
  repository(owner: "YOUR_OWNER", name: "YOUR_REPO") {
    discussionCategories(first: 20) {
      nodes {
        id
        name
      }
    }
  }
}
```

### 3. Secretsの設定

リポジトリの Settings > Secrets and variables > Actions で以下を設定:

| Secret | 説明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI APIキー |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

`GITHUB_TOKEN` は自動で提供されます。

### 4. Variables（オプション）

| Variable | デフォルト | 説明 |
|----------|----------|------|
| `OPENAI_MODEL` | `gpt-4.1-mini` | 使用するOpenAIモデル |

## 使い方

### 手動実行

```bash
# ローカル実行（.envファイルが必要）
python -m scripts.run_daily

# 日付指定
python -m scripts.run_daily --date 2024-01-15
```

### GitHub Actions

- **自動実行**: 毎日9:00 JST
- **手動実行**: Actions > EIC Daily Collection > Run workflow

## ディレクトリ構成

```
eic-hr-analytics/
├── .github/workflows/
│   └── eic_daily.yml       # GitHub Actions ワークフロー
├── config/
│   ├── sources_high.yaml   # High Trust情報源
│   ├── sources_trend.yaml  # Trend情報源
│   ├── themes.yaml         # HRテーマ辞書
│   └── categories.json     # DiscussionsカテゴリID
├── data/
│   ├── items/              # YYYY-MM.jsonl
│   └── index.json          # 重複排除インデックス
├── scripts/
│   ├── run_daily.py        # メインオーケストレーター
│   ├── collect_candidates.py
│   ├── normalize.py
│   ├── fetch_content.py
│   ├── llm_client.py
│   ├── store.py
│   ├── github_discussions.py
│   └── slack_notify.py
└── requirements.txt
```

## データ形式

### JSONL (`data/items/YYYY-MM.jsonl`)

```json
{
  "item_id": "sha256...",
  "url": "https://...",
  "title": "記事タイトル",
  "summary": "要約（200-400文字）",
  "key_points": ["要点1", "要点2", "要点3"],
  "themes": ["recruiting", "engagement"],
  "tags": ["採用", "エンゲージメント"],
  "reliability_score": 75,
  "source_group": "high",
  "source_type": "ministry",
  "observed_at": "2024-01-15T09:00:00+09:00"
}
```

### インデックス (`data/index.json`)

```json
{
  "sha256...": {
    "first_seen": "2024-01-15T09:00:00+09:00",
    "source": "厚生労働省",
    "title": "記事タイトル"
  }
}
```

## HRテーマ

| キー | 日本語名 |
|------|----------|
| `recruiting` | 採用 |
| `attrition` | 離職 |
| `compensation` | 賃金 |
| `engagement` | エンゲージメント |
| `human_capital` | 人的資本開示 |
| `reskilling` | リスキリング |
| `labor_market` | 労働市場/制度 |
| `dei` | DE&I |
| `hr_tech` | HRテック |
| `wellbeing` | ウェルビーイング |

## 信頼度スコア

| source_type | ベーススコア |
|-------------|-------------|
| ministry / intl_org | 80 |
| consulting / paper | 70 |
| news | 60 |
| tech / blog | 50 |
| other | 40 |

LLMが記事内容に基づき -10 〜 +10 の調整を行い、最終スコア（0-100）を算出。

## 冪等性

- **URL重複**: sha256ハッシュでインデックス管理
- **Discussion**: 日付タイトルで検索→再利用
- **コメント**: マーカー `<!-- EIC:LIST:TYPE:DATE -->` で検索→更新

同日に複数回実行しても、Discussionやデータが重複することはありません。

## トラブルシューティング

### APIエラー

- OpenAI: リトライ付き（最大3回、指数バックオフ）
- GitHub: 権限設定を確認（`contents: write`, `discussions: write`）

### コンテンツ取得失敗

- 個別記事の失敗はスキップして継続
- 本文なしでもLLMがタイトルから要約を生成

## ライセンス

MIT
