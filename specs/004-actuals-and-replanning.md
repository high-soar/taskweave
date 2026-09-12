---
type: spec
title: 実績工数・個別不在の原本スキーマ検証、起算日再計画、および差分・遅延診断仕様
description: actuals.yaml および calendar.yaml の原本スキーマ・論理整合性検証と、起算日（As-of Date）再計画アルゴリズム、ベースライン差分（Diff）算出と遅延原因診断仕様
tags:
  [schema, yaml, actuals, absences, replanning, diff, diagnostics, milestone-3]
status: implemented
issues: [25, 26, 27, 28]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-12T15:40:16Z }
verified: { by: human:high-soar, at: 2026-09-12T15:40:16Z }
---

# 実績工数・個別不在の原本スキーマ検証、起算日再計画、および差分・遅延診断仕様 (004-actuals-and-replanning)

## 1. 概要とユーザーストーリー

- **ユーザーストーリー**:
  - **ストーリー 1 (Issue #25 原本検証)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: メンバの日々の作業実績工数（`actuals.yaml`）とメンバ個別不在（`calendar.yaml` の `absences`）を原本 YAML として定義し、構文・型・論理整合性を検証できるようにしたい
    - **So that**: 計画原本（`members.yaml`, `tasks.yaml`, `calendar.yaml`）を破壊することなく実績と不在を安全に保持し、不正なデータによる再計算クラッシュを未然に防ぐため
  - **ストーリー 2 (Issue #26 起算日再計画計算)**:
    - **As a**: コーディングエージェントおよびプロジェクト計画担当者
    - **I want**: 指定した起算日（As-of Date）以前の実績工数を固定し、未完了タスクの残工数のみを起算日以降の未来スケジュールとして自動再計算したい
    - **So that**: 過去の作業履歴を破壊することなく、実績消化に応じた最新の実行可能スケジュールを即座に再立案するため
  - **ストーリー 3 (Issue #27 個別不在再計画)**:
    - **As a**: チームメンバおよびプロジェクト計画担当者
    - **I want**: 突発的な欠勤や予定休暇（`calendar.absences`）が発生した際、対象メンバの該当日のキャパシティを 0 として未来スケジュールを再計画したい
    - **So that**: 不在メンバへの作業割り当てを確実に回避し、必要に応じて代替メンバへの自動再割り当てや工期延伸を反映した現実的な計画を得るため
  - **ストーリー 4 (Issue #28 ベースライン差分と遅延原因診断)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: 初回計画（ベースライン）と再計画後のスケジュールを比較し、タスク日程のスリップ（Diff）と遅延原因（工数増大、欠勤、先行遅延）を自動診断したい
    - **So that**: スケジュール遅延の理由をチームに明確に説明し、クリティカルパスのボトルネックに対する対策（納期見直しやスコープ調整）を講じるため
- **背景と目的**:
  Milestone 2 では初期計画の自動算出エンジンを確立しました。続く Milestone 3 では、進行中プロジェクトにおいて日々発生する作業実績工数や突発的な休暇・欠勤を考慮した再計画（Replanning）を実現します。
  本仕様では、原本ファイル（`actuals.yaml`, `calendar.yaml`）の検証規則（Issue #25）に加え、起算日（As-of Date）を用いた過去実績の固定と未完了タスクの未来スケジュール最適化エンジン（Issue #26）、個別不在を考慮した日別可変キャパシティによる割当制御（Issue #27）、ならびにベースライン計画との差分（Diff）算出と遅延原因自動診断および推奨納期緩和の出力（Issue #28）のアルゴリズムと制約を定義します。

---

## 2. 要件定義

### 2.1 機能要件 (FR: Functional Requirements)

- **FR-1 (`actuals.yaml` スキーマ定義)**:
  - 日々の実績作業ログ `work_logs`（日付 `date`, 担当者 `member_id`, タスク `task_id`, 実績工数 `hours`）を定義できること。
  - タスク進捗状況 `task_progress`（タスク `task_id`, 残工数 `remaining_hours`, 状態 `status`）を定義できること。
- **FR-2 (`calendar.yaml` の個別不在拡張)**:
  - `calendar.yaml` の `calendar` オブジェクト配下に、メンバ個別の不在情報 `absences`（担当者 `member_id`, 不在日 `date`, 事由 `name`）を定義できること。
  - `absences` が省略されている場合でも、従来の `calendar.yaml` として後方互換性を完全に維持すること。
- **FR-3 (オプショナル原本 `actuals.yaml` の許容)**:
  - プロジェクト開始直後や実績未記録時など、ディレクトリ内に `actuals.yaml` が存在しない場合でも `validate` コマンドおよび原本検証処理が正常終了（成功）すること。
- **FR-4 (厳格な型・数値制約検証)**:
  - `work_logs[].hours` は `0.1` 以上の数値かつ `0.1` 時間刻み（小数点以下1桁まで）の正の数値であること。
  - `task_progress[].remaining_hours` は `0.0` 以上の数値かつ `0.1` 時間刻み（小数点以下1桁まで）であること。
  - `task_progress[].status` は `not_started`, `in_progress`, `completed` のいずれかであること。
  - `status: completed` の場合、`remaining_hours` は必ず `0.0` であること。
  - 各種日付（`date`）は実在する有効な `YYYY-MM-DD` 形式の日付文字列であること。
- **FR-5 (論理整合性・参照整合性の検証)**:
  - `work_logs` および `absences` の `member_id` は `members.yaml` に定義されたメンバであること。
  - `work_logs` および `task_progress` の `task_id` は `tasks.yaml` に定義されたタスクであること。
  - 同一メンバ・同一日付における `work_logs` の実績工数合計は `24.0` 時間以内であること。
  - `task_progress` 内で同一の `task_id` が重複していないこと。
  - `absences` 内で同一メンバ・同一日付の不在設定が重複していないこと。
- **FR-6 (不在日と実績工数の排他制御)**:
  - `calendar.yaml` の `absences` に指定された不在日に、同一メンバの `work_logs` 実績が記録されている場合、論理矛盾エラーとして検知すること。
- **FR-7 (1タスク1担当者原則の維持)**:
  - `work_logs` において、同一 `task_id` に対して複数の異なる `member_id` が実績を記録している場合、1タスク1担当者原則違反エラーとして検知すること。
- **FR-8 (`task_progress` 省略時の残工数デフォルト解決)**:
  - `task_progress` 自体が省略された場合、または一部タスクの指定がない場合、残工数は `max(0.0, estimate_hours - total_logged_hours)`（`total_logged_hours` は当該タスクの `work_logs` の `hours` 合計）と解決される論理仕様とする。
- **FR-9 (CLI での診断出力と位置特定)**:
  - `actuals.yaml` 内の構文・型エラー、および各論理整合性エラーは、ファイル名（`actuals.yaml` または `calendar.yaml`）と該当行番号（`<file>:<line>: <message>`）を特定して標準エラー出力に出力すること。
- **FR-10 (起算日 As-of Date による時間軸分割と実績固定)**:
  - `solve_schedule` は `as_of_date`（任意, `datetime.date | str | None`）および `actuals_data`（任意, `dict[str, Any] | None`）を引数として受け取れること。
  - `as_of_date` より前（`date < as_of_date`）の実績作業ログを過去として固定し、出力スケジュール（`daily_hours`）およびメンバ日別集計（`member_daily_work`）にそのまま反映すること。
  - `as_of_date` 以降（`date >= as_of_date`）の稼働日を未来の探索空間とし、未完了タスクの残工数（`remaining_hours`）のみを最適スケジュール計画すること。
  - `as_of_date` が省略された場合（`None`）、プロジェクト開始日（`project_start_date`）からの全量計画（M2 互換）として動作すること。
- **FR-11 (完了済みタスクの未来探索空間からの完全除外)**:
  - `status: completed` または `remaining_hours == 0.0` のタスクは未来ソルバーの探索変数・制約から除外すること。
  - 完了済みタスクは過去の実績ログから期間（`start_date`, `end_date`）および日別工数を生成して出力に含めること。
- **FR-12 (着手済み未完了タスクの担当メンバ維持と残工数計画)**:
  - 実績工数 > 0 かつ 残工数 > 0 のタスクは、着手済みの担当メンバを維持すること（ピン留め制約: `assigned[t_id, m_pinned] == 1`）。
  - 残工数（`remaining_hours`）のみを起算日以降の稼働日に最適割り当てすること。
- **FR-13 (未着手タスクの最適割当と依存関係連動)**:
  - 未着手タスク（実績工数 == 0 かつ 残工数 > 0）は、スキル制約・日別稼働上限を満たして起算日以降に最適割り当てされること。
  - 先行タスクが完了済みの場合、先行制約は満たされたものとし、先行タスクが未完了（着手済みまたは未着手）の場合はその新終了日以降に開始されること。
- **FR-14 (決定論的再現性と探索性能)**:
  - 単一ワーカー (`num_search_workers = 1`) および固定乱数シード (`random_seed = 42`) を使用し、同一入力に対して決定論的に同一のスケジュールを出力すること。10秒以内に解が出力されること。
- **FR-15 (全タスク完了時の早期リターン最適化)**:
  - 全タスクが完了済みの場合、ソルバーを起動せず実績データのみから即座に結果を生成・返却すること。
- **FR-16 (日別・メンバ別可変キャパシティ制約 $C_{m, d}$ と個別不在割当制御)**:
  - `calendar.absences` に指定されたメンバの個別不在日は、該当メンバの日別キャパシティを 0（$C_{m, d} = 0$）とし、タスク作業工数の割当を一切行わないこと。
  - 未着手タスクにおいて、同じ必須スキルを持つ別メンバが存在する場合、遅延を最小化するよう別メンバへの振替割当が自動検討されること。
  - 代替メンバが不在の場合や着手済みタスク（担当メンバ固定）の場合、不在日を作業日としてスキップし、翌稼働日以降に作業が継続されること。
  - チーム祝日、週末、および個別不在が複合した場合でも、各メンバの稼働可能日が正しく判定されること。
  - `as_of_date` 指定の有無に関わらず、未来の計画探索空間において個別不在日に対するキャパシティ 0 制約を適用すること。
- **FR-17 (ベースライン計画との差分算出)**:
  - 初回計画（原本 YAML から実績なしで動的計算したベースライン、または指定されたベースライン計画結果）と再計画後スケジュールの差分を出力できること。
  - 全体工期 Makespan の変動差分（`makespan_workdays` のスリップ日数）を出力すること。
  - タスクごとの開始日差（スリップ日数）、終了日差（スリップ日数）、稼働日数差（工期増減）、担当者変更有無、納期超過日数増減（`delay_increase_days`）を出力すること。
- **FR-18 (再計画遅延原因の自動診断と主原因特定)**:
  - 再計画で終了日が遅延（スリップ）したタスク、または納期超過日数が増大したタスクについて、以下の要因を特定・診断できること:
    1. **工数増大（超過工数: `workload_increase`）**: 実績工数と残工数の合計が見積工数を超過している（`total_logged_hours + remaining_hours > estimate_hours`）。
    2. **メンバ欠勤（`member_absence`）**: 担当メンバの稼働予定期間に `calendar.absences` の不在日が存在し、作業が中断・延伸された。
    3. **先行タスク遅延の波及（`dependency_delay`）**: 依存先行タスクの終了遅延により開始日が後ろ倒しになった。
  - 遅延タスクごとに、該当するすべての要因リスト（`reasons`）、主原因（`primary_reason`）、および人間可読な診断説明文（`details`）を出力すること。
- **FR-19 (納期超過タスクに対する推奨納期緩和日の出力)**:
  - 再計画後も納期（`deadline`）を超過するタスクに対し、実行可能終了日に基づく推奨納期緩和日（Recommendations）および超過日数を提示できること。
- **FR-20 (Python API および CLI サブコマンド)**:
  - Python API として `taskweave.diff.compute_schedule_diff` および `taskweave.engine.replan`（`taskweave.replan`）を提供すること。
  - CLI サブコマンド `taskweave replan [directory] --as-of <YYYY-MM-DD> [--baseline <path>] [--format text|json]` を提供し、人間向けテキストサマリおよびプログラム連携用 JSON 構造化データを出力できること。

### 2.2 非機能要件 (NFR: Non-Functional Requirements)

- **NFR-1 (SSOT と原本保護)**: 実績データや個別不在は独立した原本ファイル・スキーマで管理し、ベースライン計画データ（`tasks.yaml` の見積工数など）を破壊・変更しないこと。
- **NFR-2 (決定論性と完全性)**: 同一の原本データに対して常に同一の検証結果・スケジュール計算結果を返すこと。浮動小数点誤差による判定ブレを起こさないこと。
- **NFR-3 (YAGNI 原則)**: 複数メンバでの同時実績記録や、分単位の時間帯記録（例: 09:00〜18:00）は行わず、日単位・0.1h 刻みに限定すること。
- **NFR-4 (後方互換性)**: `as_of_date` を指定しない場合、M2 の全量計算動作および出力仕様と完全な後方互換性を保つこと。

---

## 3. データ構造・スキーマ定義 (Schema-Driven)

原本データディレクトリ（例: `data/`）において、既存の 3 ファイルに加えて `actuals.yaml` を配置可能とします。

```text
data/
├── members.yaml      # メンバ情報
├── tasks.yaml        # タスク情報
├── calendar.yaml     # チームカレンダー・稼働日・個別不在（拡張）
└── actuals.yaml      # 日々の作業実績・タスク進捗（任意原本）
```

---

### 3.1 `actuals.yaml` スキーマ

日々の作業実績工数と、必要に応じたタスクの最新進捗状況を記録します。

```yaml
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

#### フィールド詳細 (`actuals.yaml`)

| フィールド名                      | 型             | 必須 | デフォルト | 説明・制約                                                                                        |
| :-------------------------------- | :------------- | :--- | :--------- | :------------------------------------------------------------------------------------------------ |
| `work_logs`                       | list of object | 任意 | `[]`       | 作業実績ログのリスト。                                                                            |
| `work_logs[].date`                | string (date)  | 必須 | -          | 作業実施日。実在する `YYYY-MM-DD` 形式の日付文字列。                                              |
| `work_logs[].member_id`           | string         | 必須 | -          | 作業を担当したメンバの ID。`members.yaml` に定義が存在すること。                                  |
| `work_logs[].task_id`             | string         | 必須 | -          | 作業対象のタスク ID。`tasks.yaml` に定義が存在すること。                                          |
| `work_logs[].hours`               | number         | 必須 | -          | 投入した実績工数（時間）。`0.1` 以上の `0.1` 刻みの正の有限数値。                                 |
| `task_progress`                   | list of object | 任意 | `[]`       | タスク進捗ステータスおよび明示的残工数のリスト。                                                  |
| `task_progress[].task_id`         | string         | 必須 | -          | 対象タスク ID。`tasks.yaml` に定義が存在すること。同一リスト内で重複不可。                        |
| `task_progress[].remaining_hours` | number         | 必須 | -          | 見積もり直した残工数（時間）。`0.0` 以上の `0.1` 刻みの有限数値。`status: completed` 時は `0.0`。 |
| `task_progress[].status`          | string         | 必須 | -          | タスク状態。`not_started`, `in_progress`, `completed` のいずれか。                                |

---

### 3.2 `calendar.yaml` の `absences` 拡張スキーマ

`calendar.yaml` の `calendar` オブジェクト配下に、メンバ個別の不在日リスト `absences` を追加します。

```yaml
calendar:
  workdays:
    - mon
    - tue
    - wed
    - thu
    - fri
  holidays:
    - date: "2026-09-15"
      name: "敬老の日"
  absences:
    - member_id: bob
      date: "2026-09-16"
      name: "私用休暇"
    - member_id: alice
      date: "2026-09-18"
      name: "体調不良"
```

#### フィールド詳細 (`calendar.absences[]`)

| フィールド名           | 型             | 必須 | デフォルト | 説明・制約                                                                         |
| :--------------------- | :------------- | :--- | :--------- | :--------------------------------------------------------------------------------- |
| `absences`             | list of object | 任意 | `[]`       | メンバ個別の不在日（有給休暇・欠勤・研修等）のリスト。                             |
| `absences[].member_id` | string         | 必須 | -          | 不在となるメンバの ID。`members.yaml` に定義が存在すること。                       |
| `absences[].date`      | string (date)  | 必須 | -          | 不在日。実在する `YYYY-MM-DD` 形式の日付文字列。同一メンバ・同一日付の重複は不可。 |
| `absences[].name`      | string         | 任意 | `""`       | 不在の事由・名称。省略可能（指定する場合は非 null の文字列）。                     |

---

### 3.3 差分（Diff）および遅延診断データ構造

`taskweave.diff.compute_schedule_diff` および `taskweave replan --format json` で出力される差分・診断の構造です。

```json
{
  "makespan": {
    "baseline_workdays": 10,
    "replanned_workdays": 13,
    "slip_workdays": 3
  },
  "tasks": {
    "task-api": {
      "task_id": "task-api",
      "baseline": {
        "start_date": "2026-09-08",
        "end_date": "2026-09-11",
        "assigned_to": "alice",
        "workdays_count": 4,
        "delay_days": 0
      },
      "replanned": {
        "start_date": "2026-09-08",
        "end_date": "2026-09-15",
        "assigned_to": "alice",
        "workdays_count": 5,
        "status": "in_progress",
        "delay_days": 2
      },
      "diff": {
        "start_date_slip_days": 0,
        "end_date_slip_days": 4,
        "workdays_count_diff": 1,
        "assignee_changed": false,
        "delay_increase_days": 2
      },
      "diagnostics": {
        "is_delayed": true,
        "primary_reason": "workload_increase",
        "reasons": ["workload_increase"],
        "details": [
          "見積工数 (16.0h) に対し、実績および残工数合計 (22.0h) が超過 (+6.0h)"
        ]
      }
    }
  },
  "summary": {
    "total_tasks": 5,
    "delayed_tasks_count": 1,
    "delayed_task_ids": ["task-api"]
  },
  "recommendations": [
    {
      "task_id": "task-api",
      "current_deadline": "2026-09-11",
      "recommended_deadline": "2026-09-15",
      "delay_days": 2,
      "message": "タスク 'task-api' の納期を 2026-09-15 以降に緩和することを推奨します"
    }
  ]
}
```

---

## 4. 受入基準とテストシナリオ (TDD 連携)

### シナリオ 1: 正常系原本データの検証 (AC-1, AC-2, AC-3)

- **前提 (Given)**:
  - 有効な `members.yaml`, `tasks.yaml`, `calendar.yaml`（`absences` を含む）が存在する。
  - 有効な `actuals.yaml`（`work_logs`, `task_progress`）が存在する（または存在しない）。
- **操作 (When)**:
  - `taskweave validate [dir]` を実行する。
- **期待結果 (Then)**:
  - エラーなく解析され、検証成功（終了コード 0）すること。`actuals.yaml` がない場合でも正常終了すること。

### シナリオ 2: スキーマ・型制約違反の検知 (AC-1, AC-2)

- **前提 (Given)**:
  - `actuals.yaml` で `hours` が `0` や `-1.0`、あるいは `0.15`（0.1h 刻みでない）が指定されている。
  - または `task_progress` で `status: completed` なのに `remaining_hours: 2.0` が指定されている。
  - または `calendar.absences` で同一メンバ・同一日付が重複している。
- **操作 (When)**:
  - バリデータで検証を実行する。
- **期待結果 (Then)**:
  - 検証が失敗し、該当ファイルの行番号付きでエラーが出力されること。

### シナリオ 3: 論理整合性違反の検知 (AC-4)

- **前提 (Given)**:
  - 未定義の `member_id` や `task_id` が `work_logs`, `task_progress`, `absences` に指定されている。
  - または同一メンバの 1 日の実績合計が `24.5h`（24h 超）である。
  - または `calendar.absences` に不在登録されているメンバ・日付に実績工数が記録されている。
  - または同一タスクに対して Alice と Bob の両方の実績工数が記録されている（1タスク1担当者違反）。
- **操作 (When)**:
  - バリデータで検証を実行する。
- **期待結果 (Then)**:
  - 検証が失敗し、未定義参照・上限超過・不在日矛盾・複数担当者違反を明示したエラーが出力されること。

### シナリオ 4: 起算日（As-of Date）による実績固定と出力反映 (AC-1)

- **前提 (Given)**:
  - `actuals.yaml` に `date < as_of_date` の作業実績ログが記録されている。
- **操作 (When)**:
  - `solve_schedule(..., as_of_date="2026-09-10", actuals_data=actuals)` を実行する。
- **期待結果 (Then)**:
  - 出力スケジュールにおいて、起算日より前の実績ログがタスクの `daily_hours` および `member_daily_work` にそのまま固定されて反映されること。

### シナリオ 5: 完了済みタスクの除外と実績期間出力 (AC-2)

- **前提 (Given)**:
  - あるタスク（例: `task-api`）が `status: completed` または `remaining_hours == 0` である。
- **操作 (When)**:
  - `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - 当該タスクは未来の探索空間（`date >= as_of_date`）から除外され、起算日以降の稼働日を消費しないこと。
  - スケジュール出力には過去の実績ログから算出した `start_date`, `end_date`, `daily_hours` が正しく含まれること。

### シナリオ 6: 着手済み未完了タスクの担当メンバ維持と残工数計画 (AC-3)

- **前提 (Given)**:
  - タスク `task-api` に Alice の実績工数 `10.0h` が記録されており、残工数 `6.0h` が残っている。
  - チームには同等のスキルを持つ Bob も存在する。
- **操作 (When)**:
  - `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - `task-api` の担当者は Bob に振り替えられず Alice が維持されること（ピン留め制約）。
  - 残工数 `6.0h` のみが起算日以降の稼働日に計画されること。

### シナリオ 7: 未着手タスクの最適割当と先行タスク連動 (AC-4)

- **前提 (Given)**:
  - タスク `task-ui` は `task-api` に依存しており、未着手である。
  - `task-api` の残工数が起算日以降に計画される。
- **操作 (When)**:
  - `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - `task-ui` は `task-api` の新予定終了日の翌稼働日以降に開始され、スキル制約と稼働上限を満たして起算日以降に最適割り当てされること。

### シナリオ 8: 後方互換性（as_of_date 未指定時） (AC-5)

- **前提 (Given)**:
  - `as_of_date` を指定しない（`None`）。
- **操作 (When)**:
  - `solve_schedule(members, tasks, calendar, project_start_date)` を実行する。
- **期待結果 (Then)**:
  - 従来のプロジェクト開始日からの全量計画（M2 互換）として同一の解が出力されること。

### シナリオ 9: 決定論的再現性と探索性能 (AC-6)

- **前提 (Given)**:
  - 同一の原本データおよび実績データ。
- **操作 (When)**:
  - `solve_schedule` を複数回実行する。
- **期待結果 (Then)**:
  - 10秒以内に解が出力され、複数回実行でタスクの日別割当・担当者が完全に一致すること。

### シナリオ 10: 個別不在メンバへの該当日の割当回避（日別キャパシティ 0） (AC-1)

- **前提 (Given)**:
  - `calendar.yaml` の `absences` に特定メンバ（例: Alice）の特定稼働日（例: `2026-09-15`）が指定されている。
- **操作 (When)**:
  - `solve_schedule`（または起算日付き再計画）を実行する。
- **期待結果 (Then)**:
  - Alice の `2026-09-15` における日別作業時間（`member_daily_work` およびタスクの `daily_hours`）が 0 であり、タスク作業工数が一切割り当てられないこと。

### シナリオ 11: 未着手タスクにおける代替メンバへの自動再割り当て (AC-2)

- **前提 (Given)**:
  - Alice と Bob が同一の必須スキルを保有している。
  - 未着手タスク（例: 工数 8h, 納期が初日）が存在する。
  - Alice に初日の不在（`absence`）が設定され、Bob は初日に稼働可能である。
- **操作 (When)**:
  - `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - 遅延ペナルティを最小化するため、タスクの担当者が Bob に自動的に割り当てられ、初日に完了すること。

### シナリオ 12: 代替メンバ不在時または着手済みタスクにおける不在日スキップと作業継続 (AC-3)

- **前提 (Given)**:
  - ケース A: 必須スキルを持つ代替メンバが存在しない単一適任者タスク。
  - ケース B: 実績工数が既に記録された着手済みタスク（Alice 担当固定）。
  - 対象メンバ（Alice）の作業期間内に 1 日以上の不在日が設定されている。
- **操作 (When)**:
  - `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - 他メンバへ振り替えられることなく Alice が担当を維持し、不在日には作業が割り当てられず（スキップ）、翌稼働日以降に作業が継続されて完了すること。

### シナリオ 13: チーム祝日・週末・個別不在の複合環境での稼働判定 (AC-4)

- **前提 (Given)**:
  - 週末（土日）、チーム祝日、およびメンバ個別不在が連続または隣接して存在する。
- **操作 (When)**:
  - `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - 週末・祝日は全メンバ非稼働日、個別不在日は対象メンバのみ非稼働日として正しく判定され、稼働可能日のみに工数が割り当てられること。

### シナリオ 14: ベースライン計画との差分（Diff）算出 (AC-1)

- **前提 (Given)**:
  - ベースラインスケジュールと再計画後スケジュールが存在する。
- **操作 (When)**:
  - `compute_schedule_diff(baseline, replanned)` を実行する。
- **期待結果 (Then)**:
  - 全体 Makespan のスリップ日数（稼働日数差）、およびタスクごとの開始日差・終了日差・工期（稼働日数）差・担当者変更有無が正しく算出されること。

### シナリオ 15: 遅延原因の自動診断と主原因特定 (AC-2)

- **前提 (Given)**:
  - ケース A: タスク `task-1` で見積 8h に対し実績 6h + 残工数 6h = 12h（+4h 超過）が発生している。
  - ケース B: タスク `task-2` の担当メンバに作業期間中の不在日があり延伸している。
  - ケース C: タスク `task-3` は自身の工数増大はないが、先行タスク `task-1` の遅延により開始が後ろ倒しになっている。
- **操作 (When)**:
  - `compute_schedule_diff` を実行する。
- **期待結果 (Then)**:
  - ケース A: 主原因 `workload_increase`、超過工数（+4.0h）の詳細が出力されること。
  - ケース B: 主原因 `member_absence`、不在による延伸の詳細が出力されること。
  - ケース C: 主原因 `dependency_delay`、先行タスク遅延波及の詳細が出力されること。

### シナリオ 16: 納期超過タスクに対する推奨納期緩和日（Recommendations） (AC-3)

- **前提 (Given)**:
  - 再計画後スケジュールでタスクの終了日が納期（`deadline`）を超過している。
- **操作 (When)**:
  - `compute_schedule_diff` を実行する。
- **期待結果 (Then)**:
  - 当該タスクの現在の納期、推奨納期緩和日（再計画終了日以降）、遅延稼働日数を含む推奨オブジェクトが出力されること。

### シナリオ 17: Python API および CLI サブコマンドの動作 (AC-4)

- **前提 (Given)**:
  - 原本 YAML および `actuals.yaml` を含むディレクトリが存在する。
- **操作 (When)**:
  - Python API `taskweave.engine.replan(dir, as_of_date=...)` を呼び出す。
  - または CLI `taskweave replan <dir> --as-of <date> [--format text|json]` を実行する。
- **期待結果 (Then)**:
  - Python API は `{"baseline": ..., "replanned": ..., "diff": ...}` の構造化辞書を返すこと。
  - CLI はテキスト形式で視認性の高いサマリーレポートを標準出力に表示すること。
  - `--format json` 指定時はスキーマに合致する JSON 文字列を出力し終了コード 0 であること。
  - `--as-of` 未指定時は終了コード 2 (引数エラー) で終了すること。

### シナリオ 18: テストおよび品質ゲート全通過 (AC-5)

- **前提 (Given)**:
  - 新規作成した単体テスト（`test_diff.py`）および CLI テスト（`test_cli.py` の `replan` テスト）。
- **操作 (When)**:
  - `npm test`（pytest + node --test）および品質チェックコマンドを実行する。
- **期待結果 (Then)**:
  - 全テストが正常に通過し、フォーマット・静的解析・型チェック・OKF ドキュメントチェックすべてが成功すること。

---

## 5. 制約事項・スコープ外 (Out of Scope)

1. **複数メンバによる同一タスク実績の許容**:
   - 初期段階では「1タスク1担当者原則」を厳格に適用し、複数メンバによる実績記録はエラーとします。
2. **タイムスタンプ付き時間帯記録**:
   - 工数は日単位・時間数（h）で管理し、開始・終了時刻（例: 09:00〜18:00）は管理しません。
3. **原本 YAML の自動書き換え・破壊的更新**:
   - 再計画結果に基づく原本（`tasks.yaml` の納期変更など）の確定・自動更新機能は Milestone 4 で実装します（Milestone 3 では差分と推奨の出力に限定）。

---

## 6. 代替案と設計判断

- **`calendar.yaml` への `absences` 統合 vs `members.yaml` への休暇追加**:
  - **採択**: `calendar.yaml` の `absences` フィールドへの配置。
  - **理由**: 全社祝日（`holidays`）とメンバ個別不在（`absences`）はどちらもカレンダー（稼働日・非稼働日判定）に属する時系列情報であり、静的なメンバ属性（スキルや稼働上限）を管理する `members.yaml` を汚さないため。
- **実績工数（`actuals.yaml`）の独立ファイル化**:
  - **採択**: 別ファイル `actuals.yaml` の新設。
  - **理由**: 計画原本（`tasks.yaml`）と実績データ（`actuals.yaml`）を物理的に分離することで、元の見積工数や依存関係を保持したまま、任意の時点（As-of Date）からの再計算を可能にするため。
- **差分比較モジュールの分離 (`taskweave.diff`)**:
  - **採択**: ソルバー計算ロジック（`engine.py`）とは独立した `diff.py` への分離。
  - **理由**: 単一責務の原則（SRP）およびテスト容易性の観点から、計画計算処理と差分・診断評価ロジックを分離し、将来の可視化機能（M4）等からも再利用可能とするため。
