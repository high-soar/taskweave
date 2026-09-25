---
type: spec
title: スキーマ表現力 & 最適化強化仕様
description: 原本 YAML スキーマのルートキー対称性統一、非推奨警告、メンバー個別稼働曜日、担当者明示指定、負荷平準化およびタスク引き継ぎの仕様定義
tags: [schema, symmetry, deprecation, actuals, optimization, milestone-5]
status: accepted
issues: [50, 51]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-25T05:15:00Z }
---

# スキーマ表現力 & 最適化強化仕様 (006-schema-expressiveness-and-optimization)

## 1. 概要とユーザーストーリー

- **Milestone 5 のゴール**:
  混成チーム（時短勤務・週2日委託・フルタイム）や実務の運用変更（引き継ぎ・負荷分散）に柔軟に対応できるよう、原本 YAML スキーマの表現力とソルバー最適化を強化する。
- **ユーザーストーリー**:
  - **ストーリー 1 (Issue #50: 原本 YAML スキーマのルートキー対称性統一と非推奨警告の導入)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: `actuals.yaml` において他の原本 YAML（`members.yaml`, `tasks.yaml`, `calendar.yaml`）と同様に `actuals:` ルートキー構造を推奨形式として対称性を統一し、旧形式（トップレベル直下形式）に対して非推奨警告（Deprecation Warning）を出力したい
    - **So that**: 原本 YAML スキーマの対称性・一貫性を確立し、エージェントやツールが迷いなく構造化データを解析・生成できるようにするため（RFC #38 の合意に基づく）
  - **ストーリー 2 (Issue #51: メンバー個別稼働曜日（workdays）の原本定義とスケジュール計算への反映)**:
    - **As a**: プロジェクト管理者および混成チームのリード
    - **I want**: 業務委託・時短勤務・副業メンバーなど特定曜日のみ稼働するメンバーの個別稼働曜日（例: `workdays: ["mon", "wed", "fri"]`）を `members.yaml` に定義し、スケジュール計算に反映させたい
    - **So that**: カレンダー原本（`calendar.yaml` の `absences`）に毎週の非稼働日を個別登録する手間をなくし、混成チームのキャパシティを簡潔かつ正確に管理できるようにするため
  - **ストーリー 3 (Issue #52: 担当者の明示指定・推奨 - 今後予定)**:
    - **As a**: プロジェクト管理者および計画立案者
    - **I want**: `tasks.yaml` においてタスクの担当者を事前指定（`assigned_to`）または推奨（`preferred_member`）したい
    - **So that**: 特定メンバへの名指し割り当てと自動最適化を共存させるため
  - **ストーリー 4 (Issue #53: 負荷平準化ソフト制約 - 今後予定)**:
    - **As a**: チームリード
    - **I want**: 同一スキルを持つ複数メンバー間で作業負荷が偏らないよう、全体の納期を損なわずに負荷が平準化されるようにしたい
    - **So that**: 特定のメンバーへの過負荷を防ぎ、健全なチーム稼働を維持するため
  - **ストーリー 5 (Issue #54: 着手済みタスクの引き継ぎ・再割当 - 今後予定)**:
    - **As a**: プロジェクト管理者およびメンバ
    - **I want**: 着手済みタスクの残工数を別メンバーへ引き継ぎ（Reassign）できるようにしたい
    - **So that**: メンバの長期不在や担当変更時にも柔軟に計画を継続するため
- **背景と目的**:
  先行マイルストーンにおいて、Taskweave は原本 YAML（`members.yaml`, `tasks.yaml`, `calendar.yaml`, `actuals.yaml`）を基盤とした計画・実績追跡・再計画ワークフローを確立しました。
  しかし、`members.yaml`（`members:`）、`tasks.yaml`（`tasks:`）、`calendar.yaml`（`calendar:`）がルートキー必須であるのに対し、`actuals.yaml` のみトップレベル直下に `work_logs` / `task_progress` を配置する形式と `actuals:` ルートキー形式が混在し、非対称性が生じていました（RFC #38）。
  本仕様では、Milestone 5 の第1段階として原本 YAML のルートキー対称性を統一し、旧形式に対する段階的移行ポリシー（Deprecation Warning）を確立します。

---

## 2. 要件定義

### 2.1 機能要件 (FR: Functional Requirements)

- **FR-1 (`actuals:` ルートキー標準形式の確立)**:
  - `actuals.yaml` の標準・推奨形式として、トップレベルに `actuals:` ルートキーを配置し、その配下に `work_logs` および `task_progress` を定義する構造を規定する。
- **FR-2 (旧トップレベル直下形式に対する非推奨警告)**:
  - トップレベル直下に `work_logs` または `task_progress` を配置した旧形式の `actuals.yaml` を読み込んだ際、バリデーションエラーとせず、非推奨警告（Deprecation Warning）を発行する。
  - 後方互換性を維持するため、旧形式データは内部で透過的に正規化して処理を継続する。
- **FR-3 (`ValidationResult` / `ProjectValidationResult` の `warnings` 拡張)**:
  - `ValidationResult` および `ProjectValidationResult` に `warnings: list[str] = field(default_factory=list)` を追加する。
  - バリデータは警告メッセージを `warnings` に格納し、標準エラー出力やコンソール出力などのプレゼンテーション層と関心を分離する。
- **FR-4 (CLI `validate` での警告表示と移行ヒント出力)**:
  - `taskweave validate` コマンド実行時、`warnings` が存在する場合は標準エラー出力（stderr）に `[WARNING]` メッセージと推奨形式への移行ヒントを表示する。
  - エラー（`errors`）が存在しない限り、終了コード 0 で正常終了する。
- **FR-5 (`taskweave log` による正規化書き出し)**:
  - `taskweave log` コマンドで実績・進捗を記録する際、新規作成時および既存ファイル更新時のいずれにおいても、常に `actuals:` ルートキーを持つ正規化形式でファイルへ書き出す。
  - 旧トップレベル形式で存在していた `actuals.yaml` に対しても、次回 `taskweave log` 実行時に安全に推奨形式へ移行・保存される。
- **FR-6 (透過的な正規化ロードと後方互換性)**:
  - `actuals:` ルートキー付き形式の `actuals.yaml` は `warnings` なしで正常にロードされる。
  - `taskweave plan`, `taskweave replan`, `taskweave apply` などの計算エンジンおよび CLI コマンドは、ルートキー有無に関わらず透過的に同一のデータ構造（`work_logs`, `task_progress`）として解釈する。
- **FR-7 (`members[].workdays` の原本定義と構文制約 - Issue #51)**:
  - `members.yaml` の各メンバー定義に、個別稼働曜日を表す `workdays` フィールド（曜日文字列のリスト: `"mon"`, `"tue"`, `"wed"`, `"thu"`, `"fri"`, `"sat"`, `"sun"`）を任意指定できること。
  - バリデータは、配列型、許容曜日文字列、重複要素の禁止、および空リスト（要素数0）の禁止を構文検証する。
- **FR-8 (`calendar.workdays` サブセット検証 - 最小・安全なフィルター設計 - Issue #51)**:
  - プロジェクトの論理整合性検証において、各メンバーの `workdays` がプロジェクトカレンダーの営業日（`calendar.workdays`）のサブセット（部分集合）であることを検証する。
  - プロジェクト営業日外の曜日（例: プロジェクトが月〜金稼働でメンバーに土曜を指定）が定義された場合は論理整合性エラーを出力し、解決ヒントを提示する。
- **FR-9 (`workdays` 省略時のデフォルト継承 - Issue #51)**:
  - `workdays` が未指定（省略）のメンバーは、従来のチームカレンダー営業日設定（`calendar.workdays`、デフォルト: 月〜金）に従う。
- **FR-10 (日別キャパシティ計算における非稼働曜日のキャパシティ 0 化 - Issue #51)**:
  - 計算エンジン（`engine.py`）の初期計画（`solve_schedule`）および再計画（`_solve_replan`）において、メンバーの `workdays` に含まれない曜日のキャパシティ（利用可能時間）を 0 とし、タスクの割当を抑止する。
- **FR-11 (チーム祝日・個別不在との論理積結合 - Issue #51)**:
  - `calendar.yaml` のチーム祝日（`holidays`）およびメンバー個別不在（`absences`）と併用された場合、それらの論理積（プロジェクト営業日 かつ 祝日でない かつ メンバー個別稼働曜日 かつ 個別不在でない日のみ稼働可能）として正しく扱われること。
- **FR-12 (スケジュール出力・レポーティングへの正確な反映 - Issue #51)**:
  - `taskweave plan` / `replan` のスケジュール出力（Markdown 表、Mermaid ガントチャート）において、非稼働曜日を跨いだ作業日程（開始日・終了日・稼働日数）が正確に表示されること。

### 2.2 非機能要件 (NFR: Non-Functional Requirements)

- **NFR-1 (後方互換性と非破壊移行)**:
  - 既存プロジェクトの旧形式 `actuals.yaml` を即座に破損・拒絶せず、段階的な移行期間を設ける。
- **NFR-2 (関心の分離)**:
  - バリデータモジュール（`validator.py`）はデータ検査と警告生成のみを担当し、CLI モジュール（`cli.py`）が出力フォーマットおよび終了コード制御を担当する。
- **NFR-3 (冪等性と決定論性)**:
  - `taskweave log` による書き出しは冪等であり、フォーマット変換によって作業ログや進捗データの数値・文字列が改変されないこと。
- **NFR-4 (YAGNI 原則)**:
  - 現段階で不要な一括マイグレーション専用サブコマンドの乱立を避け、日々のバリデーション（ヒント表示）および `taskweave log` での自動移行に留める。

---

## 3. データ構造・スキーマ定義 (Schema-Driven)

### 3.1 原本 YAML のルートキー対称性 (SSOT)

すべての原本 YAML ファイルは、ファイル種別を表すルートキーでラップされる対称的な構造を標準とします。

| ファイル名      | 推奨ルートキー | 状態     | 説明                                      |
| :-------------- | :------------- | :------- | :---------------------------------------- |
| `members.yaml`  | `members:`     | 必須     | メンバー一覧配列                          |
| `tasks.yaml`    | `tasks:`       | 必須     | タスク一覧配列                            |
| `calendar.yaml` | `calendar:`    | 必須     | チーム稼働日・祝日・個別不在オブジェクト  |
| `actuals.yaml`  | `actuals:`     | **推奨** | 日々の作業実績およびタスク進捗（M5 統一） |

---

### 3.2 `actuals.yaml` 推奨スキーマ (ルートキー形式)

```yaml
actuals:
  work_logs:
    - date: "2026-09-10"
      member_id: alice
      task_id: task-api
      hours: 6.0
    - date: "2026-09-11"
      member_id: alice
      task_id: task-api
      hours: 4.5

  task_progress:
    - task_id: task-api
      remaining_hours: 5.5
      status: in_progress
    - task_id: task-setup
      remaining_hours: 0.0
      status: completed
```

#### フィールド詳細 (`actuals`)

| フィールド名                              | 型             | 必須 | デフォルト | 説明・制約                                                                                        |
| :---------------------------------------- | :------------- | :--- | :--------- | :------------------------------------------------------------------------------------------------ |
| `actuals`                                 | object         | 推奨 | -          | 実績データのルートオブジェクト。                                                                  |
| `actuals.work_logs`                       | list of object | 任意 | `[]`       | 作業実績ログのリスト。                                                                            |
| `actuals.work_logs[].date`                | string (date)  | 必須 | -          | 作業実施日。実在する `YYYY-MM-DD` 形式の日付文字列。                                              |
| `actuals.work_logs[].member_id`           | string         | 必須 | -          | 作業を担当したメンバの ID。`members.yaml` に定義が存在すること。                                  |
| `actuals.work_logs[].task_id`             | string         | 必須 | -          | 作業対象のタスク ID。`tasks.yaml` に定義が存在すること。                                          |
| `actuals.work_logs[].hours`               | number         | 必須 | -          | 投入した実績工数（時間）。`0.1` 以上の `0.1` 刻みの正の有限数値。                                 |
| `actuals.task_progress`                   | list of object | 任意 | `[]`       | タスク進捗ステータスおよび明示的残工数のリスト。                                                  |
| `actuals.task_progress[].task_id`         | string         | 必須 | -          | 対象タスク ID。`tasks.yaml` に定義が存在すること。同一リスト内で重複不可。                        |
| `actuals.task_progress[].remaining_hours` | number         | 必須 | -          | 見積もり直した残工数（時間）。`0.0` 以上の `0.1` 刻みの有限数値。`status: completed` 時は `0.0`。 |
| `actuals.task_progress[].status`          | string         | 必須 | -          | タスク状態。`not_started`, `in_progress`, `completed` のいずれか。                                |

---

### 3.3 非推奨旧スキーマ (トップレベル直下形式) と非推奨ポリシー

```yaml
# 非推奨形式 (Deprecated)
work_logs:
  - date: "2026-09-10"
    member_id: alice
    task_id: task-api
    hours: 6.0

task_progress:
  - task_id: task-api
    remaining_hours: 5.5
    status: in_progress
```

- **非推奨ポリシー**:
  1. **警告期間 (Milestone 5)**: 旧形式を検知した場合は `warnings` を返し、CLI 実行時に標準エラー出力へ警告と推奨形式への移行ヒントを表示する。バリデーション自体は成功（終了コード 0）とし、処理をブロックしない。
  2. **自動正規化**: `taskweave log` の実行により、追記・更新時に自動的に `actuals:` ルートキー付き形式へ更新される。
  3. **将来の廃止 (Major Version 移行時)**: メジャーバージョンアップ時に旧形式のサポートを終了し、エラー扱いとする予定。

---

### 3.4 `members.yaml` 拡張スキーマ (`workdays` - Issue #51)

特定曜日のみ稼働するメンバー（業務委託・時短勤務・副業など）の稼働曜日をメンバーごとに定義します。

```yaml
members:
  - id: alice
    name: "Alice"
    max_capacity: 1.0
    skills:
      - backend
  - id: bob
    name: "Bob (週3日稼働)"
    max_capacity: 1.0
    workdays:
      - mon
      - wed
      - fri
    skills:
      - frontend
```

#### フィールド詳細 (`members[].workdays`)

| フィールド名         | 型             | 必須 | デフォルト              | 説明・制約                                                                                                                                                                                                                                               |
| :------------------- | :------------- | :--- | :---------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `members[].workdays` | list of string | 任意 | `null` (カレンダー準拠) | メンバー固有の稼働曜日リスト。値は `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` のいずれか。重複不可、空リスト（`[]`）不可。プロジェクトカレンダーの営業日（`calendar.workdays`）のサブセットであること。未指定時はプロジェクトカレンダー設定に従う。 |

---

## 4. 受入基準とテストシナリオ (TDD 連携)

### シナリオ 1: `actuals:` ルートキー付き形式の正常ロード (AC-3)

- **前提 (Given)**: `actuals:` ルートキーでラップされた構文・論理ともに正しい `actuals.yaml` が存在する。
- **操作 (When)**: `validate_actuals` または `validate_project_data` を実行する。
- **期待結果 (Then)**: `valid == True`、`errors` が空、かつ `warnings` が空（警告なし）であること。

### シナリオ 2: トップレベル形式での非推奨警告格納と透過的正規化 (AC-2)

- **前提 (Given)**: トップレベル直下に `work_logs:` や `task_progress:` が配置された `actuals.yaml` が存在する。
- **操作 (When)**: `validate_actuals` または `validate_project_data` を実行する。
- **期待結果 (Then)**: `valid == True`、`errors` が空、`warnings` に非推奨警告メッセージが 1 件以上格納され、ロード結果（`data` / `actuals`）には正規化された `work_logs` と `task_progress` が格納されていること。

### シナリオ 3: バリデータ構造体の warnings フィールド定義 (AC-1)

- **前提 (Given)**: `taskweave.validator` モジュールをインポートする。
- **操作 (When)**: `ValidationResult` および `ProjectValidationResult` のフィールド構成を確認する。
- **期待結果 (Then)**: 両クラスに `warnings: list[str] = field(default_factory=list)` が存在し、デフォルトで空リストとなること。

### シナリオ 4: CLI `taskweave validate` での警告・移行ヒント出力 (AC-4)

- **前提 (Given)**: トップレベル直下形式の `actuals.yaml` を含む有効な原本ディレクトリが存在する。
- **操作 (When)**: `taskweave validate <dir>` を実行する。
- **期待結果 (Then)**:
  - 終了コードが 0 であること。
  - 標準エラー出力（stderr）に `[WARNING]` および非推奨警告、推奨スキーマへの移行ヒントが出力されること。
  - 標準出力（stdout）に検証成功メッセージが出力されること。

### シナリオ 5: CLI `taskweave log` での正規化書き出し (AC-5)

- **前提 (Given)**: `actuals.yaml` が存在しない、または旧トップレベル形式で存在する原本ディレクトリがある。
- **操作 (When)**: `taskweave log <date> <dir> --member <id> --task <id> --hours <h>` を実行する。
- **期待結果 (Then)**:
  - 書き出された `actuals.yaml` のルートに `actuals:` キーが存在すること。
  - 以降の `validate` 実行で非推奨警告が発生しないこと。

### シナリオ 6: 原本仕様書および実績仕様書への反映 (AC-6)

- **前提 (Given)**: `specs/001-yaml-schema.md`、`specs/004-actuals-and-replanning.md`、`specs/README.md` を確認する。
- **期待結果 (Then)**: ルートキー対称性の統一方針と非推奨警告ポリシーが明記されていること。

### シナリオ 7: pytest 品質ゲート全通過 (AC-7)

- **操作 (When)**: `uv run pytest` および `npm test` を実行する。
- **期待結果 (Then)**: すべてのテストケースが成功し、リポジトリ品質ゲートが全通過すること。

### シナリオ 8: `members.yaml` の `workdays` 構文検証 (Issue #51 AC-1, AC-2)

- **前提 (Given)**: `members.yaml` 内のメンバーに `workdays` フィールドが指定されている。
- **操作 (When)**: `validate_members` を実行する。
- **期待結果 (Then)**:
  - 正しい形式（例: `["mon", "wed", "fri"]`）の場合、`valid == True` でパース結果に `workdays` リストが保持されること。
  - 不正な型（文字列以外、数値、null）、不正な曜日名（`"funday"` 等）、重複曜日（`["mon", "mon"]`）、空配列（`[]`）の場合、`valid == False` となり具体的な構文エラーメッセージが出力されること。

### シナリオ 9: `calendar.workdays` サブセット検証エラー (Issue #51 AC-2)

- **前提 (Given)**: `calendar.yaml` で `workdays: ["mon", "tue", "wed", "thu", "fri"]` が設定されており、`members.yaml` のメンバーに `workdays: ["mon", "sat"]` のようにプロジェクト営業日外の曜日が指定されている。
- **操作 (When)**: `validate_project_data` または `validate_logical_integrity` を実行する。
- **期待結果 (Then)**: `valid == False` となり、該当メンバー、指定されたプロジェクト外の曜日、およびプロジェクト営業日のサブセットで指定すべき旨の解決ヒントを含む論理整合性エラーが出力されること。

### シナリオ 10: `workdays` 未指定メンバーの後方互換性 (Issue #51 AC-3)

- **前提 (Given)**: `members.yaml` 内のメンバー定義に `workdays` が未指定（省略）である。
- **操作 (When)**: `validate_project_data` および `solve_schedule` を実行する。
- **期待結果 (Then)**: エラーなく正常に処理され、プロジェクトカレンダーの営業日設定（`calendar.workdays`、デフォルト: 月〜金）に従って日別キャパシティが割り当てられること。

### シナリオ 11: 非稼働曜日のキャパシティ 0 化とタスク割当抑止 (Issue #51 AC-4)

- **前提 (Given)**: メンバー Alice の稼働曜日が `["mon", "wed", "fri"]` と指定されている。
- **操作 (When)**: `solve_schedule` または `_solve_replan` を実行する。
- **期待結果 (Then)**: Alice の非稼働曜日（火曜・木曜・土曜・日曜）の日別キャパシティが 0 となり、Alice の担当タスクの作業時間がこれらの曜日に一切割り当てられないこと。

### シナリオ 12: チーム祝日・個別不在との論理積 (Issue #51 AC-5)

- **前提 (Given)**: メンバー Alice の稼働曜日が `["mon", "wed", "fri"]` であり、ある週の月曜日が祝日（`calendar.holidays`）、水曜日が Alice の個別不在（`calendar.absences`）として登録されている。
- **操作 (When)**: スケジュール計算を実行する。
- **期待結果 (Then)**: その週の Alice の稼働可能日は金曜日のみとなり、祝日の月曜日および個別不在の水曜日には作業時間が割り当てられないこと（論理積の成立）。

### シナリオ 13: スケジュール出力・レポーティングでの非稼働曜日跨ぎ表示 (Issue #51 AC-6)

- **前提 (Given)**: 火曜・木曜のみ稼働のメンバーに 16 時間（8h × 2 稼働日）のタスクが割り当てられている。
- **操作 (When)**: `taskweave plan` または `taskweave replan` を実行し、Markdown 表および Mermaid ガントチャートを出力する。
- **期待結果 (Then)**: 非稼働曜日（水曜日）を挟んで開始日（火曜）から終了日（木曜）までの日程が正しく計算・表示されること。

### シナリオ 14: pytest 品質ゲート全通過 (Issue #51 AC-7)

- **操作 (When)**: `test_validator.py`, `test_engine.py`, `test_cli.py` を含む全 pytest テストおよびリポジトリ品質ゲートを実行する。
- **期待結果 (Then)**: すべてのテストケースが成功すること。

---

## 5. 制約事項・スコープ外 (Out of Scope)

- **旧形式の強制エラー化**: Milestone 5 では後方互換性を最優先し、エラーにはせず非推奨警告（Warning）にとどめる。
- **他原本ファイルのルートキー省略許容**: `members.yaml`, `tasks.yaml`, `calendar.yaml` は現行どおりルートキー必須を維持し、ルートキーなしは許容しない（RFC #38 の合意に基づく）。
- **一括マイグレーション専用 CLI**: `taskweave migrate` 等の専用コマンドは現時点では実装せず、`taskweave log` による通常運用時の安全な自動変換で対応する（YAGNI 原則）。
- **計画系 CLI コマンド（plan, replan, apply）での警告出力抑制**: JSON や Mermaid の標準出力パイプラインおよび自動化スクリプトとの親和性を保つため、警告出力は検証専門コマンド（`taskweave validate`）に集約し、`plan`, `replan`, `apply` などの計算・適用系コマンドでは warnings の標準エラー出力を抑制する設計とする（バリデーション失敗のエラーのみ stderr に出力）。
- **プロジェクト営業日外の個別稼働の禁止 (Issue #51 AC-2)**: プロジェクトカレンダーの稼働日（`calendar.workdays`）に含まれない曜日（例: 週末副業など）をメンバー個別に指定することはスコープ外とし、プロジェクト営業日のサブセット（部分集合）に限定する（最小・安全なフィルター設計）。チームとして休日に稼働させる場合は `calendar.workdays` に該当曜日を追加してプロジェクト全体で許容する運用とする。

---

## 6. 代替案と設計判断

- **代替案 A: 全原本ファイルでルートキーなしを透過的に許容する**:
  - `members.yaml` や `tasks.yaml` でもトップレベル配列を許容する案。
  - **不採用理由**: 将来のメタデータ拡張（バージョン番号、プロジェクト説明等）を付与できなくなること、および原本ごとの関心事が曖昧になるため不採用とした。
- **代替案 B: トップレベル形式の即時エラー化**:
  - **不採用理由**: 既存の運用プロジェクトやテストデータが一斉に動作不能となり、開発者・エージェント双方に不要な混乱を与えるため、Warning による段階的移行を採用した。
- **設計判断 C: 計画系コマンド（plan / replan / apply）における警告出力の扱い**:
  - **検討**: すべての CLI コマンドで warnings を stderr に出力する案。
  - **決定**: `taskweave validate` のみに警告表示を集約。
  - **理由**: CI やシェルパイプラインにおいて `taskweave plan --format json` や `--format mermaid` の標準出力を他ツールへパイプ・リダイレクトする際、不要な stderr 出力による自動化ツールの誤検知リスクを低減するため。原本の構文・非推奨警告のチェックは `taskweave validate` で明示的に行う責務分離を維持する。
- **設計判断 D: メンバー個別稼働曜日のフィルターモデル (Issue #51 AC-2)**:
  - **検討**: メンバーごとにプロジェクト営業日外の曜日（例: 土日）を独立して許容する「スーパーセットモデル」と、プロジェクト営業日を上限とする「サブセットモデル（フィルターモデル）」。
  - **決定**: サブセットモデル（`calendar.workdays` の部分集合）を採用。
  - **理由**: プロジェクト全体の営業日・カレンダーとの不整合を防ぎ、予期せぬ週末稼働や Makespan 算出の複雑化を防止するため。混成チームにおいて最も安全かつ最小の拡張である。
