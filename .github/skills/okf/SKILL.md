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
4. **Progressive Disclosure**: Folders use `index.md` to summarize contents so agents can navigate hierarchy without loading the entire corpus at once.
5. **Graph-Shaped Links**: Documents cross-reference using standard Markdown links.

---

## 2. Frontmatter Specification (OKF v0.2)

Every OKF document MUST start with a YAML frontmatter block delimited by `---`.

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

- **`issue`**: 紐づく GitHub Issue 番号（例: `issue: 1`）
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
  - ディレクトリ配下の概要一覧として `index.md` を配置し、各コンセプトの `title` と `description` を一覧化する。
  - エージェントは `index.md` を参照することで、全ドキュメントをメモリに展開せずに必要なドキュメントへアクセスできる。

---

## 6. チェックリスト

- [ ] ドキュメント先頭が `---` で始まる有効な YAML フロントマターであること。
- [ ] `type` フィールドが指定されていること。
- [ ] `title` および `description`（1行要約）が記載されていること。
- [ ] 日時がすべて ISO 8601 UTC 形式（例: `2026-09-08T16:00:00Z`）であること。
- [ ] アクターが `human:<id>` または `<agent>/<model>` の形式であること。
