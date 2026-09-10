---
type: spec
title: OKF 文書管理とタグインデックス
description: Git 管理下の Taskweave 文書に OKF frontmatter を適用し、タグ集約インデックスと自動検査を提供する仕様
tags: [okf, documentation, validation]
status: accepted
issues: []
generated: { by: copilot/chat, at: 2026-09-10T12:09:08Z }
---

# OKF 文書管理とタグインデックス (002-okf-document-management)

## 1. 概要とユーザーストーリー

- **ユーザーストーリー**:
  - **As a**: 開発者およびコーディングエージェント
  - **I want**: リポジトリの文書を統一した OKF frontmatter とタグで管理したい
  - **So that**: 文書の種類と所在を機械的に把握し、タグから関連文書を検索できるようにするため
- **背景と目的**:
  Taskweave では仕様、開発ルール、ロードマップ、README などを Git 管理下の Markdown として扱います。文書ごとのメタデータを一定の形式に揃え、root `index.md` にタグと文書一覧を集約することで、人間とエージェントが必要な知識へ到達しやすくします。

## 2. 要件定義

### 2.1 機能要件 (FR: Functional Requirements)

- **FR-1 (OKF 対象文書)**: Git 管理下の Markdown のうち、通常のプロジェクト文書は OKF frontmatter の検査対象とする。対象には root の `README.md`、`AGENTS.md`、`ROADMAP.md`、`specs/`、`docs/` 配下の文書を含める。
- **FR-2 (ツール設定文書の境界)**: `.github/skills/`、`.github/agents/`、`.github/copilot-instructions.md` は各ツールのネイティブ frontmatter を使用するため、OKF の必須フィールドおよびタグ集約の対象外とする。検査 CLI はこれらのファイルを OKF 文書として扱わない。
- **FR-3 (frontmatter)**: OKF 対象文書は先頭に YAML frontmatter を持ち、`type`、`title`、`description`、`tags`、`generated` を必須とする。`index.md` も Taskweave 固有の運用として frontmatter を持つ。
- **FR-4 (タグ)**: `tags` は 1 個以上の文字列配列とし、各タグは小文字 ASCII の kebab-case（`[a-z0-9]+(?:-[a-z0-9]+)*`）で重複不可とする。`index.md` 自身のタグは集約元にしない。
- **FR-5 (タグインデックス)**: root `index.md` に、OKF 対象文書のタイトル、説明、リンク、タグ一覧、タグごとの文書一覧を生成する。タグ一覧からタグ別 section に移動できること。
- **FR-6 (生成と検査の分離)**: `npm run docs:index` は root `index.md` の生成領域を更新し、`npm run docs:check` は文書と生成結果を検査する。検査コマンドはファイルを変更しない。
- **FR-7 (Git 管理範囲)**: 文書の列挙には `git ls-files` を使用し、Git 管理外の Markdown は検査・タグ集約の対象外とする。
- **FR-8 (品質ゲート)**: `docs:check` を pre-push hook と GitHub Actions の品質チェックへ組み込む。

### 2.2 非機能要件 (NFR: Non-Functional Requirements)

- **NFR-1 (OKF 互換性)**: OKF v0.2 の `type` 必須、標準 YAML frontmatter、予約ファイルとしての `index.md`、拡張フィールド許容という考え方を維持する。`index.md` への frontmatter 必須化とタグ命名は Taskweave 固有の運用規約として扱う。
- **NFR-2 (決定性)**: 文書、タグ、タグ別文書は相対パスとタグの辞書順で安定して並び、同じ入力から同じ index を生成できること。
- **NFR-3 (診断可能性)**: 検査エラーはファイル名、frontmatter 内の行番号、問題のフィールドまたは index の状態を含めること。
- **NFR-4 (非破壊性)**: `docs:check` はファイルを書き換えず、`docs:index` は root `index.md` の生成マーカー内だけを更新すること。
- **NFR-5 (依存関係)**: 既存の `yaml` パッケージを利用し、frontmatter 検査のための新しい依存関係を追加しないこと。

## 3. データ構造・フォーマット定義

### 3.1 OKF 対象文書の frontmatter

```yaml
---
type: playbook
title: 人向け開発ルール
description: Taskweave の人間開発者が守る開発ルール
tags: [development, workflow]
status: stable
generated: { by: copilot/chat, at: 2026-09-10T11:11:30Z }
---
```

必須フィールドは次のとおりです。

| フィールド    | 型             | 必須     | 制約                                                |
| :------------ | :------------- | :------- | :-------------------------------------------------- |
| `type`        | string         | **必須** | 空でない小文字 kebab-case。`index` を含む。         |
| `title`       | string         | **必須** | 空でない人間向けタイトル。                          |
| `description` | string         | **必須** | 空でない 1 行要約。                                 |
| `tags`        | list of string | **必須** | 1 個以上、小文字 ASCII kebab-case、文書内重複不可。 |
| `generated`   | object         | **必須** | `by` と ISO 8601 UTC の `at` を持つ。               |

`status`、`verified`、`sources`、Issue や milestone などの拡張フィールドは OKF の拡張として保持できます。`status` を指定する場合は `draft`、`under-review`、`accepted`、`implemented`、`superseded`、`stable`、`deprecated` のいずれかとします。

`generated.by` は OKF のアクター表記に従い、`human:<id>`、`process:<id>`、または `<producer>/<model>` の形式とします。`generated.at` は `YYYY-MM-DDTHH:mm:ssZ` 形式とします。

### 3.2 root `index.md` の生成領域

root `index.md` は frontmatter と手書きの概要を持ち、以下のマーカー間を生成領域とします。

```markdown
<!-- BEGIN GENERATED: okf-index -->

## Documents

...

## Tags

...
<!-- END GENERATED: okf-index -->
```

生成領域には次を含めます。

- `Documents`: root `index.md` 自身とツール設定文書を除く OKF 文書一覧
- `Tags`: `index` type の文書を除く OKF 文書のタグ一覧
- 各タグの section: `Tag: <tag>` 見出しと該当文書一覧

タグリンクは `#tag-<tag>` 形式の見出しアンカーを使用します。生成領域外の本文は自動生成で変更しません。

## 4. 受入基準とテストシナリオ (TDD 連携)

### シナリオ 1: 正常な OKF 文書の検査

- **前提 (Given)**: Git 管理下の通常 Markdown が必須 frontmatter と正しいタグを持つ。
- **操作 (When)**: `npm run docs:check` を実行する。
- **期待結果 (Then)**: 終了コード `0` となり、文書の検査に成功する。

### シナリオ 2: frontmatter 不備の検知

- **前提 (Given)**: OKF 対象文書に frontmatter がない、YAML が壊れている、または必須フィールドが欠落している。
- **操作 (When)**: `npm run docs:check` を実行する。
- **期待結果 (Then)**: 終了コード `1` となり、ファイル名、行番号、問題のフィールドを含む診断を標準エラー出力へ返す。

### シナリオ 3: タグ規則違反の検知

- **前提 (Given)**: `Bad_Tag`、大文字、空配列、重複タグなどを持つ文書がある。
- **操作 (When)**: `npm run docs:check` を実行する。
- **期待結果 (Then)**: 終了コード `1` となり、該当タグと文書を含む診断を返す。

### シナリオ 4: root index の生成

- **前提 (Given)**: 複数の OKF 文書が存在する。
- **操作 (When)**: `npm run docs:index` を実行する。
- **期待結果 (Then)**: root `index.md` の生成領域に文書一覧、タグ一覧、タグ別一覧が決定的に出力され、生成領域外の本文は保持される。

### シナリオ 5: stale index の検知

- **前提 (Given)**: 文書の title、description、tags、または対象ファイルが変わり、root `index.md` を再生成していない。
- **操作 (When)**: `npm run docs:check` を実行する。
- **期待結果 (Then)**: 終了コード `1` となり、`npm run docs:index` の実行を案内する。

### シナリオ 6: Git 管理外 Markdown の除外

- **前提 (Given)**: Git 管理外の Markdown に不正な frontmatter がある。
- **操作 (When)**: `npm run docs:check` を実行する。
- **期待結果 (Then)**: そのファイルは検査結果とタグ集約に影響しない。

### シナリオ 7: ツール設定文書の互換性維持

- **前提 (Given)**: `.github/skills/`、`.github/agents/`、`.github/copilot-instructions.md` にツール固有の frontmatter がある、または frontmatter を持たない。
- **操作 (When)**: `npm run docs:check` を実行する。
- **期待結果 (Then)**: OKF 必須フィールドの不足として失敗せず、root index のタグ集約にも含めない。

## 5. 制約事項・スコープ外 (Out of Scope)

1. Git 管理外 Markdown の検査やタグ集約。
2. 一般の Markdown リンク全体の到達性検査。初版では生成 index のリンクと対象ファイル存在だけを検査する。
3. タグから本文内容を全文検索する動的 UI。初版は GitHub の見出しアンカーへ移動する静的なタグナビゲーションとする。
4. `.github/skills/`、`.github/agents/`、`.github/copilot-instructions.md` の frontmatter を OKF 共通形式へ変換すること。

## 6. 代替案と設計判断

- **index を手書きする案**: 文書追加やタグ変更のたびに更新漏れが起きるため採用しない。
- **pre-push で index を自動更新する案**: push 前に作業ツリーを書き換えるため採用しない。更新コマンドと検査コマンドを分離する。
- **全 Markdown に同じ必須 frontmatter を強制する案**: Copilot/Agent のネイティブ形式との互換性を損なうため採用しない。通常文書とツール設定文書をプロファイル分離する。
- **外部 frontmatter パーサーを追加する案**: 既存の `yaml` パッケージで必要な構文を処理できるため採用しない。
