---
type: spec
title: 実績工数・個別不在の原本スキーマおよび論理整合性仕様
description: actuals.yaml および calendar.yaml の absences の原本スキーマ定義と論理整合性検証ルール
tags: [schema, yaml, actuals, absences, replanning, milestone-3]
status: implemented
issues: [25]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-12T03:13:00Z }
verified: { by: human:high-soar, at: 2026-09-12T03:13:05Z }
---

# 実績工数・個別不在の原本スキーマおよび論理整合性仕様 (004-actuals-and-replanning)

## 1. 概要とユーザーストーリー

- **ユーザーストーリー**:
  - **As a**: プロジェクト管理者およびコーディングエージェント
  - **I want**: メンバの日々の作業実績工数（`actuals.yaml`）とメンバ個別不在（`calendar.yaml` の `absences`）を原本 YAML として定義し、構文・型・論理整合性を検証できるようにしたい
  - **So that**: 計画原本（`members.yaml`, `tasks.yaml`, `calendar.yaml`）を破壊することなく実績と不在を安全に保持し、不正なデータによる再計算クラッシュを未然に防ぐため
- **背景と目的**:
  Milestone 2 では初期計画の自動算出エンジンを確立しました。続く Milestone 3 では、進行中プロジェクトにおいて日々発生する作業実績工数や突発的な休暇・欠勤を考慮した再計画（Replanning）を実現します。
  本仕様では、再計画の入力となる実績原本ファイル（`actuals.yaml`）およびカレンダー拡張（個別不在 `absences`）のデータスキーマを定義し、静的検証（型・構文）および論理整合性検証（存在参照、排他制御、1タスク1担当者原則など）の規則を確立します。

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

### 2.2 非機能要件 (NFR: Non-Functional Requirements)

- **NFR-1 (SSOT と原本保護)**: 実績データや個別不在は独立した原本ファイル・スキーマで管理し、ベースライン計画データ（`tasks.yaml` の見積工数など）を破壊・変更しないこと。
- **NFR-2 (決定論性と完全性)**: 同一の原本データに対して常に同一の検証結果を返すこと。浮動小数点誤差による判定ブレを起こさないこと。
- **NFR-3 (YAGNI 原則)**: 複数メンバでの同時実績記録や、分単位の時間帯記録（例: 09:00〜18:00）は行わず、日単位・0.1h 刻みに限定すること。

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

---

## 5. 制約事項・スコープ外 (Out of Scope)

1. **複数メンバによる同一タスク実績の許容**:
   - 初期段階では「1タスク1担当者原則」を厳格に適用し、複数メンバによる実績記録はエラーとします。
2. **タイムスタンプ付き時間帯記録**:
   - 工数は日単位・時間数（h）で管理し、開始・終了時刻（例: 09:00〜18:00）は管理しません。
3. **実績の自動スケジュール再計算（Replanning アルゴリズム）**:
   - 本仕様はデータスキーマと整合性検証（Issue #25）を対象とします。再計画計算（As-of Date による残工数スケジューリング）は次課題 Issue #26 で実装します。

---

## 6. 代替案と設計判断

- **`calendar.yaml` への `absences` 統合 vs `members.yaml` への休暇追加**:
  - **採択**: `calendar.yaml` の `absences` フィールドへの配置。
  - **理由**: 全社祝日（`holidays`）とメンバ個別不在（`absences`）はどちらもカレンダー（稼働日・非稼働日判定）に属する時系列情報であり、静的なメンバ属性（スキルや稼働上限）を管理する `members.yaml` を汚さないため。
- **実績工数（`actuals.yaml`）の独立ファイル化**:
  - **採択**: 別ファイル `actuals.yaml` の新設。
  - **理由**: 計画原本（`tasks.yaml`）と実績データ（`actuals.yaml`）を物理的に分離することで、元の見積工数や依存関係を保持したまま、任意の時点（As-of Date）からの再計算を可能にするため。
