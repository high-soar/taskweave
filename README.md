---
type: project
title: Taskweave
description: コーディングエージェント向けのスケジュール調整ツール
tags: [project, scheduling, documentation]
status: draft
generated: { by: copilot/chat, at: 2026-09-10T12:09:08Z }
---

# Taskweave

コーディングエージェント向けのスケジュール調整ツールです。

現在は、実装に入る前の要件整理とツール選定を行っている段階です。スケジュール計算機能や YAML の原本形式は、まだ実装・確定していません。

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

計算エンジンには Python と OR-Tools、Python の依存関係管理には `uv` を使う構成を候補にしています。ただし、実装方式やデータモデルは今後の検討で変更する可能性があります。

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
- **エージェント向け CLI の体系と計画のレビュー・確定手順**: [Milestone 4](ROADMAP.md#milestone-4-エージェント向け-cli--レポーティング-agent-cli--reporting) で確定
- **複数メンバでのタスク担当・日単位より細かい計画**: 初期 MVP ではスコープ外（YAGNI 原則）とし、[将来の検討事項](ROADMAP.md#将来の検討事項初期スコープ外--yagni) として整理

## 開発ルール

人が開発するときに守るルールの原本は [人向け開発ルール](docs/development/rules.md) です。Issue 管理、SDD/TDD、PR レビュー、Git branch/worktree、品質ゲート、Git フックの手順をまとめています。目次は [開発ルールの目次](docs/development/index.md) を参照してください。

## 文書インデックス

通常のプロジェクト文書は [Taskweave 文書インデックス](index.md) から確認できます。タグ一覧は各文書の OKF frontmatter から生成されます。文書を追加・変更した場合は `npm run docs:index` と `npm run docs:check` を実行してください。

## 開発環境

VS Code でこのリポジトリを開き、`Dev Containers: Reopen in Container` を実行します。開発コンテナーには Node.js 24、npm、GitHub CLI、GitHub Copilot CLI、`uv`、`ripgrep` が含まれます。

初回起動時に `@github/copilot` は自動でグローバルインストールされます。Copilot CLI の履歴、Copilot Chat の履歴、Google Antigravity の履歴は Docker ボリュームに永続化されます。

現時点では、アプリケーションの Python 依存関係や計算エンジンはまだ導入していません。

## 開発時の確認

品質チェックと Git フックの手順は [人向け開発ルール](docs/development/rules.md) にまとめています。

## AI 向け設定

共通の AI 向けルールは [AGENTS.md](AGENTS.md) が正本です。GitHub Copilot と Google Antigravity の設定は、そこから参照する構成にしています。

実装を開始した後、確定したデータモデル、CLI、計算方式、運用手順をこの README に反映します。
