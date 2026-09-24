---
type: spec
title: エージェント CLI & レポーティング仕様
description: 原本初期計画コマンド (taskweave plan)、可視化出力 (Mermaid ガントチャート・Markdown 表)、実績・進捗記録 (taskweave log)、および再計画ベースライン確定・原本更新ワークフロー (taskweave apply) の仕様
tags: [cli, reporting, mermaid, markdown, plan, log, apply, milestone-4]
status: implemented
issues: [40, 41, 42, 43]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-24T16:45:00Z }
verified: { by: human:high-soar, at: 2026-09-21T11:35:23Z }
---

# エージェント CLI & レポーティング仕様 (005-agent-cli-and-reporting)

## 1. 概要とユーザーストーリー

- **ユーザーストーリー**:
  - **ストーリー 1 (Issue #40: 原本初期計画コマンド `taskweave plan`)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: 原本 YAML（`members.yaml`, `tasks.yaml`, `calendar.yaml`）から初期スケジュール（担当者、開始日、終了日、Makespan 等）を `taskweave plan` コマンドで一括計算・出力したい
    - **So that**: 実績反映や再計画（replan）の起点となるベースライン計画を CLI から手軽に立案・保存し、エージェントや他ツールとの連携を円滑にするため
  - **ストーリー 2 (Issue #41: スケジュールおよび差分の可視化出力)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: `taskweave plan` および `taskweave replan` の実行結果を、Mermaid ガントチャート構文や Markdown 表形式（`--format mermaid`, `--format markdown`）で直接出力したい
    - **So that**: GitHub Issue / PR のコメント、進捗レポート、ドキュメントにそのまま貼り付けて人間やチームと視覚的にスケジュールや差分を共有できるようにするため
  - **ストーリー 3 (Issue #42: 実績・進捗の記録インターフェース `taskweave log`)**:
    - **As a**: 開発メンバーおよびコーディングエージェント
    - **I want**: `actuals.yaml` を手動で直接テキスト編集する代わりに、`taskweave log` コマンドを通じて作業日・メンバー・タスク・実績時間・残工数・進捗ステータスを安全に記録・追記したい
    - **So that**: 手動編集による構文エラーや論理不正（未定義IDの参照、休暇日での稼働記録など）を防ぎ、日常の実績入力を素早く正確に行うため
  - **ストーリー 4 (Issue #43: 再計画差分確認とベースライン確定・原本更新ワークフロー `taskweave apply`)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: 再計画（replan）で得られたスケジュール案や遅延診断を確認した上で、新スケジュールを確定ベースラインとして保存・原本更新するコマンド（`taskweave apply`）を実行したい
    - **So that**: 再計画の試算（what-if シミュレーション）と正式な計画確定を安全に分離し、Git コミットと連動した一貫性のある更新管理を行うため
- **背景と目的**:
  Milestone 1〜3 において、原本 YAML スキーマ、OR-Tools CP-SAT スケジューリング計算エンジン、および実績反映・再計画（`replan`）エンジンを構築しました。
  本仕様（Milestone 4）では、これら基盤ロジックをコーディングエージェントおよび人間が円滑に操作できるよう、統一的な CLI サブコマンド体系（`plan`, `replan`, `log`, `apply`）と可視化レポーティング（Mermaid / Markdown）を確立します。

---

## 2. 要件定義

### 2.1 機能要件 (FR: Functional Requirements)

#### 原本初期計画コマンド (`taskweave plan` - Issue #40)

- **FR-1 (`taskweave plan` コマンドライン構文)**:
  - 基本構文: `taskweave plan [directory] [--start-date <YYYY-MM-DD>] [--format text|json] [--output <path>]`
  - `directory`: 原本 YAML ファイル（`members.yaml`, `tasks.yaml`, `calendar.yaml`）が配置されたディレクトリ。省略時は `data`。
  - `--start-date <YYYY-MM-DD>`: プロジェクト開始日。省略時は実績データ中の最古作業ログ日（`earliest_log_date`）、それも存在しない場合は実行日当日（`datetime.date.today()`）を起点とする。
  - `--format`: 出力形式を指定。`text`（デフォルト: 人間向けテキストサマリ）または `json`（JSON 構造化データ）。（※Issue #41 にて `markdown`, `mermaid` を追加拡張）。
  - `--output <path>`: 指定されたパスにフォーマット結果を出力・保存する。
- **FR-2 (事前原本バリデーション連携)**:
  - スケジュール計算の実行前に、指定ディレクトリの原本 YAML に対して `validate_directory` を実行すること。
  - 構文エラーまたは論理整合性エラーが存在する場合、標準エラー出力（`stderr`）に対象ファイル・行番号・エラー内容を出力し、終了コード `1` で処理を中断すること。
- **FR-3 (初期スケジュール計算エンジン実行)**:
  - 検証通過後、原本データ（members, tasks, calendar）を `taskweave.engine.solve_schedule` に渡し、制約を満たすスケジュールを算出すること。
  - プロジェクト開始日は `--start-date` が指定された場合はその日付、未指定の場合は実績データ中の最古作業ログ日（`earliest_log_date`）、それも存在しない場合は実行日当日（`datetime.date.today()`）を起点とすること。
  - 最適解または実行可能解が得られた場合、各タスクの割当担当者、開始日、終了日、稼働日数、遅延日数、および全体の Makespan を出力すること。計算不能または解なし（INFEASIBLE 等）の場合は標準エラー出力にメッセージを出力して終了コード `1` で終了すること。
  - 納期制約違反やボトルネックが存在する場合、ソフト制約によるペナルティ最小化解と遅延タスク・納期緩和推奨（recommendations）を診断情報として出力すること。
- **FR-4 (`--format text` 出力形式)**:
  - スケジュールのステータス、全体の Makespan（実稼働日数および実日付範囲）、タスクごとの割当・日程・工数概要を読みやすいテキスト形式で出力すること。
  - 例:
    ```text
    Taskweave Schedule Plan Report
    ==============================
    Status: OPTIMAL
    Makespan: 10 workdays (2026-09-08 ~ 2026-09-22)

    Tasks:
      - task-setup: alice (2026-09-08 ~ 2026-09-08, 1 workdays, 8.0h)
      - task-api: alice (2026-09-09 ~ 2026-09-10, 2 workdays, 16.0h)
      - task-frontend: bob (2026-09-09 ~ 2026-09-10, 2 workdays, 16.0h)
      ...
    ```
- **FR-5 (`--format json` 出力形式)**:
  - `taskweave.engine.solve_schedule` の返却辞書と完全互換の JSON 形式を出力すること。
  - 出力された JSON は、`taskweave replan --baseline <path>` のベースライン入力としてそのまま読み込める構造であること。
- **FR-6 (`--output <path>` 保存機能)**:
  - `--output` が指定された場合、指定されたファイルパス（親ディレクトリが存在しない場合は作成）にフォーマット済みテキストまたは JSON を保存すること。
  - 保存成功時、標準出力に保存完了メッセージを表示するか、標準出力への出力とファイル保存を両立すること。

#### 可視化レポーティング (`--format mermaid|markdown` - Issue #41)

- **FR-7 (Mermaid ガントチャート出力)**:
  - `taskweave plan --format mermaid` および `taskweave replan --format mermaid` により、GitHub Markdown で直接プレビュー可能な `gantt` 構文を出力すること。
  - ヘッダー仕様:
    ```mermaid
    gantt
        title Taskweave Schedule Plan (または Taskweave Replanned Schedule)
        dateFormat YYYY-MM-DD
        axisFormat %Y-%m-%d
        excludes weekends
    ```
  - `taskweave plan --format mermaid`:
    - 担当者ごとに `section <assignee>` を設ける（未割当は `section unassigned`）。
    - タスクの開始日・終了日、および先行依存関係（`depends_on` がある場合は `after <dep1> <dep2>`）を反映すること。
    - 納期超過タスク（`delay_days > 0`）には `crit` タグを付与すること。
  - `taskweave replan --format mermaid`:
    - 担当者ごとに `section <assignee>` を設ける。
    - 再計画後のスケジュールにおいて、タスクの進捗ステータスおよび実績・残工数を反映すること:
      - 完了タスク (`completed` / `remaining_hours == 0`): `done` タグを付与（例: `task-setup [完了] :done, task-setup, 2026-09-08, 2026-09-08`）。
      - 進行中タスク (`in_progress`):
        - 実績が存在する場合 (`total_logged_hours > 0`): 実績期間を `done` として可視化（例: `task-api [実績] :done, task-api-actual, 2026-09-09, 2026-09-09`）。
        - 残工数が存在する場合 (`remaining_hours > 0`): 残作業日程を `active`（遅延時は `crit, active`）として可視化（例: `task-api [残工数] :active, task-api, 2026-09-10, 2026-09-12`）。
      - 未着手タスク (`not_started`): 残作業日程を通常バー（遅延時は `crit`）として可視化。
- **FR-8 (Markdown テーブル出力)**:
  - `taskweave plan --format markdown`:
    - `# スケジュール計画レポート (Taskweave Schedule Plan)`
    - `## 全体サマリ`: ステータス、Makespan（稼働日数・期間）、タスク総数、総工数。
    - `## タスク一覧`: タスクID、担当者、開始日、終了日、稼働日数、見積工数、納期、遅延（日）。
    - `## 担当者別工数サマリ`: 担当者、割当タスク数、合計工数。
    - （遅延タスクまたは納期緩和推奨が存在する場合）`## 遅延タスク診断` および `## 納期緩和推奨 (Recommendations)`。
  - `taskweave replan --format markdown`:
    - `# スケジュール再計画レポート (Taskweave Replanning Report)`
    - `## ベースライン比較サマリ`: Makespan（ベースライン vs 再計画 vs スリップ日数）、タスク総数、遅延タスク数。
    - `## 遅延タスク診断 (Delayed Tasks & Diagnostics)`: 遅延タスクID、担当者、ベースライン終了日、再計画終了日、スリップ日数、主原因、詳細。遅延なしの場合はその旨を明記。
    - `## 再計画タスク一覧 (Replanned Tasks)`: タスクID、担当者、ステータス、開始日、終了日、稼働日数、実績工数、残工数、納期、遅延日数。
    - （納期緩和推奨が存在する場合）`## 納期緩和推奨 (Recommendations)`: タスクID、現納期、推奨納期、遅延日数、推奨内容。
- **FR-8.1 (`taskweave replan` の `--output <path>` 対応)**:
  - `replan` サブコマンドにおいても `--output <path>` オプションをサポートし、指定パスにフォーマット済みテキスト（text / json / mermaid / markdown）を保存し、標準出力にも出力すること。

#### 実績記録インターフェース (`taskweave log` - Issue #42)

- **FR-9 (`taskweave log` コマンド構文)**:
  - 構文: `taskweave log <date> --member <id> --task <id> --hours <h> [--remaining <h>] [--status <status>] [directory]`
  - `actuals.yaml` の `work_logs` に稼働ログを追記または更新し、オプション指定時は `task_progress` も更新すること。
  - 新規作成時は Issue #38 合意方針に従い `actuals:` ルートキー付き形式を推奨デフォルトとし、既存ファイルが存在する場合はその構造を踏襲すること。
  - メンバ不在日での作業記録や未定義タスク参照などの論理違反を事前に検証し不正を防止すること。

#### ベースライン確定・原本更新 (`taskweave apply` - Issue #43)

- **FR-10 (`taskweave apply` コマンド構文)**:
  - 構文: `taskweave apply [directory] --as-of <date>`
  - 再計画結果を確定し、プロジェクトの公式なベースラインファイル（`baseline.json`）を安全に更新・保存すること。

---

### 2.2 非機能要件 (NFR: Non-Functional Requirements)

- **NFR-1 (決定論的再現性)**:
  - 同一の原本 YAML データに対して `taskweave plan` を実行した場合、常に同一のスケジュール計算結果が得られること（CP-SAT の決定論的 Warm-start ヒントおよび単一ワーカー設定の継承）。
- **NFR-2 (エラーハンドリングと終了コード)**:
  - 正常終了: `0`
  - 原本検証エラー・計算不能・実行時エラー: `1`
  - CLI 引数不正: `2`
- **NFR-3 (エージェント親和性)**:
  - `--format json` による構造化データ出力、および `--format markdown` / `mermaid` によるコメント埋め込み用テキスト出力を完備し、AI エージェントが計画を自動解釈・報告できるようにすること。

---

## 3. データ構造・スキーマ定義

### 3.1 `taskweave plan --format json` 出力スキーマ

```json
{
  "status": "OPTIMAL",
  "project_start_date": "2026-09-08",
  "as_of_date": null,
  "makespan_workdays": 10,
  "tasks": {
    "task-setup": {
      "assigned_to": "alice",
      "start_date": "2026-09-08",
      "end_date": "2026-09-08",
      "workdays_count": 1,
      "actual_active_days": 1,
      "estimate_hours": 8.0,
      "remaining_hours": 8.0,
      "total_logged_hours": 0.0,
      "status": "not_started",
      "daily_hours": {
        "2026-09-08": 8.0
      },
      "deadline": null,
      "delay_days": 0
    }
  },
  "member_daily_work": {
    "alice": {
      "2026-09-08": 8.0
    }
  },
  "diagnostics": {
    "is_deadline_violated": false,
    "total_delay_workdays": 0,
    "delayed_tasks": [],
    "recommendations": []
  }
}
```

---

## 4. 受入基準とテストシナリオ (TDD 連携: Issue #40)

### シナリオ 1: 正常系（引数なし・デフォルトディレクトリ `data` の初期計画表示）

- **前提 (Given)**: カレントディレクトリ下の `data/` に有効な `members.yaml`, `tasks.yaml`, `calendar.yaml` が存在する。
- **操作 (When)**: `taskweave plan` を引数なしで実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 標準出力に `Taskweave Schedule Plan Report` およびステータス、Makespan、タスク一覧のテキストサマリが出力される。
  - 標準エラー出力は空である。

### シナリオ 2: ディレクトリ指定および `--format json` 出力

- **前提 (Given)**: `examples/basic/` に原本データが存在する。
- **操作 (When)**: `taskweave plan examples/basic --format json` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 標準出力が有効な JSON 文字列であり、`status`, `makespan_workdays`, `tasks` などのキーが含まれている。

### シナリオ 3: `--output <path>` による計画ファイルの保存

- **前提 (Given)**: 有効な原本データが存在し、出力先パス `output/baseline.json` を指定する。
- **操作 (When)**: `taskweave plan examples/basic --format json --output output/baseline.json` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - `output/baseline.json` が生成され、有効な計画 JSON が書き込まれている。
  - 生成された JSON を `taskweave replan examples/basic --as-of 2026-09-09 --baseline output/baseline.json` で直接入力として再利用できる。

### シナリオ 4: 原本データに検証エラーがある場合の失敗

- **前提 (Given)**: `tasks.yaml` に循環依存または構文エラーが含まれるディレクトリ。
- **操作 (When)**: `taskweave plan <invalid_dir>` を実行する。
- **期待結果 (Then)**:
  - 終了コード `1` で終了する。
  - 標準エラー出力に対象ファイル名・エラー行・原因メッセージが出力される。
  - 計算エンジンは呼び出されない。

### シナリオ 5: 納期超過（ソフト制約）発生時の診断情報出力

- **前提 (Given)**: 原本データにおいて設定された納期（deadline）が厳しく、遅延が発生するプロジェクト。
- **操作 (When)**: `taskweave plan` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する（ソフト制約によるペナルティ最小化解）。
  - 出力テキストまたは JSON に、遅延タスク（`delay_days > 0`）および納期緩和推奨（recommendations）が含まれる。

### シナリオ 6: `taskweave plan --format mermaid` によるガントチャート出力 (AC-1)

- **前提 (Given)**: 有効な原本データが存在し、先行依存関係を持つタスクが含まれる。
- **操作 (When)**: `taskweave plan examples/basic --format mermaid` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 標準出力に `gantt` 構文が出力され、`section`（担当者名）、タスク日程、および `after`（先行依存タスク）が含まれていること。

### シナリオ 7: `taskweave plan --format markdown` による Markdown テーブル出力 (AC-2)

- **前提 (Given)**: 有効な原本データが存在する。
- **操作 (When)**: `taskweave plan examples/basic --format markdown` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 標準出力に Markdown 見出し（`# スケジュール計画レポート`）と、全体サマリ表、タスク一覧表、担当者別工数サマリ表が出力されること。

### シナリオ 8: `taskweave replan --format mermaid` による再計画可視化出力 (AC-3)

- **前提 (Given)**: 原本データおよび実績（一部完了・進行中）が存在する。
- **操作 (When)**: `taskweave replan examples/basic --as-of 2026-09-09 --format mermaid` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 標準出力に `gantt` 構文が出力され、完了タスクには `done`、進行中タスクの実績には `done`、残工数には `active` が付与されて視覚的に区別できること。

### シナリオ 9: `taskweave replan --format markdown` による遅延診断 Markdown 出力 (AC-4)

- **前提 (Given)**: ベースライン計画および遅延要因を含む実績データが存在する。
- **操作 (When)**: `taskweave replan examples/basic --as-of 2026-09-09 --format markdown` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 標準出力に Markdown テーブルが出力され、ベースライン比較サマリ、遅延タスク診断（スリップ日数、主原因、詳細）、再計画タスク一覧が含まれること。

### シナリオ 10: `--output <path>` オプションとの併用によるファイル保存 (AC-5)

- **前提 (Given)**: 有効な原本データが存在し、出力先パスを指定する。
- **操作 (When)**: `taskweave plan examples/basic --format mermaid --output output/plan.mermaid` および `taskweave replan examples/basic --as-of 2026-09-09 --format markdown --output output/replan.md` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 指定されたパスに該当フォーマットのテキストが正常に保存され、標準出力にも同一テキストが出力されること。

---

## 5. 制約事項・スコープ外 (Out of Scope)

- **実績工数の追記・進捗更新（`taskweave log`）**: Issue #42 にて対応。
- **再計画結果のベースライン確定・原本更新（`taskweave apply`）**: Issue #43 にて対応。
- **複数メンバによる同一タスクの同時分担（ペアプロ等）**: YAGNI 原則に基づき将来検討。
