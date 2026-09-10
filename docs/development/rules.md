---
type: playbook
title: 人向け開発ルール
description: Taskweave の人間開発者が仕様、実装、レビュー、Git 運用を進めるときの共通ルール
tags: [development, workflow, review, git]
status: stable
generated: { by: copilot/chat, at: 2026-09-10T15:32:30Z }
sources:
  - id: taskweave-readme
    resource: ../../README.md
    title: Taskweave README
  - id: taskweave-agents
    resource: ../../AGENTS.md
    title: Taskweave Project Agent Guidelines
---

# 人向け開発ルール

この文書を、Taskweave の人間開発者が守る開発ルールの正本とします。README.md と AGENTS.md にはこの文書への参照だけを置き、ルールの本文を重複させません。

## 1. 目標とユーザーストーリー

- **ロードマップ**: 全体方針とマイルストーンは [`ROADMAP.md`](../../ROADMAP.md) および GitHub Milestones で可視化します。
- **ユーザーストーリー**: 実現したい価値や機能は、[Issue テンプレート](../../.github/ISSUE_TEMPLATE/user_story.yml) を使用して GitHub Issues (`user-story` ラベル) として起票します。
- **タスク管理**: ストーリーを達成するための作業項目は、Issue 本文内の Tasklist (`- [ ]`) で管理し、Issue の過度な乱立を防ぎます。
- **DoR (準備完了の定義)**: 実装着手前に、ストーリーの目的（Who/What/Why）、受入基準（Acceptance Criteria）、および必要な仕様（[`specs/`](../../specs/)）が合意されていることを確認します。

## 2. 仕様策定とテスト駆動開発 (SDD & TDD)

1. **Spec（仕様策定・合意 - SDD）**: 詳細な原本 YAML スキーマや計算制約は [`specs/`](../../specs/) 配下に仕様書を作成して合意します。
2. **Test（テスト先行 - TDD Red）**: 仕様書の受入基準に基づき、失敗するテストを作成します。
3. **Code（最小実装 - TDD Green）**: テストを通過させるための最小限の実装を行います（YAGNI 原則の遵守）。
4. **Refactor（品質改善 - TDD Refactor）**: テストが通過する状態を維持しながら、コードの品質・構造を整理します。
5. **DoD (完了の定義)**: 全受入基準のテスト通過、品質チェック全通過、仕様・ドキュメント更新を確認し、PR 概要に `Closes #<Issue番号>` を記載して PR を作成します。CI が正常終了することを確認した上で、人間のレビューおよび承認・マージ指示を待ちます。エージェントは指示されない限り勝手にマージしてはなりません。

現行の開発基盤では `node --test` によるテストを実施し、今後の計算エンジン（Python）導入時は `pytest` を用いてテスト駆動開発を行います。

## 3. プルリクエストのレビューコメント

### 3.1 レビュー記録の正本

- PR のレビュー結果、指摘への回答、修正方針、再レビュー結果、および未解決リスクは、対象 PR のコメントに記録します。チャット、ターミナル出力、Issue、口頭でのやり取りだけを完了の根拠にしません。
- PR 外で議論した内容を採用する場合は、決定事項と次のアクションを PR のコメントへ要約してからレビューを完了します。
- 1 回のレビューで関連する指摘は 1 件のトップレベルコメントにまとめ、指摘には安定した番号（例: `[R1]`）を付けます。追加の指摘は既存コメントを編集せず、同じ PR の新しいコメントに追記します。

### 3.2 指摘と回答

- **指摘を先に書く**: 概要や感想より先に、確認できたバグ、回帰、リスク、テスト不足を重要度順に記載します。可能な場合はファイルと行を示します。
- **修正可能な内容にする**: 各指摘に影響、再現条件、期待する動作、修正の方向を含めます。根拠のない懸念を不具合として扱いません。
- **GitHub の機能を使い分ける**: 複数の指摘をまとめる場合や自分が作成した PR には `gh pr comment` でトップレベルコメントを投稿します。1 行に限定される問題だけはインラインコメントにします。正式なレビュー状態を付ける権限がある人だけが `gh pr review --comment` または `gh pr review --request-changes` を使います。
- **回答も PR コメントで行う**: PR 作成者または修正担当者は、各指摘の番号を参照して、対応方針（修正、受け入れ、見送り）、理由、変更コミット、検証結果、残るリスクを同じ PR のコメントまたはレビュー・スレッドへ記載します。ローカル修正やコミットメッセージだけでは回答済みとしません。
- **再レビューを記録する**: 修正後はレビュアーが同じ PR の更新された差分と検証結果を確認し、解決した指摘と未解決の指摘をコメントで明示します。指摘を解決済みとするのは、修正と検証を確認した後に限ります。

### 3.3 レビュー完了条件

- 承認またはマージを依頼する前に、すべての指摘へ回答があり、未解決リスクと対応予定が PR コメントに明示され、必要なテストと CI の結果が記録されていることを確認します。
- エージェントはレビュー結果の整理、PR コメントの投稿、修正内容と検証結果への回答を行えますが、正式な承認とマージは人間が行います。エージェントは明示的な指示なしに `approve`、`merge`、またはそれに相当する操作を行いません。
- **無関係な状態を混ぜない**: PR のリビジョンで再現しないローカル限定の失敗、既存の作業ツリー変更、環境問題は、PR の問題として報告しません。

## 4. Git ブランチと worktree

- **作業開始前に確認する**: `git fetch origin` の後、`git branch --show-current`、`git log --oneline origin/main..HEAD`、`git diff --name-status origin/main...HEAD`、`git worktree list` で現在のブランチ、worktree、未整理の差分を確認します。別の Issue 用ブランチにいる、意図しない差分がある、または対象ブランチが別の worktree で使用中の場合は、編集を始めずに切り分けます。
- **専用 worktree を作成する**: Issue 対応は 1 Issue / 1 PR / 1 作業ブランチ / 1 worktree とし、`origin/main` を起点に専用 worktree と `feature/issue-<number>-<slug>` または `fix/issue-<number>-<slug>` を作成します。例: `git worktree add -b feature/issue-<number>-<slug> .worktrees/taskweave-<number>-<slug> origin/main`。Issue に紐づかないリポジトリ設定・文書などの保守作業は `chore/<slug>` を使います。別の Issue 用ブランチや worktree を再利用せず、`feat/` と `feature/` を混在させません。
- **`main` へ直接作業・push しない**: `main` の worktree は確認や更新にのみ使用し、実装・コミット・push は専用 worktree の作業ブランチで行います。レビュー修正も同じ worktree と PR ブランチへ追加します。
- **PR 前に起点を再確認する**: 現在のブランチ名と `origin/main...HEAD` の差分を確認し、無関係なコミットやファイルが含まれていないことを確認してから commit、push、PR 作成を行います。
- **PR の承認とマージは人間が行う**: PR のレビュー、承認、およびマージの権限は人間（開発者・レビュアー）にあります。エージェントは PR 作成と CI の正常終了確認までを担当し、ユーザーから明示的な指示がない限り、自律的に PR をマージしてはなりません。
- **マージ後に整理する**: PR がマージされたら `main` を更新し、作業 worktree を離れてから `git worktree remove .worktrees/taskweave-<number>-<slug>` で削除し、不要になったローカルおよびリモートの作業ブランチも削除します。未コミットの変更が残っている場合は、削除前に内容を確認します。

## 5. 品質ゲートと Git フック

依存関係を導入し、リポジトリの品質チェックを実行します。

```sh
npm install
npm run docs:check
npm run format:check
npm run lint
npm test
npm run typecheck
npm run validate -- examples/basic
```

整形が必要な場合は `npm run format` を実行します。

文書を追加・変更した場合は、Git に追加した後で root index を更新して検査します。

```sh
npm run docs:index
npm run docs:check
```

`npm install` または `npm ci` を実行すると、リポジトリ管理下の [`.githooks/pre-push`](../../.githooks/pre-push) がこの clone の Git 設定に登録されます。以降の `git push` では、整形チェック、Lint、テスト、型チェックが実行されます。

既存の clone で再設定する場合は `npm run prepare` を実行します。プルリクエストと `main` への push では、同じチェックが GitHub Actions により実行されます。
