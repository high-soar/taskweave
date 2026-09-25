---
type: project
title: Taskweave
description: コーディングエージェント向けのスケジュール調整ツール
tags: [project, scheduling, documentation]
status: draft
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-25T02:25:00Z }
---

# Taskweave

コーディングエージェント向けのスケジュール調整ツールです。

原本 YAML スキーマと検証ツールの整備（Milestone 1）、Python / OR-Tools による計算エンジン MVP（Milestone 2）、実績反映と再計画ワークフロー（Milestone 3）、およびエージェント向け CLI & レポーティング（Milestone 4）が完了し、現在はスキーマ表現力 & 最適化強化（Milestone 5）の準備段階です。

## 目的

メンバの稼働割合、スキル、タスクの見積工数、依存関係、工程ごとの期限をもとに、チーム全体のスケジュール案を作成できるようにします。

Excel で手作業による調整を行う場合、タスクの順番や見積工数を変更したときに、後続タスクの開始日・終了日を連鎖的に修正する必要があります。また、メンバごとの一日の稼働上限を守りながら、プロジェクトや工程の期限を満たす調整も難しくなります。

Taskweave では、これらの条件をテキストベースの原本として管理し、コーディングエージェントが変更内容を解釈して再計画できる形を目指します。

## 現在検討している方針

- メンバやタスクなどの原本は YAML で管理する
- メンバごとの稼働割合を、プロジェクトに使える一日の容量として扱う
- タスクごとに見積工数、必要スキル、依存関係、期限を持たせる
- 実績を原本に追加し、指定した時点以降の未来だけを再計画する
- 休暇、見積工数の変更、作業範囲の変更をシナリオとして扱えるようにする
- 初期の計画単位は日、工数の単位は時間とする案を検討している
- 初期段階では、1つのタスクを同時に担当するメンバは1人とする案を検討している
- 必須スキルや期限は制約、得意・不得意や担当希望は優先度として扱う案を検討している

計算エンジンには Python と OR-Tools CP-SAT を採用し、`python/` 配下のパッケージとして `uv` で依存関係を管理しています。

## 想定している利用例

- メンバが急遽一週間休むため、残りのスケジュールを引き直す
- 作業範囲が変わって見積工数が増えたため、後続の予定を見直す
- タスクの実施順を変更したため、工程全体を再計画する
- 作業実績を反映し、現在時点から先の計画だけを更新する

## 未確定事項とマイルストーン対応

各設計課題や未確定事項は、[`ROADMAP.md`](ROADMAP.md) の各マイルストーンおよび将来バックログに整理して順次確定・実装を進めます。

- **原本 YAML のファイル分割とスキーマ定義**: [Milestone 1](ROADMAP.md#milestone-1-原本-yaml-スキーマ--検証ツール-data-schema--validation) で確定
- **日本の祝日やチーム固有の稼働日（カレンダー原本）の扱い**: [Milestone 1](ROADMAP.md#milestone-1-原本-yaml-スキーマ--検証ツール-data-schema--validation) および [Milestone 2](ROADMAP.md#milestone-2-計算エンジン-mvp-scheduling-engine-mvp) で確定
- **期限を守れない場合の診断結果と代替案の提示方法**: [Milestone 2](ROADMAP.md#milestone-2-計算エンジン-mvp-scheduling-engine-mvp) で確定
- **実績反映・起算日再計画および差分比較（Diff）・遅延原因診断**: [Milestone 3](ROADMAP.md#milestone-3-実績反映--再計画ワークフロー-replanning--actuals) で確定
- **エージェント向け CLI の体系と計画のレビュー・確定手順**: [Milestone 4](ROADMAP.md#milestone-4-エージェント向け-cli--レポーティング-agent-cli--reporting) で確定
- **複数メンバでのタスク担当・日単位より細かい計画**: 初期 MVP ではスコープ外（YAGNI 原則）とし、[将来の検討事項](ROADMAP.md#将来の検討事項初期スコープ外--yagni) として整理

## 利用方法（別プロジェクト・DevContainer からの利用）

現在、PyPI への一般公開前でも GitHub リポジトリから直接 CLI ツールとして実行またはインストールして利用できます。
DevContainer 等の隔離環境から利用する場合に便利です。

### 1. 一時実行（インストール不要）

`uvx` を使用すると、ツールを事前インストールせずに GitHub から直接実行できます。

```bash
uvx --from "git+https://github.com/high-soar/taskweave.git#subdirectory=python" taskweave --help
```

最新のコードを強制的に再取得したい場合は `--refresh` を付与します：

```bash
uvx --refresh --from "git+https://github.com/high-soar/taskweave.git#subdirectory=python" taskweave --help
```

### 2. コンテナや環境への常設インストール（uv tool）

独立した CLI コマンドとしてインストールし、常時 `taskweave` を実行できるようにします。

```bash
uv tool install "git+https://github.com/high-soar/taskweave.git" --subdirectory python
```

更新する場合は以下を実行します：

```bash
uv tool upgrade taskweave
```

### 3. 別プロジェクトの DevContainer 起動時に自動セットアップ

別プロジェクトの `.devcontainer/devcontainer.json` に設定しておくことで、コンテナ作成時に自動的にインストールされます。

```jsonc
{
  "postCreateCommand": "uv tool install git+https://github.com/high-soar/taskweave.git --subdirectory python",
}
```

### 4. プロジェクトの依存関係として追加（pip / uv）

```bash
# uv の場合
uv add "git+https://github.com/high-soar/taskweave.git" --subdirectory python

# pip の場合
pip install "git+https://github.com/high-soar/taskweave.git#subdirectory=python"
```

### 5. CLI コマンド例

```bash
# 原本 YAML の検証
taskweave validate data

# 原本 YAML から初期計画を計算（テキストサマリ表示）
taskweave plan data

# 初期計画を JSON でファイル保存（ベースライン計画の作成）
taskweave plan data --format json --output baseline.json

# 初期計画を Mermaid ガントチャート構文で出力・保存
taskweave plan data --format mermaid --output plan.mermaid

# 初期計画を Markdown テーブル形式で出力
taskweave plan data --format markdown

# 実績工数および進捗ステータスの安全な記録・追記
taskweave log 2026-09-08 data --member alice --task task-setup --hours 8.0 --remaining 0.0 --status completed

# 起算日を指定した再計画とベースライン差分（Diff）診断
taskweave replan data --as-of 2026-09-09 --baseline baseline.json

# 再計画後の進捗・残工数を Mermaid ガントチャートで出力
taskweave replan data --as-of 2026-09-09 --format mermaid

# 再計画差分および遅延診断を Markdown テーブル形式で出力・保存
taskweave replan data --as-of 2026-09-09 --format markdown --output replan.md

# 再計画結果の確認とベースライン確定保存（既存 baseline.json を安全に更新・バックアップ作成）
taskweave apply data --as-of 2026-09-09

# 差分サマリの確認のみ（ファイル更新なし）
taskweave apply data --as-of 2026-09-09 --dry-run

# 納期緩和推奨・担当者変更を原本 tasks.yaml にも自動反映
taskweave apply data --as-of 2026-09-09 --update-tasks
```

## 開発ルール

人が開発するときに守るルールの原本は [人向け開発ルール](docs/development/rules.md) です。Issue 管理、SDD/TDD、PR レビュー、Git branch/worktree、品質ゲート、Git フックの手順をまとめています。目次は [開発ルールの目次](docs/development/index.md) を参照してください。

## 文書インデックス

通常のプロジェクト文書は [Taskweave 文書インデックス](index.md) から確認できます。タグ一覧は各文書の OKF frontmatter から生成されます。文書を追加・変更した場合は `npm run docs:index` と `npm run docs:check` を実行してください。

## 開発環境

VS Code でこのリポジトリを開き、`Dev Containers: Reopen in Container` を実行します。開発コンテナーには Node.js 24、npm、GitHub CLI、GitHub Copilot CLI、`uv`、`ripgrep` が含まれます。

初回起動時に `@github/copilot` は自動でグローバルインストールされます。Copilot CLI の履歴、Copilot Chat の履歴、Google Antigravity の履歴は Docker ボリュームに永続化されます。

Python 計算エンジンの依存関係（OR-Tools 等）は `python/pyproject.toml` に定義され、`uv` により管理されます。テストは `npm test` または `cd python && uv run pytest` で実行できます。

## 開発時の確認

品質チェックと Git フックの手順は [人向け開発ルール](docs/development/rules.md) にまとめています。

## AI 向け設定

共通の AI 向けルールは [AGENTS.md](AGENTS.md) が正本です。GitHub Copilot と Google Antigravity の設定は、そこから参照する構成にしています。

実装を開始した後、確定したデータモデル、CLI、計算方式、運用手順をこの README に反映します。
