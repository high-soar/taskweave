---
name: okf
description: Use this skill when creating, editing, reviewing, or structuring Markdown knowledge documents and specifications according to Open Knowledge Format (OKF v0.2), including YAML frontmatter, actor conventions, trust tiers, and progressive disclosure.
---

# Open Knowledge Format (OKF v0.2) Skill

This skill defines the rules and procedures for authoring and maintaining Markdown knowledge documents and specifications in accordance with **Open Knowledge Format (OKF v0.2)**.

OKF is a vendor-neutral, Git-native format that formalizes the "LLM-wiki pattern" using Markdown files with standardized YAML frontmatter.

---

## 1. Core Principles

1. **Human & Agent Readable**: Plain Markdown files with YAML frontmatter. No proprietary SDKs, databases, or runtime required.
2. **Trust & Provenance First-Class**: Every document explicitly records who generated it (`generated`), who verified it (`verified`), and where the knowledge originates (`sources`).
3. **Minimally Opinionated & Extensible**: Only `type` is strictly required. Additional custom fields (e.g., `issue`, `milestone`) are allowed and preserved.
4. **Progressive Disclosure**: Use `index.md` as a local summary when a directory benefits from one; it is optional.
5. **Graph-Shaped Links**: Documents cross-reference using standard Markdown links.

---

## 2. Frontmatter Specification (OKF v0.2)

Every OKF concept document MUST start with a YAML frontmatter block delimited by `---` (reserved files such as `index.md` and `log.md` are exempt).

```yaml
---
type: spec # REQUIRED. Concept type (e.g. spec, architecture, playbook, concept)
title: 原本 YAML スキーマ定義 # RECOMMENDED. Human-readable display name
description: メンバ・タスク・制約の原本データモデルおよび検証ルールの仕様定義 # RECOMMENDED. One-line summary
tags: [schema, yaml, milestone-1] # RECOMMENDED. Cross-cutting categorization
status: draft # OPTIONAL. draft | under-review | accepted | implemented | superseded
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-08T16:00:00Z } # OPTIONAL. Authoring actor and time
verified: { by: human:high-soar, at: 2026-09-08T16:30:00Z } # OPTIONAL. Sign-off / verification event
---
```

### 2.1 Frontmatter Fields Reference

| フィールド        | 必須     | 型          | 説明                                                                                                                                      |
| :---------------- | :------- | :---------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| **`type`**        | **必須** | string      | ドキュメントの種別（例: `spec`, `architecture`, `concept`, `playbook`, `metric`）。                                                       |
| **`title`**       | 推奨     | string      | 人間が読む表示名。                                                                                                                        |
| **`description`** | 推奨     | string      | 1 行の要約。`index.md` 生成や検索スニペットに利用。                                                                                       |
| **`tags`**        | 推奨     | list of str | 分類・検索用タグ（小文字・ハイフン区切り推奨）。                                                                                          |
| **`resource`**    | 任意     | URI / path  | 物理的なリソース（DBテーブル、APIエンドポイント、ファイル等）がある場合の識別子。                                                         |
| **`status`**      | 任意     | string      | ライフサイクル状態。OKF標準: `draft`, `stable`, `deprecated`。仕様書では `under-review`, `accepted`, `implemented`, `superseded` を併用。 |
| **`generated`**   | 推奨     | map         | 最新の実質的変更を行ったアクターと日時 `{ by: <actor>, at: <ISO 8601 UTC> }`。                                                            |
| **`verified`**    | 任意     | map / list  | 内容を検証・承認したイベント `{ by: <actor>, at: <ISO 8601 UTC> }`。                                                                      |
| **`sources`**     | 任意     | list of map | 導出元の参照リソース（`id`, `resource`, `title`, `author`, `last_modified` 等）。                                                         |
| **`stale_after`** | 任意     | ISO 8601    | この日時以降は陳腐化（stale）と判定される絶対日時。                                                                                       |

---

## 3. アクター表記規則 (Actor Convention)

`generated.by` や `verified.by` には、アクションを実行した主体を以下の形式で記述します。

- **人間 (Human)**: `human:<user_id>` (例: `human:high-soar`)
- **AI エージェント (Agent)**: `<producer>/<model_or_version>` (例: `antigravity/gemini-3.8-flash`, `copilot/chat`)
- **自動プロセス (Process)**: `process:<id>` (例: `process:ci-validator`, `process:nightly-test`)

### トラストティア（信頼度レベル）の導出

ドキュメントの信頼度は `verified` フィールドから以下のように判定されます：

1. **`unverified`** (未検証): `verified` が存在しない。
2. **`machine-confirmed`** (機械検証済): `verified` が非人間（`process:` やエージェント）のみ。
3. **`human-reviewed`** (人間レビュー・承認済): `verified` に少なくとも 1 つの `human:<id>` が含まれる。

---

## 4. 仕様書 (`type: spec`) での運用プラクティス

Taskweave の仕様書（`specs/*.md`）では、OKF を以下のように活用します。

### 4.1 拡張フィールド

- **`issues` / `issue`**: 紐づく GitHub Issue 番号。複数 Issue にまたがる仕様の場合は `issues: [1, 2]`、単一の場合は `issues: [1]` または `issue: 1` を使用する。
- **`milestone`**: 紐づくマイルストーン（例: `milestone: M1`）

### 4.2 ライフサイクルと更新手順

1. **起草時 (`draft`)**:
   - エージェントが仕様を起草: `generated: { by: antigravity/gemini-3.8-flash, at: <now> }`、`status: draft`。
2. **レビュー・合意時 (`accepted`)**:
   - ユーザーとの仕様合意が完了したら、`status: accepted` に更新。
   - レビュー承認を記録: `verified: { by: human:<user_id>, at: <now> }` を付与。
3. **実装完了時 (`implemented`)**:
   - TDD テスト・実装が完了し品質ゲート通過後、`status: implemented` に更新。
4. **仕様改定時**:
   - 軽微な更新: `specs/xxx.md` を更新し、`generated.at` を更新。
   - 大規模・破壊的改定: 新仕様書を作成し、旧仕様書を `status: superseded` に更新して新仕様へのリンクを記載。

---

## 5. 相互リンクと漸進的開示 (Progressive Disclosure)

- **クロスリンク**:
  - ドキュメント間の参照には標準 Markdown リンクを使用する。
  - ルート相対パス（例: `[YAML Schema](/specs/001-yaml-schema.md)`）または相対パス（`./001-yaml-schema.md`）を使用する。
- **`index.md` の運用**:
  - ディレクトリ内の文書を短く案内する必要がある場合にだけ `index.md` を配置し、各コンセプトの `title` と `description` を一覧化する。
  - 文書数が少ないディレクトリや既存の README で十分なディレクトリには、新しい `index.md` を追加しない。
  - 書式は公開 OKF 仕様（§6）に準拠したフラットな 1 行形式（`* [<title>](<filename>) - <description>`）とする。
  - `index.md` は予約ファイル（目次）であり、YAML フロントマターは持たない（全ドキュメント必須ルールの例外）。
  - エージェントは `index.md` を参照することで、全ドキュメントをメモリに展開せずに必要なドキュメントへアクセスできる。

---

## 6. Taskweave での運用

この節は OKF v0.2 の拡張ではなく、Taskweave リポジトリ固有の運用ルールです。公式定義と互換性を保ちながら、文書の対象範囲、タグ、検査方法を固定します。

### 6.1 文書プロファイル

- `README.md`、`AGENTS.md`、`ROADMAP.md`、`specs/`、`docs/` 配下の Git 管理 Markdown は OKF 文書として扱う。
- 通常の OKF 文書には `type`、`title`、`description`、`tags`、`generated` を必須とする。
- root `index.md` は Taskweave の生成対象として `type: index` などの frontmatter を付ける。
- サブディレクトリの `index.md` は必要な場合だけ置く任意のナビゲーション文書とし、置く場合は Taskweave の通常 OKF 文書として frontmatter を付ける。
- `.github/skills/`、`.github/agents/`、`.github/copilot-instructions.md` は Copilot、Antigravity、または VS Code のネイティブ形式を優先し、OKF 必須フィールドとタグ集約の対象外とする。
- 新しいツール固有 Markdown を追加する場合は、OKF 文書として分類できるか、既存ツール形式を維持する除外対象かを決める。

### 6.2 frontmatter とタグの更新

1. 新しい通常文書を作るときは、先頭に固定形式の YAML frontmatter を追加する。
2. `tags` は小文字 ASCII の kebab-case（例: `git-worktree`）で 1 個以上指定し、同じ文書内で重複させない。
3. 文書の内容、タイトル、説明、タグを実質的に変更したときは `generated.at` を更新する。単なる整形でも frontmatter の値を変更した場合は更新する。
4. `generated.by` は `human:<id>`、`process:<id>`、または `<producer>/<model>` のいずれかを使用する。
5. `index.md` のタグ一覧は手入力しない。各文書の `tags` が正本であり、root `index.md` はそこから生成する。

### 6.3 タグ検索と index 更新

- root [`index.md`](../../index.md) の `Tags` 一覧からタグを選ぶと、同じファイル内のタグ別文書一覧へ移動できる。
- 文書を追加・削除したり、`title`、`description`、`tags` を変更したりした場合は `npm run docs:index` を実行する。
- `<!-- BEGIN GENERATED: okf-index -->` と `<!-- END GENERATED: okf-index -->` の間は生成領域であり、手動編集しない。
- `npm run docs:check` は frontmatter、タグ、生成 index の一致を検査する。index は自動修正せず、古い場合は `npm run docs:index` を案内して失敗する。
- 検査対象は `git ls-files` で列挙される Git 管理 Markdown であり、Git 管理外の Markdown は対象外とする。

### 6.4 推奨ワークフロー

```sh
# 文書を追加・編集した後
npm run docs:index
npm run docs:check

# push 前に通常の品質ゲートも実行
npm run format:check
npm run lint
npm test
npm run typecheck
```

`docs:check` は `.githooks/pre-push` と GitHub Actions でも実行される。新しい文書を Git に追加した後、index を再生成してから commit する。

## 7. チェックリスト

- [ ] `index.md` を追加する必要性を確認し、追加する場合は Taskweave の通常 OKF 文書として先頭に有効な YAML フロントマターを置くこと。
- [ ] `type` フィールドが指定されていること。
- [ ] `title` および `description`（1行要約）が記載されていること。
- [ ] 日時がすべて ISO 8601 UTC 形式（例: `2026-09-08T16:00:00Z`）であること。
- [ ] アクターが `human:<id>` または `<agent>/<model>` の形式であること。
- [ ] Taskweave の通常文書では `tags` が小文字 ASCII kebab-case で重複していないこと。
- [ ] 文書追加・変更後に `npm run docs:index` と `npm run docs:check` を実行していること。
