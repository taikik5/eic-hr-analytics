# EIC - External Insight Collector for HR Analytics

HR分析向けの外部情報自動収集システム。毎日9:00 JSTにGitHub Actionsで実行し、HR関連の記事を収集・分析・蓄積します。

---

## 目次

1. [概要](#概要)
2. [システム仕様](#システム仕様)
   - [アーキテクチャ](#アーキテクチャ)
   - [処理フロー](#処理フロー)
   - [収集対象](#収集対象)
   - [HRテーマ分類](#hrテーマ分類)
   - [信頼度スコア](#信頼度スコア)
   - [冪等性保証](#冪等性保証)
3. [機能一覧](#機能一覧)
4. [セットアップガイド](#セットアップガイド)
   - [前提条件](#前提条件)
   - [Step 1: リポジトリの準備](#step-1-リポジトリの準備)
   - [Step 2: GitHub Discussionsの設定](#step-2-github-discussionsの設定)
   - [Step 3: Slackの設定](#step-3-slackの設定)
   - [Step 4: GitHub Secretsの設定](#step-4-github-secretsの設定)
   - [Step 5: 動作確認](#step-5-動作確認)
5. [使い方](#使い方)
6. [ディレクトリ構成](#ディレクトリ構成)
7. [データ形式](#データ形式)
8. [設定ファイル](#設定ファイル)
9. [トラブルシューティング](#トラブルシューティング)
10. [ライセンス](#ライセンス)

---

## 概要

EIC（External Insight Collector）は、HR（人事）分野に関連する外部情報を自動収集・分析・蓄積するシステムです。

### このシステムでできること

| 機能 | 説明 |
|------|------|
| 📰 **自動収集** | RSSフィードからHR関連記事を毎日自動収集（最大40件/日） |
| 🤖 **LLM分析** | OpenAI APIで記事を要約・分類・信頼度評価 |
| 💾 **構造化保存** | JSONL形式でデータを蓄積、重複を自動排除 |
| 💬 **GitHub Discussions** | 日次ダイジェストを自動投稿（HIGH/TREND別） |
| 🔔 **Slack通知** | ハイライト記事を1日1通通知 |

### 主なユースケース

- HR部門の情報収集業務の効率化
- 労働市場・人事トレンドの継続的なモニタリング
- 政策動向（省庁発表）の自動追跡
- ナレッジベースの構築

---

## システム仕様

### アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (毎日 9:00 JST)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   RSS    │───▶│ 本文取得 │───▶│ LLM分析  │───▶│  保存    │  │
│  │  収集    │    │trafilatura│   │ OpenAI   │    │ JSONL    │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                       │         │
│                                    ┌──────────────────┴───────┐ │
│                                    ▼                          ▼ │
│                          ┌──────────────┐          ┌──────────┐ │
│                          │   GitHub     │          │  Slack   │ │
│                          │ Discussions  │          │  通知    │ │
│                          └──────────────┘          └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 処理フロー

1. **候補収集**: RSSフィードから過去48時間以内の記事を収集
2. **重複排除**: URL正規化 + SHA256ハッシュでインデックス照合
3. **本文取得**: trafilaturaで記事本文を抽出（最大12,000文字）
4. **LLM分析**: OpenAI API（gpt-4.1-mini）で要約・分類・評価
5. **保存**: JSONL形式で月別ファイルに追記
6. **Discussion更新**: 日次スレッドにHIGH/TREND別リスト投稿
7. **Slack通知**: 上位5件のハイライトを通知

### 収集対象

#### High Trust（信頼性重視）- 最大20件/日

| 分類 | 情報源例 |
|------|----------|
| 省庁・公的機関 | 厚生労働省、経済産業省、内閣府 |
| 研究機関 | JILPT（労働政策研究・研修機構）、RIETI |
| コンサルティング | マッキンゼー、BCG、デロイト |
| 大手メディア | 日経、東洋経済 |

#### Trend（トレンド重視）- 最大20件/日

| 分類 | 情報源例 |
|------|----------|
| 技術コミュニティ | Zenn、Qiita |
| 企業ブログ | 各社Tech Blog |
| 個人発信 | note |
| 海外メディア | SHRM、HR Dive、People Matters |

### HRテーマ分類

LLMが記事を以下の10テーマに自動分類します：

| キー | 日本語名 | 説明 |
|------|----------|------|
| `recruiting` | 採用 | 採用戦略、人材獲得、採用ブランディング |
| `attrition` | 離職 | 離職率、リテンション、退職分析 |
| `compensation` | 賃金 | 給与、報酬、ベースアップ |
| `engagement` | エンゲージメント | 従業員満足度、モチベーション |
| `human_capital` | 人的資本開示 | ISO30414、人的資本経営 |
| `reskilling` | リスキリング | 学び直し、スキル開発 |
| `labor_market` | 労働市場/制度 | 雇用統計、労働法制 |
| `dei` | DE&I | ダイバーシティ、公平性、インクルージョン |
| `hr_tech` | HRテック | HR SaaS、ピープルアナリティクス |
| `wellbeing` | ウェルビーイング | 健康経営、メンタルヘルス |

### 信頼度スコア

記事の信頼度を0-100のスコアで評価します。

#### ベーススコア（情報源タイプ別）

| source_type | ベーススコア | 説明 |
|-------------|-------------|------|
| `ministry` | 80 | 省庁・政府機関 |
| `intl_org` | 80 | 国際機関 |
| `consulting` | 70 | コンサルティングファーム |
| `paper` | 70 | 研究論文・レポート |
| `news` | 60 | 大手メディア |
| `tech` | 50 | 技術系メディア |
| `blog` | 50 | ブログ・個人発信 |
| `other` | 40 | その他 |

#### 最終スコア計算

```
最終スコア = clamp(ベーススコア + LLM調整値, 0, 100)
```

- LLMが記事内容を分析し、-10〜+10の調整値を付与
- 調整理由も記録（例：「一次ソースを引用」「個人の意見のみ」）

### 冪等性保証

同日に複数回実行しても、データが重複しない設計です。

| 対象 | 冪等性の仕組み |
|------|---------------|
| 記事の重複 | URL正規化 + SHA256ハッシュでインデックス管理 |
| Discussion | 日付タイトル `[EIC][Daily] YYYY-MM-DD (JST)` で検索・再利用 |
| コメント | HTMLマーカー `<!-- EIC:LIST:TYPE:DATE -->` で検索・更新 |
| JSONL | インデックス通過後のみ追記 |

---

## 機能一覧

### 現在実装済みの機能

| 機能 | 状態 | 説明 |
|------|------|------|
| RSS収集 | ✅ 実装済 | feedparserによるRSS/Atomフィード解析 |
| URL正規化 | ✅ 実装済 | utm_*パラメータ削除、フラグメント削除、末尾スラッシュ統一 |
| 重複排除 | ✅ 実装済 | SHA256ハッシュによるインデックス管理 |
| 本文抽出 | ✅ 実装済 | trafilaturaによるHTML→テキスト変換 |
| LLM分析 | ✅ 実装済 | OpenAI Responses API + JSON Schema Strict Mode |
| JSONL保存 | ✅ 実装済 | 月別ファイルへの追記保存 |
| GitHub Discussions | ✅ 実装済 | GraphQL APIによる日次スレッド管理 |
| Slack通知 | ✅ 実装済 | Incoming Webhookによる日次通知 |
| 自動実行 | ✅ 実装済 | GitHub Actions cron（毎日9:00 JST） |
| 手動実行 | ✅ 実装済 | workflow_dispatch対応 |
| 日付指定 | ✅ 実装済 | `--date YYYY-MM-DD` オプション |
| リトライ処理 | ✅ 実装済 | 指数バックオフ付きリトライ |
| 部分失敗許容 | ✅ 実装済 | 個別記事の失敗をスキップして継続 |

---

## セットアップガイド

### 前提条件

以下のアカウント・サービスが必要です：

| 項目 | 説明 | 取得方法 |
|------|------|----------|
| GitHubアカウント | リポジトリ、Discussionsの利用 | [github.com](https://github.com) |
| OpenAI APIキー | LLM分析に使用 | [platform.openai.com](https://platform.openai.com/api-keys) |
| Slackワークスペース | 通知の受信 | [slack.com](https://slack.com) |

### Step 1: リポジトリの準備

#### 1.1 リポジトリのクローン

```bash
git clone https://github.com/your-org/eic-hr-analytics.git
cd eic-hr-analytics
```

#### 1.2 （オプション）ローカル実行環境の準備

ローカルでテストする場合のみ必要です：

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt
```

#### 1.3 （オプション）.envファイルの作成

ローカル実行用の環境変数ファイルを作成：

```bash
cp .env.example .env
```

`.env` を編集して各値を設定：

```
OPENAI_API_KEY=sk-xxxxx
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxxxx
GITHUB_TOKEN=ghp_xxxxx
GITHUB_REPO_OWNER=your-username
GITHUB_REPO_NAME=eic-hr-analytics
```

### Step 2: GitHub Discussionsの設定

#### 2.1 Discussionsの有効化

1. GitHubでリポジトリを開く
2. **Settings**（設定）タブをクリック
3. 左メニューの **General** を選択
4. 下にスクロールして **Features** セクションを探す
5. **Discussions** にチェックを入れる

#### 2.2 カテゴリの作成

1. リポジトリの **Discussions** タブをクリック
2. 左サイドバーの **Categories** の横にある ⚙️（歯車アイコン）をクリック
3. **New category** ボタンをクリック
4. 以下を入力：
   - **Category name**: `Daily Digest`
   - **Description**: `EIC daily collection summaries`（任意）
   - **Discussion Format**: `Announcement`（推奨）
5. **Create** をクリック

#### 2.3 カテゴリIDの取得

1. [GitHub GraphQL Explorer](https://docs.github.com/en/graphql/overview/explorer) にアクセス
2. GitHubアカウントでサインイン
3. 以下のクエリを実行（`YOUR_OWNER` と `YOUR_REPO` を置き換え）：

```graphql
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

4. 結果から `Daily Digest` の `id` をコピー（例：`DIC_kwDO...`）

#### 2.4 カテゴリIDの設定

`config/categories.json` を編集：

```json
{
  "daily_digest_category_id": "DIC_kwDO..."
}
```

### Step 3: Slackの設定

#### 3.1 Slack Appの作成

1. [Slack API](https://api.slack.com/apps) にアクセス
2. **Create New App** をクリック
3. **From scratch** を選択
4. 以下を入力：
   - **App Name**: `EIC Bot`（任意）
   - **Pick a workspace**: 通知を受けたいワークスペースを選択
5. **Create App** をクリック

#### 3.2 Incoming Webhookの有効化

1. 左メニューの **Incoming Webhooks** をクリック
2. **Activate Incoming Webhooks** を **On** に切り替え
3. **Add New Webhook to Workspace** をクリック
4. 通知を投稿するチャンネルを選択（例：`#hr-insights`）
5. **Allow** をクリック
6. 生成された **Webhook URL** をコピー（`https://hooks.slack.com/services/...`）

> ⚠️ **注意**: Webhook URLは機密情報です。コードに直接書かず、必ずSecretsで管理してください。

### Step 4: GitHub Secretsの設定

#### 4.1 Secretsの登録

1. GitHubでリポジトリを開く
2. **Settings** > **Secrets and variables** > **Actions** をクリック
3. **New repository secret** をクリックして以下を登録：

| Secret名 | 値 |
|----------|-----|
| `OPENAI_API_KEY` | OpenAI APIキー（`sk-...`） |
| `SLACK_WEBHOOK_URL` | Slack Webhook URL（`https://hooks.slack.com/...`） |

#### 4.2 Variables（オプション）

デフォルト以外のモデルを使用する場合：

1. **Settings** > **Secrets and variables** > **Actions** の **Variables** タブ
2. **New repository variable** をクリック

| Variable名 | 値 | 説明 |
|------------|-----|------|
| `OPENAI_MODEL` | `gpt-4.1-mini` | 使用するOpenAIモデル |

### Step 5: 動作確認

#### 5.1 手動実行でテスト

1. リポジトリの **Actions** タブをクリック
2. 左メニューから **EIC Daily Collection** を選択
3. **Run workflow** ボタンをクリック
4. **Run workflow** を確認してクリック

#### 5.2 結果の確認

- ✅ **Actions**: ワークフローが緑色（成功）で完了
- ✅ **Discussions**: 新しいスレッドが作成され、HIGH/TRENDコメントが投稿
- ✅ **Slack**: 指定チャンネルに通知が届く
- ✅ **data/**: `items/YYYY-MM.jsonl` と `index.json` が更新

---

## 使い方

### 自動実行

- **スケジュール**: 毎日 9:00 JST（UTC 0:00）に自動実行
- 設定変更: `.github/workflows/eic_daily.yml` の `cron` を編集

### 手動実行（GitHub Actions）

1. **Actions** タブ > **EIC Daily Collection** > **Run workflow**
2. オプションで日付を指定可能（`YYYY-MM-DD` 形式）

### ローカル実行

```bash
# 通常実行（今日の日付で処理）
python -m scripts.run_daily

# 日付を指定して実行
python -m scripts.run_daily --date 2024-01-15
```

---

## ディレクトリ構成

```
eic-hr-analytics/
├── .github/
│   └── workflows/
│       └── eic_daily.yml           # GitHub Actions ワークフロー
├── config/
│   ├── sources_high.yaml           # High Trust情報源（10ソース）
│   ├── sources_trend.yaml          # Trend情報源（10ソース）
│   ├── themes.yaml                 # HRテーマ辞書（10テーマ）
│   └── categories.json             # DiscussionsカテゴリID
├── data/
│   ├── items/                      # 収集データ格納
│   │   ├── .gitkeep
│   │   └── YYYY-MM.jsonl           # 月別データファイル
│   └── index.json                  # 重複排除インデックス
├── scripts/
│   ├── __init__.py
│   ├── run_daily.py                # メインオーケストレーター
│   ├── collect_candidates.py       # RSS収集
│   ├── normalize.py                # URL正規化 + SHA256
│   ├── fetch_content.py            # 本文抽出
│   ├── llm_client.py               # OpenAI API クライアント
│   ├── store.py                    # データ保存
│   ├── github_discussions.py       # GitHub Discussions操作
│   ├── slack_notify.py             # Slack通知
│   └── utils.py                    # 共通ユーティリティ
├── .env.example                    # 環境変数テンプレート
├── .gitignore
├── requirements.txt                # Python依存関係
└── README.md                       # このファイル
```

---

## データ形式

### 記事データ（JSONL）

ファイル: `data/items/YYYY-MM.jsonl`

各行が1記事のJSONオブジェクト：

```json
{
  "item_id": "a1b2c3d4e5f6...",
  "url": "https://example.com/article",
  "url_normalized": "https://example.com/article",
  "title": "記事タイトル",
  "summary": "要約（200-400文字）",
  "key_points": ["要点1", "要点2", "要点3"],
  "themes": ["recruiting", "engagement"],
  "tags": ["採用", "エンゲージメント"],
  "language": "ja",
  "reliability_score": 75,
  "reliability_reason": "公式データを引用",
  "source_group": "high",
  "source_key": "mhlw",
  "source_name": "厚生労働省",
  "source_type": "ministry",
  "publisher": "厚生労働省",
  "rss_title": "元のRSSタイトル",
  "rss_pub_date": "2024-01-15T10:00:00+09:00",
  "content_length": 5000,
  "observed_at": "2024-01-15T09:00:00+09:00"
}
```

### 重複排除インデックス

ファイル: `data/index.json`

```json
{
  "a1b2c3d4e5f6...": {
    "first_seen": "2024-01-15T09:00:00+09:00",
    "source": "厚生労働省",
    "title": "記事タイトル"
  }
}
```

---

## 設定ファイル

### sources_high.yaml / sources_trend.yaml

情報源の定義：

```yaml
sources:
  - key: mhlw              # 一意の識別子
    name: 厚生労働省        # 表示名
    type: ministry          # 情報源タイプ
    publisher: 厚生労働省   # 発行者
    language: ja            # 言語
    rss_url: https://...    # RSSフィードURL
```

### themes.yaml

HRテーマの定義：

```yaml
themes:
  recruiting:
    ja: 採用
    keywords:
      - 採用
      - 人材獲得
      - recruiting
```

### categories.json

GitHub DiscussionsのカテゴリID：

```json
{
  "daily_digest_category_id": "DIC_kwDO..."
}
```

---

## トラブルシューティング

### よくある問題と解決方法

#### ワークフローが失敗する

| エラー | 原因 | 解決方法 |
|--------|------|----------|
| `OPENAI_API_KEY is not set` | Secretが未設定 | Step 4を確認 |
| `GITHUB_TOKEN` 権限エラー | 権限不足 | workflowファイルの`permissions`を確認 |
| `Discussion category not found` | カテゴリID誤り | Step 2.3を再実行 |

#### Slack通知が届かない

1. Webhook URLが正しいか確認
2. Slackアプリがチャンネルに追加されているか確認
3. ワークフローのログで`Slack notification`の出力を確認

#### 記事が収集されない

1. RSSフィードが有効か確認（ブラウザでURLにアクセス）
2. 過去48時間以内の記事があるか確認
3. すべて既存記事として重複排除されていないか確認

### ログの確認

GitHub Actionsのログで詳細を確認できます：

1. **Actions** タブ > 該当のワークフロー実行をクリック
2. **collect** ジョブをクリック
3. 各ステップを展開してログを確認

### リトライ仕様

| 処理 | リトライ回数 | バックオフ |
|------|-------------|-----------|
| OpenAI API | 3回 | 指数（1→2→4秒） |
| コンテンツ取得 | 2回 | 線形（2秒） |
| Slack通知 | 2回 | 線形（2秒） |

---

## ライセンス

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
