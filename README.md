# EIC - External Insight Collector for HR Analytics

HR分析向けの外部情報自動収集システム。毎日9:00 JSTにGitHub Actionsで実行し、HR関連の記事を収集・分析・蓄積します。

---

## 目次

1. [概要](#概要)
   - [EICとは](#eicとは)
   - [なぜEICが必要なのか](#なぜeicが必要なのか)
   - [このシステムでできること](#このシステムでできること)
   - [3つの出力チャネルと役割](#3つの出力チャネルと役割)
   - [活用シナリオ](#活用シナリオ)
   - [JSONLデータの実践的活用パターン](#jsonlデータの実践的活用パターン)
2. [収集対象サイト一覧](#収集対象サイト一覧)
3. [システム仕様](#システム仕様)
   - [アーキテクチャ](#アーキテクチャ)
   - [処理フロー](#処理フロー)
   - [HRテーマ分類](#hrテーマ分類)
   - [信頼度スコア](#信頼度スコア)
   - [冪等性保証](#冪等性保証)
4. [機能一覧](#機能一覧)
5. [セットアップガイド](#セットアップガイド)
   - [前提条件](#前提条件)
   - [Step 1: リポジトリの準備](#step-1-リポジトリの準備)
   - [Step 2: GitHub Discussionsの設定](#step-2-github-discussionsの設定)
   - [Step 3: Personal Access Token (PAT) の作成](#step-3-personal-access-token-pat-の作成)
   - [Step 4: Slackの設定](#step-4-slackの設定)
   - [Step 5: GitHub Secretsの設定](#step-5-github-secretsの設定)
   - [Step 6: 動作確認](#step-6-動作確認)
6. [使い方](#使い方)
7. [ディレクトリ構成](#ディレクトリ構成)
8. [データ形式](#データ形式)
9. [設定ファイル](#設定ファイル)
10. [トラブルシューティング](#トラブルシューティング)
11. [ライセンス](#ライセンス)

---

## 概要

### EICとは

**EIC（External Insight Collector）** は、HR（人事）分野に関連する外部情報を**自動で収集・分析・蓄積**するシステムです。

毎日決まった時間に、省庁の発表、コンサルティングファームのレポート、技術ブログなど、HR関連の情報源を巡回し、新しい記事を見つけてAI（OpenAI API）で要約・分類します。収集したデータは構造化されて保存され、Slack通知やGitHub Discussionsで確認できます。

```
┌─────────────────────────────────────────────────────────────────────────┐
│  「HR領域の情報収集、毎日やるのは大変...」                                   │
│                           ↓                                              │
│  EICが毎朝自動で収集 → AI要約 → Slackに通知 → データも蓄積               │
│                           ↓                                              │
│  「今日の重要ニュースがSlackに届く！過去データも検索できる！」              │
└─────────────────────────────────────────────────────────────────────────┘
```

### なぜEICが必要なのか

HR領域では、以下のような情報を継続的に追跡する必要があります：

| 情報の種類 | 例 | 追跡の重要性 |
|-----------|-----|-------------|
| **法制度の変更** | 働き方改革関連法、育児介護休業法改正 | コンプライアンス対応 |
| **労働市場動向** | 有効求人倍率、転職率、賃金統計 | 採用戦略の立案 |
| **先進事例** | 他社のHRテック導入、人的資本開示の取り組み | ベストプラクティスの参考 |
| **技術トレンド** | ピープルアナリティクス、AIによる採用 | DX推進の検討材料 |

しかし、これらの情報源は多岐にわたり、毎日チェックするのは現実的ではありません。EICはこの**情報収集の自動化**を実現します。

### このシステムでできること

| 機能 | 説明 |
|------|------|
| **自動収集** | 20以上のRSSフィードからHR関連記事を毎日自動収集（最大40件/日） |
| **AI分析** | OpenAI APIで記事を要約（200-400字）、テーマ分類、信頼度評価 |
| **構造化保存** | JSONL形式でデータを蓄積、URL重複を自動排除 |
| **GitHub Discussions** | 日次ダイジェストを自動投稿（HIGH/TREND別にリスト化） |
| **Slack通知** | 上位5件のハイライト記事を1日1通通知 |

### 3つの出力チャネルと役割

EICは収集したデータを**3つのチャネル**に出力します。それぞれ異なる役割があり、用途に応じて使い分けられます。

```
                    ┌─────────────────────┐
                    │   EIC Daily Run     │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   JSONL Files   │  │ GitHub          │  │   Slack         │
│   (データ蓄積)   │  │ Discussions     │  │   (即時通知)     │
│                 │  │ (日次レビュー)   │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

#### 1. JSONLファイル（データ蓄積層）

**ファイル**: `data/items/YYYY-MM.jsonl`

| 項目 | 説明 |
|------|------|
| **役割** | 長期的なデータ蓄積・分析基盤 |
| **形式** | 1行1記事のJSON（月別ファイル） |
| **特徴** | 全記事の詳細情報を保持（要約、テーマ、信頼度スコアなど） |
| **用途** | 過去データの検索、傾向分析、レポート作成、外部ツール連携 |

**活用例**:
- 「過去3ヶ月で"リスキリング"に関する記事は何件あったか？」
- 「信頼度スコア70以上の記事だけ抽出してレポートを作成」
- BIツール（Tableau、Power BI）やJupyter Notebookでの分析

#### 2. GitHub Discussions（日次レビュー層）

**場所**: リポジトリの「Discussions」タブ

| 項目 | 説明 |
|------|------|
| **役割** | チームでの日次情報共有・議論 |
| **形式** | 日付ごとのスレッド + HIGH/TRENDコメント |
| **特徴** | コメント機能で議論可能、履歴が残る |
| **用途** | 毎朝のチームレビュー、重要記事へのコメント付け |

**活用例**:
- 毎朝のミーティングで「今日のDiscussionを見ながら議論」
- 気になる記事に「これ深掘りしたい」とコメント
- 過去の日付のスレッドを検索して振り返り

#### 3. Slack通知（即時通知層）

**場所**: 指定したSlackチャンネル

| 項目 | 説明 |
|------|------|
| **役割** | 重要記事の即時プッシュ通知 |
| **形式** | Block Kit形式のリッチメッセージ |
| **特徴** | 信頼度スコア上位5件をハイライト |
| **用途** | 忙しい人向けの「今日の要点」、Discussionへの導線 |

**活用例**:
- 朝の通勤中にスマホでSlack通知をチェック
- 「詳細はDiscussionで」のリンクからフル版を確認
- チーム全員が同じ情報を共有

### 活用シナリオ

#### シナリオ1: 日々の情報収集効率化

```
Before: 毎朝30分かけて10サイトをチェック → 見落としも多い
After:  Slackに届く通知を5分でチェック → 漏れなく把握
```

#### シナリオ2: 月次レポートの作成

```
Before: 1ヶ月分の記事を思い出しながら手動でまとめる
After:  JSONLファイルを分析して「今月のHRトピックTop10」を自動生成
```

#### シナリオ3: 経営層への報告資料

```
Before: 「最近のHRトレンドは？」と聞かれて慌てて調査
After:  蓄積データから「信頼度スコア70以上の省庁発表」を抽出してすぐ提出
```

#### シナリオ4: ナレッジベース構築

```
JSONLデータをNotionやConfluenceにインポート
 → 社内HRナレッジDBとして活用
 → 「過去にこんな事例があった」と検索可能に
```

#### シナリオ5: 将来的なAI活用への布石

```
蓄積したJSONLデータ
 → RAG（検索拡張生成）の知識ベースとして活用
 → 「最新のHR法制度について教えて」と社内AIに質問
```

### JSONLデータの実践的活用パターン

EICが蓄積するJSONLファイル（`data/items/YYYY-MM.jsonl`）には、各記事の詳細情報が構造化されて保存されています。以下は、実際の業務で活用される3つの代表的なシーンです。

#### パターン1: 採用施策の改善

**状況**: 新卒採用の早期離職が多い問題を解決したい

**JSONLデータの活用フロー**:

1. **テーマで絞り込み**
   ```json
   themes = "recruiting" の記事を抽出（例：15件）
   ```

2. **信頼度でランキング**
   ```
   reliability_score 65点以上 → 業界の信頼できる情報
   60点以下 → 参考程度にとどめる
   ```

3. **キーポイントの抽出**
   各記事の `key_points` から施策のヒントを発見
   ```
   例："理念共感が定着率向上の鍵"
      "RJP理論による情報開示が重要"
      "経営者の早期関与が必須"
   ```

4. **経営層への提案**
   複数の信頼度高い記事から「理念共感採用」の重要性を立証し、
   採用ページの改善やRJP実装を提案

5. **施策の継続的モニタリング**
   実装後、同じテーマの新しい事例をEICで追跡し、効果測定

**実装例**（Pythonでの分析）:
```python
import pandas as pd

# JSONLを読み込み
df = pd.read_json('data/items/2026-01.jsonl', lines=True)

# 採用関連の記事を抽出
recruiting_articles = df[df['themes'].apply(lambda x: 'recruiting' in x)]

# 信頼度が高い順にソート
high_quality = recruiting_articles[recruiting_articles['reliability_score'] >= 65]\
    .sort_values('reliability_score', ascending=False)

# 要点と信頼度を表示
print(high_quality[['title', 'reliability_score', 'key_points', 'url']])
```

#### パターン2: 組織課題の多角的把握

**状況**: 「最近、何か組織の雰囲気が変わってきた気がする」という経営層の懸念

**JSONLデータの活用フロー**:

1. **テーマ別の月次集計**
   ```
   themes の出現頻度を集計：
   - recruiting       8件
   - attrition        8件
   - engagement       5件
   - compensation     2件
   - wellbeing        3件
   ```

2. **トレンド変化の検知**
   - 前月より「定着」関連の記事が増加 → 業界全体で離職課題が顕著化
   - 「女性のウェルビーイング」が新たなテーマに → 自社でも対応が必要かも

3. **タグから具体的な対策テーマを抽出**
   ```
   "理念共感", "キャリア自律", "オンボーディング",
   "心理的安全性", "女性の健康支援" などのキーワードが頻出
   ```

4. **経営層への報告資料作成**
   「業界全体で採用と定着が両立困難な状況。
    自社もこの波に乗っている可能性がある。
    来年度は入社後の適応支援に投資すべき」

**実装例**（集計):
```python
# テーマ別の記事数をカウント
theme_counts = {}
for _, row in df.iterrows():
    for theme in row['themes']:
        theme_counts[theme] = theme_counts.get(theme, 0) + 1

# 出現頻度でソート
sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
for theme, count in sorted_themes:
    print(f"{theme}: {count}件")

# タグの出現頻度
from collections import Counter
all_tags = []
for _, row in df.iterrows():
    all_tags.extend(row['tags'])
tag_counts = Counter(all_tags)
print("\nホットなタグ Top 10:")
for tag, count in tag_counts.most_common(10):
    print(f"  {tag}: {count}件")
```

#### パターン3: 外部ベストプラクティスの検証

**状況**: 「1on1制度の導入を考えているが、実際に効果がある？」

**JSONLデータの活用フロー**:

1. **キーワード検索**
   ```json
   title または summary に "1on1" が含まれる記事を検索
   ```

2. **企業事例の発見**
   ```
   例："味の素式ななメンター制度"
       reliability_score: 65 (High Trust Source + 企業事例)
       key_points:
       - "応募者が定員の1.5〜2倍に達している"
       - "エンゲージメント向上・離職率低下の効果"
   ```

3. **信頼度の確認**
   - 記事元が「HR NOTE」+ 企業の公式セミナー → 信頼性が高い
   - published_at が最近 → 最新の事例

4. **経営層への企画書に引用**
   ```
   「HR NOTEの記事によると、味の素のななメンター制度は
    エンゲージメント向上と離職率低下に貢献。
    参考資料：[記事URL]」
   ```

5. **継続的なベンチマーク**
   実装後、定期的にEICで同テーマの新事例をモニタリングし、
   業界水準と自社の成果を比較

**実装例**（キーワード検索）:
```python
# "1on1" に関連する記事を検索
search_keyword = '1on1'
results = df[
    df['title'].str.contains(search_keyword, case=False) |
    df['summary'].str.contains(search_keyword, case=False)
]

# 信頼度が高い順に表示
for _, row in results.sort_values('reliability_score', ascending=False).iterrows():
    print(f"【{row['source_name']}】{row['reliability_score']}点")
    print(f"{row['title']}")
    print(f"要点：{row['key_points']}")
    print(f"URL: {row['url']}\n")
```

#### JSONLデータの実用的な活用パターン一覧

| 活用シーン | 使う項目 | 効果 |
|-----------|----------|------|
| **課題分析** | `themes`, `key_points` | 業界トレンドから自社課題を発見 |
| **施策の根拠集め** | `title`, `summary`, `url` | 提案に説得力をもたせる |
| **ベストプラクティス検証** | `reliability_score`, `source_type` | 信頼度で情報の質を判断 |
| **定期モニタリング** | `observed_at`, `tags` | 同テーマの継続的な追跡 |
| **経営判断材料** | `published_at` の時系列 | トレンド変化を検知 |
| **BIツール連携** | 全項目 | TableauやPower BIでの可視化 |

#### JSONLの主要フィールド説明

各記事は以下の情報を含みます（検索・分析に活用）:

```json
{
  "item_id": "sha256ハッシュ",              // 重複排除用のID
  "url": "記事のURL",                      // 元記事へのリンク
  "title": "AI要約されたタイトル",         // 正規化されたタイトル
  "summary": "200-400字の日本語要約",      // すぐに読める要点
  "key_points": ["要点1", "要点2", "要点3"], // 必ず3つ
  "themes": ["recruiting", "attrition"],   // 複数選択可
  "tags": ["採用", "新卒採用", ...],       // 自由タグ
  "source_name": "HR NOTE",                // 情報源名
  "source_type": "news",                   // 信頼度の基準
  "reliability_score": 65,                 // 0-100のスコア
  "published_at": "2026-01-31T...",        // 公開日
  "observed_at": "2026-01-31T16:36:...",   // 収集日時
  "language": "ja"                         // 言語（ja/en/unknown）
}
```

---

## 収集対象サイト一覧

EICは以下のサイトからRSSフィードを通じて記事を収集します。

### High Trust Sources（信頼性重視）

高い信頼性を持つ情報源です。省庁発表、研究機関レポート、大手メディアなど。

| 状態 | ソース名 | 発行者 | 種別 | URL |
|------|----------|--------|------|-----|
| ✅ 有効 | 厚生労働省 新着情報 | 厚生労働省 | ministry | https://www.mhlw.go.jp/stf/rss/shinchaku.xml |
| ✅ 有効 | HR NOTE | HR NOTE | news | https://hrnote.jp/feed/ |
| ⏸️ 停止中 | 経済産業省 新着情報 | 経済産業省 | ministry | https://www.meti.go.jp/rss/recent.xml |
| ⏸️ 停止中 | 労働政策研究・研修機構 | JILPT | intl_org | https://www.jil.go.jp/rss/whatsnew.xml |
| ⏸️ 停止中 | 経済産業研究所 | RIETI | intl_org | https://www.rieti.go.jp/jp/rss/index.xml |
| ⏸️ 停止中 | リクルートワークス研究所 | リクルートワークス研究所 | consulting | https://www.works-i.com/feed/ |
| ⏸️ 停止中 | 野村総合研究所 | 野村総合研究所 | consulting | https://www.nri.com/jp/knowledge/blog/feed |
| ⏸️ 停止中 | 日経 人事・労務 | 日本経済新聞 | news | https://www.nikkei.com/rss/feeds/economy.xml |
| ⏸️ 停止中 | ILO ニュース | International Labour Organization | intl_org | https://www.ilo.org/global/rss/lang--en/index.htm |
| ⏸️ 停止中 | OECD 雇用・労働 | OECD | intl_org | https://www.oecd.org/employment/rss/index.xml |

> **Note**: 「⏸️ 停止中」のソースはテスト期間中のためコメントアウトされています。本番運用時は `config/sources_high.yaml` のコメントを解除してください。

### Trend Sources（トレンド重視）

技術コミュニティや企業ブログなど、トレンド把握に有用な情報源です。

| 状態 | ソース名 | 発行者 | 種別 | URL |
|------|----------|--------|------|-----|
| ✅ 有効 | SmartHR Tech Blog | SmartHR | blog | https://tech.smarthr.jp/feed |
| ✅ 有効 | サイボウズ式 | サイボウズ | blog | https://cybozushiki.cybozu.co.jp/feed |
| ⏸️ 停止中 | Zenn HR関連 | Zenn | tech | https://zenn.dev/topics/hr/feed |
| ⏸️ 停止中 | Zenn ピープルアナリティクス | Zenn | tech | https://zenn.dev/topics/peopleanalytics/feed |
| ⏸️ 停止中 | Qiita HR関連 | Qiita | tech | https://qiita.com/tags/hr/feed |
| ⏸️ 停止中 | note HR関連 | note | blog | https://note.com/hashtag/人事/rss |
| ⏸️ 停止中 | メルカリ Engineering Blog | メルカリ | blog | https://engineering.mercari.com/blog/feed.xml |
| ⏸️ 停止中 | Harvard Business Review - HR | Harvard Business Review | consulting | https://hbr.org/topic/human-resource-management/feed |
| ⏸️ 停止中 | SHRM News | SHRM | news | https://www.shrm.org/rss/pages/news.aspx |
| ⏸️ 停止中 | Medium HR & Leadership | Medium | blog | https://medium.com/feed/tag/human-resources |

### ソースの有効化方法

停止中のソースを有効化するには、対応する設定ファイルを編集します：

```bash
# High Trustソースの設定
config/sources_high.yaml

# Trendソースの設定
config/sources_trend.yaml
```

コメントアウト（`#`）を削除して保存すると、次回の実行から収集対象に追加されます。

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

> ⚠️ **重要**: カテゴリのフォーマットは必ず「Open-ended Discussion」を選択してください。「Announcement」を選択するとGitHub Actionsからの投稿が失敗します。

1. リポジトリの **Discussions** タブをクリック
2. 左サイドバーの **Categories** の横にある ⚙️（歯車アイコン）をクリック
3. **New category** ボタンをクリック
4. 以下を入力：
   - **Category name**: `Daily Digest`
   - **Description**: `EIC daily collection summaries`（任意）
   - **Discussion Format**: `Open-ended Discussion`（**必須**）
5. **Create** をクリック

#### 2.3 ワークフロー権限の設定

> ⚠️ **重要**: この設定がないとDiscussionへの投稿が失敗します

1. リポジトリの **Settings** > **Actions** > **General** を開く
2. 下部の「**Workflow permissions**」セクションを確認
3. 「**Read and write permissions**」を選択
4. **Save** をクリック

#### 2.4 カテゴリIDの取得

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

#### 2.5 カテゴリIDの設定

`config/categories.json` を編集：

```json
{
  "daily_digest_category_id": "DIC_kwDO..."
}
```

### Step 3: Personal Access Token (PAT) の作成

> ⚠️ **重要**: GitHub Actionsの自動生成トークン（GITHUB_TOKEN）はDiscussion作成に必要な権限が不足している場合があります。確実に動作させるために、Personal Access Token (PAT) を作成することを**強く推奨**します。

#### 3.1 Fine-grained Personal Access Tokenの作成

1. GitHubにログインし、右上のプロフィールアイコンをクリック
2. **Settings** をクリック
3. 左メニューの一番下にある **Developer settings** をクリック
4. **Personal access tokens** > **Fine-grained tokens** をクリック
5. **Generate new token** をクリック

#### 3.2 トークンの設定

以下の設定を行います：

| 項目 | 値 |
|------|-----|
| **Token name** | `EIC-HR-Analytics` など分かりやすい名前 |
| **Expiration** | 任意（90日〜1年推奨） |
| **Repository access** | `Only select repositories` → このリポジトリを選択 |

**Permissions** セクションで以下を設定：

| カテゴリ | 権限 | 設定値 |
|---------|------|--------|
| **Repository permissions** | Contents | Read and write |
| **Repository permissions** | Discussions | Read and write |
| **Repository permissions** | Metadata | Read-only（自動で設定される） |

6. **Generate token** をクリック
7. 表示されたトークン（`github_pat_...`）を**必ずコピー**して安全な場所に保存

> ⚠️ トークンは一度しか表示されません。紛失した場合は再作成が必要です。

#### 3.3 トークンの有効期限管理

PATには有効期限があります。期限切れ前に以下を行ってください：

1. GitHub Settings > Developer settings > Personal access tokens で確認
2. 期限切れ30日前にリマインダーメールが届きます
3. **Regenerate token** で更新し、Secretsも更新

### Step 4: Slackの設定

#### 4.1 Slack Appの作成

1. [Slack API](https://api.slack.com/apps) にアクセス
2. **Create New App** をクリック
3. **From scratch** を選択
4. 以下を入力：
   - **App Name**: `EIC Bot`（任意）
   - **Pick a workspace**: 通知を受けたいワークスペースを選択
5. **Create App** をクリック

#### 4.2 Incoming Webhookの有効化

1. 左メニューの **Incoming Webhooks** をクリック
2. **Activate Incoming Webhooks** を **On** に切り替え
3. **Add New Webhook to Workspace** をクリック
4. 通知を投稿するチャンネルを選択（例：`#hr-insights`）
5. **Allow** をクリック
6. 生成された **Webhook URL** をコピー（`https://hooks.slack.com/services/...`）

> ⚠️ **注意**: Webhook URLは機密情報です。コードに直接書かず、必ずSecretsで管理してください。

### Step 5: GitHub Secretsの設定

#### 5.1 Secretsの登録

1. GitHubでリポジトリを開く
2. **Settings** > **Secrets and variables** > **Actions** をクリック
3. **New repository secret** をクリックして以下を登録：

| Secret名 | 値 | 説明 |
|----------|-----|------|
| `OPENAI_API_KEY` | `sk-...` | OpenAI APIキー |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/...` | Slack Webhook URL |
| `GH_PAT` | `github_pat_...` | Step 3で作成したPAT（**推奨**） |

> **Note**: `GH_PAT`を設定しない場合、自動生成の`GITHUB_TOKEN`にフォールバックしますが、Discussion作成が失敗する可能性があります。

#### 5.2 Variables（オプション）

デフォルト以外のモデルを使用する場合：

1. **Settings** > **Secrets and variables** > **Actions** の **Variables** タブ
2. **New repository variable** をクリック

| Variable名 | 値 | 説明 |
|------------|-----|------|
| `OPENAI_MODEL` | `gpt-4.1-mini` | 使用するOpenAIモデル |

### Step 6: 動作確認

#### 6.1 手動実行でテスト

1. リポジトリの **Actions** タブをクリック
2. 左メニューから **EIC Daily Collection** を選択
3. **Run workflow** ボタンをクリック
4. **Run workflow** を確認してクリック

#### 6.2 結果の確認

以下をすべて確認してください：

- ✅ **Actions**: ワークフローが緑色（成功）で完了
- ✅ **Discussions**: 新しいスレッド `[EIC][Daily] YYYY-MM-DD (JST)` が作成され、HIGH/TRENDコメントが投稿されている
- ✅ **Slack**: 指定チャンネルに通知が届く（Discussionへのリンク付き）
- ✅ **data/**: `items/YYYY-MM.jsonl` と `index.json` が更新されている

#### 6.3 よくある初期エラー

| 症状 | 原因 | 解決方法 |
|------|------|----------|
| Actions成功だがDiscussion未作成 | PAT未設定 or 権限不足 | Step 3を確認、GH_PATを登録 |
| `Resource not accessible by integration` | カテゴリがAnnouncement形式 | Step 2.2でOpen-endedに変更 |
| Slack通知にDiscussionリンクがない | Discussion作成失敗 | 上記を確認、リポジトリURLがフォールバック表示される |

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
│   ├── sources_high.yaml           # High Trust情報源（現在2ソース有効）
│   ├── sources_trend.yaml          # Trend情報源（現在2ソース有効）
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
  - key: mhlw_news           # 一意の識別子
    name: 厚生労働省 新着情報  # 表示名
    type: rss                # 取得方式（現在rssのみ）
    url: https://...         # RSSフィードURL
    publisher: 厚生労働省     # 発行者
    source_type: ministry    # 情報源タイプ（信頼度スコアに影響）
    language: ja             # 言語
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
| `OPENAI_API_KEY is not set` | Secretが未設定 | Step 5を確認 |
| `Discussion category not found` | カテゴリID誤り | Step 2.4を再実行 |
| `git push` が失敗 | リモートに変更がある | 自動でリベースされるため、再実行で解決 |

#### GitHub Discussionが作成されない

エラーログに `Resource not accessible by integration` が表示される場合、以下を順番に確認してください：

**確認1: Personal Access Token (PAT) の設定**

GitHub Actionsの自動生成トークンはDiscussion APIへのアクセスが制限されている場合があります。

1. Step 3の手順でPATを作成
2. リポジトリの **Settings** > **Secrets and variables** > **Actions**
3. `GH_PAT` という名前でSecretを登録
4. ワークフローを再実行

**確認2: ワークフロー権限設定**

1. リポジトリの **Settings** > **Actions** > **General** を開く
2. 下部の「**Workflow permissions**」セクションを確認
3. 「**Read and write permissions**」を選択
4. **Save** をクリック

**確認3: Discussionカテゴリのフォーマット**

「Announcement」タイプのカテゴリはGITHUB_TOKENからの投稿が制限されます。

1. リポジトリの **Discussions** タブを開く
2. 左サイドバーの **Categories** 横の ⚙️ をクリック
3. 「Daily Digest」カテゴリの ✏️（編集）をクリック
4. **Discussion Format** を「**Open-ended Discussion**」に変更
5. **Save** をクリック

**確認4: カテゴリIDの正確性**

間違ったカテゴリID（例：Q&AカテゴリのID）を設定している可能性があります。

1. Step 2.4のGraphQLクエリを再実行
2. `Daily Digest` カテゴリの `id` を確認
3. `config/categories.json` の値と一致しているか確認

#### Slack通知が届かない

1. Webhook URLが正しいか確認
2. Slackアプリがチャンネルに追加されているか確認
3. ワークフローのログで`Slack notification`の出力を確認
4. Discussion作成が失敗した場合でも、Slack通知は送信されます（警告メッセージ付き）

#### 記事が収集されない

1. RSSフィードが有効か確認（ブラウザでURLにアクセス）
2. 過去48時間以内の記事があるか確認
3. すべて既存記事として重複排除されていないか確認（`data/index.json`を確認）

### ログの確認

GitHub Actionsのログで詳細を確認できます：

1. **Actions** タブ > 該当のワークフロー実行をクリック
2. **collect** ジョブをクリック
3. 各ステップを展開してログを確認

### リトライ仕様

| 処理 | リトライ回数 | バックオフ |
|------|-------------|-----------|
| OpenAI API | 3回 | 指数（1→2→4秒） |
| GitHub GraphQL API | 3回 | 指数（2→4→8秒） |
| コンテンツ取得 | 2回 | 線形（2秒） |
| Slack通知 | 2回 | 線形（2秒） |

### PATの有効期限切れ

PATには有効期限があります。期限切れになると以下の症状が発生します：

- Actions成功だがDiscussion未作成
- エラーログに認証関連のメッセージ

**解決方法**:
1. GitHub Settings > Developer settings > Personal access tokens
2. 該当トークンの **Regenerate token** をクリック
3. 新しいトークンを `GH_PAT` Secretに再登録

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
