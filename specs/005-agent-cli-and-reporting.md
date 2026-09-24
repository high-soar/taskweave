---
type: spec
title: エージェント CLI & レポーティング仕様
description: 原本初期計画コマンド (taskweave plan)、可視化出力 (Mermaid ガントチャート・Markdown 表)、実績・進捗記録 (taskweave log)、および再計画ベースライン確定・原本更新ワークフロー (taskweave apply) の仕様
tags: [cli, reporting, mermaid, markdown, plan, log, apply, milestone-4]
status: implemented
issues: [40, 41, 42, 43]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-24T16:47:00Z }
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
  - 祝日・非稼働日を考慮し、タスクの開始日・終了日および担当者名（セクションまたはタスク名）を可視化すること。
- **FR-8 (Markdown テーブル出力)**:
  - `taskweave plan --format markdown` および `taskweave replan --format markdown` により、タスク日程一覧表、担当者別工数サマリ、および差分・遅延原因テーブルを出力すること。

#### 実績記録インターフェース (`taskweave log` - Issue #42)

- **FR-9 (`taskweave log` コマンド構文と更新仕様)**:
  - 基本構文: `taskweave log <date> --member <id> --task <id> --hours <h> [--remaining <h>] [--status <status>] [--add] [directory]`
  - 引数仕様:
    - `<date>`: 作業日（`YYYY-MM-DD` 形式、必須位置引数）。
    - `--member <id>`: 実績を記録するメンバー ID（必須）。
    - `--task <id>`: 実績を記録するタスク ID（必須）。
    - `--hours <h>`: 稼働工数（0.1 以上の 0.1 時間刻み正の数値、必須）。
    - `--remaining <h>`: 残工数（0.0 以上の 0.1 時間刻み数値、任意）。
    - `--status <status>`: タスク進捗状態（`not_started`, `in_progress`, `completed`、任意）。
    - `--add`: 同一日・同メンバ・同タスクの既存ログがある場合に上書きではなく工数を加算するフラグ（任意、デフォルトは上書き更新）。
    - `[directory]`: 原本 YAML ファイル群が配置されたディレクトリ（任意、デフォルト: `data`）。
  - 事前検証と安全性 (AC-3):
    - コマンド実行時、原本データ（`members.yaml`, `tasks.yaml`, `calendar.yaml`）および更新対象の実績データをメモリ上で結合し、原本スキーマ検証および論理整合性検証（`validate_logical_integrity`）を事前実行する。
    - 未定義メンバー ID、未定義タスク ID、カレンダー不在日（absences）での稼働記録、1日 24 時間超過、同一タスクへの複数メンバー割当、および不正な工数フォーマット等の違反を検知した場合、ファイル書き込みを行わずに標準エラー出力（`stderr`）にエラーメッセージを出力し、終了コード `1` で中断する。
  - ファイル自動作成と構造維持 (AC-4):
    - 指定ディレクトリに `actuals.yaml` が存在しない場合、`actuals:` ルートキー付き構造（Issue #38 合意方針）でファイルを自動新規作成する。
    - 既存の `actuals.yaml` が存在する場合、ルートキー付き（`actuals:`）またはフラット形式の構造を判別してその階層を維持して更新・保存する。
  - 稼働実績 (`work_logs`) の更新規則 (AC-1):
    - 同一の `date`, `member_id`, `task_id` を持つ既存エントリが存在する場合:
      - `--add` 指定時: 既存の `hours` に指定工数を加算（`round(existing + hours, 1)`）。
      - `--add` 未指定時: 既存の `hours` を指定工数で上書き更新。
    - 該当エントリが存在しない場合、新しいログエントリを `work_logs` リストの末尾に追記する。
  - 進捗ステータス (`task_progress`) の更新規則 (AC-2):
    - `--remaining` または `--status` の少なくとも一方が指定された場合に `task_progress` を更新する。
    - 同一 `task_id` のエントリが存在する場合、指定されたフィールド（`remaining_hours`, `status`）を更新する。
    - 該当エントリが存在しない場合、新規エントリを作成して `task_progress` リストに追加する（未指定のフィールドはタスク見積りやログ合計時間から自動導出またはデフォルト補完）。

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

### シナリオ 6: `taskweave log` による新規 `actuals.yaml` 自動作成と実績記録 (AC-1, AC-4, AC-5)

- **前提 (Given)**: `actuals.yaml` がまだ存在しない原本ディレクトリ（例: `data` または指定ディレクトリ）。
- **操作 (When)**: `taskweave log 2026-09-08 --member alice --task task-setup --hours 8.0` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - `actuals.yaml` が自動作成され、ルートキー `actuals:` 配下に `work_logs` リスト（日付 `2026-09-08`, メンバ `alice`, タスク `task-setup`, 工数 `8.0`）が書き込まれる。

### シナリオ 7: 同一日・同メンバ・同タスクのログ更新（上書きおよび `--add` による加算） (AC-1)

- **前提 (Given)**: すでに `date: 2026-09-08`, `member_id: alice`, `task_id: task-setup`, `hours: 4.0` が記録されている。
- **操作 (When 1 - 上書き)**: `taskweave log 2026-09-08 --member alice --task task-setup --hours 6.0` を実行する。
- **期待結果 (Then 1)**: `work_logs` 内の該当エントリの工数が `6.0` に上書き更新される（エントリ数は増えない）。
- **操作 (When 2 - 加算)**: `taskweave log 2026-09-08 --member alice --task task-setup --hours 2.0 --add` を実行する。
- **期待結果 (Then 2)**: `work_logs` 内の該当エントリの工数が `8.0` (`6.0 + 2.0`) に加算更新される。

### シナリオ 8: `--remaining` および `--status` による `task_progress` 同時更新 (AC-2)

- **前提 (Given)**: 有効な原本ディレクトリ。
- **操作 (When)**: `taskweave log 2026-09-08 --member alice --task task-setup --hours 8.0 --remaining 0.0 --status completed` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - `work_logs` に工数 `8.0` が記録される。
  - `task_progress` に `task_id: task-setup`, `remaining_hours: 0.0`, `status: completed` が記録または更新される。

### シナリオ 9: 原本データ・実績データの論理違反による記録防止 (AC-3)

- **前提 (Given)**: 未定義のメンバー ID、未定義のタスク ID、あるいは `calendar.yaml` でメンバが不在（absent）として登録されている日。
- **操作 (When)**:
  - 不在日での記録: `taskweave log 2026-09-09 --member alice --task task-setup --hours 8.0`
  - または未定義メンバでの記録: `taskweave log 2026-09-08 --member unknown --task task-setup --hours 8.0`
- **期待結果 (Then)**:
  - 終了コード `1` で中断する。
  - 標準エラー出力（`stderr`）に論理違反の内容（未定義メンバ、不在日での実績記録等）が出力される。
  - `actuals.yaml` への書き込みは行われない（ファイルは変更されない）。

### シナリオ 10: 既存 `actuals.yaml` のルートキー構造維持 (AC-4)

- **前提 (Given)**: フラット形式（`actuals:` ルートキーなしで `work_logs:` がトップレベルにある）の既存 `actuals.yaml`。
- **操作 (When)**: `taskweave log 2026-09-09 --member alice --task task-setup --hours 4.0` を実行する。
- **期待結果 (Then)**:
  - 終了コード `0` で終了する。
  - 更新後の `actuals.yaml` もフラット形式のまま維持され、既存の構造が崩れない。

---

## 5. 制約事項・スコープ外 (Out of Scope)

- **Mermaid ガントチャート出力および Markdown テーブル出力**: Issue #41 にて対応。
- **再計画結果のベースライン確定・原本更新（`taskweave apply`）**: Issue #43 にて対応。
- **複数メンバによる同一タスクの同時分担（ペアプロ等）**: YAGNI 原則に基づき将来検討。
