---
type: spec
title: スキーマ表現力 & 最適化強化仕様
description: 原本 YAML スキーマのルートキー対称性統一、非推奨警告、メンバー個別稼働曜日、担当者明示指定、負荷平準化およびタスク引き継ぎの仕様定義
tags: [schema, symmetry, deprecation, actuals, optimization, milestone-5]
status: accepted
issues: [50, 51, 52, 54]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-25T05:55:00Z }
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
  - **ストーリー 3 (Issue #52: 担当者の明示指定・推奨担当者サポート)**:
    - **As a**: プロジェクト管理者およびコーディングエージェント
    - **I want**: `tasks.yaml` においてタスクの担当者を「完全固定（`assigned_to`）」または「優先・推奨（`preferred_member`）」として指定できるようにしたい
    - **So that**: リードエンジニアが必ず担当すべき重要タスクや、特定ドメイン知識を持つ担当者に優先的に任せたいタスクの割当を柔軟に制御しつつ、自動スケジューリングの最適化を活用できるようにするため
  - **ストーリー 4 (Issue #53: 負荷平準化ソフト制約 - 今後予定)**:
    - **As a**: チームリード
    - **I want**: 同一スキルを持つ複数メンバー間で作業負荷が偏らないよう、全体の納期を損なわずに負荷が平準化されるようにしたい
    - **So that**: 特定のメンバーへの過負荷を防ぎ、健全なチーム稼働を維持するため
  - **ストーリー 5 (Issue #54: 着手済みタスクの引き継ぎ・再割当（Reassign / Handoff）のサポート)**:
    - **As a**: プロジェクト管理者および開発メンバー
    - **I want**: メンバーの急な長期離脱や体調不良、タスク優先度の変更に伴い、着手済みタスクの残工数を別メンバーへ引き継ぎ（Reassign / Handoff）て再計画したい
    - **So that**: 過去の実績（前任者が実施した作業ログ）を安全に保持したまま、残りの未完了工数だけを別メンバーに割り振ってプロジェクトを継続できるようにするため
- **背景と目的**:
  先行マイルストーンにおいて、Taskweave は原本 YAML（`members.yaml`, `tasks.yaml`, `calendar.yaml`, `actuals.yaml`）を基盤とした計画・実績追跡・再計画ワークフローを確立しました。
  しかし、原本タスク定義において特定メンバーへの担当割り当てを固定・推奨する構文が存在せず、CP-SAT ソルバーがスキル適合メンバーの中から任意に割り当てていました。
  本仕様では、原本 YAML の対称性統一（Issue #50）に続き、`tasks.yaml` にハード割当制約（`assigned_to`）およびソフト割当制約（`preferred_member`）を導入し、さらに実務で頻発する着手済みタスクの引き継ぎ（Issue #54: `handoff_to`）を原本 `actuals.yaml` にて安全に指定・検証・再計画・可視化できる仕組みを定義します。

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
- **FR-13 (`tasks.yaml` における明示的担当者指定 `assigned_to` - Issue #52)**:
  - `tasks.yaml` の各タスク定義に、任意の `assigned_to: <member_id>`（ハード割当制約）フィールドを指定可能とする。
  - `assigned_to` が指定されたタスクは、CP-SAT ソルバーにおいて該当メンバー以外への割当が禁止（`assigned[t, m] == 1`）される。
- **FR-14 (`tasks.yaml` における推奨担当者指定 `preferred_member` - Issue #52)**:
  - `tasks.yaml` の各タスク定義に、任意の `preferred_member: <member_id>`（ソフト割当制約）フィールドを指定可能とする。
  - `preferred_member` が指定されたタスクは、CP-SAT ソルバーの目的関数にペナルティ項を追加し、工期最短化（Makespan）を阻害しない範囲で優先的に指定メンバーへ割り当てられる（ペナルティ係数は Makespan 1日延伸のペナルティ 1,000 未満かつ前倒しペナルティ 1 を上回る 100 とする）。
- **FR-15 (`assigned_to` と `preferred_member` の相互排他バリデーション - Issue #52)**:
  - 同一タスクに `assigned_to` と `preferred_member` の双方が指定された場合、構文バリデーションエラーとして弾くこと。
- **FR-16 (割当指定の参照整合性およびスキル充足バリデーション - Issue #52)**:
  - `members.yaml` に存在しないメンバーIDの指定や、タスクの必須スキル（`required_skills`）を保有しないメンバーの指定を `assigned_to` / `preferred_member` の双方で検知し、適切な論理バリデーションエラーを出力すること。
- **FR-17 (`actuals.yaml` による実績優先原則 - Issue #52)**:
  - `actuals.yaml` で過去の作業実績ログが存在する場合、原本 `tasks.yaml` の `assigned_to` 指定よりも `actuals.yaml` の実績作業者が優先される原則とする（再計画および将来の引き継ぎ・再割当 #54 に対応）。
- **FR-18 (Infeasible 時のボトルネック診断 - Issue #52)**:
  - `assigned_to` のハード制約や該当メンバーのキャパシティ不足、納期制約違反等により解なし（`INFEASIBLE`）となった場合、ソルバーおよび CLI は明確なボトルネック診断情報を出力すること。
- **FR-19 (`actuals.yaml` におけるタスク引き継ぎ指定 `task_progress[].handoff_to` - Issue #54)**:
  - `actuals.yaml` の `task_progress` 配下の各タスク進捗定義に、任意の `handoff_to: <member_id>` フィールドを指定可能とする。`null`（または未指定）は引き継ぎなし（通常タスク）として許容する。
  - 着手済みタスクに `handoff_to` が指定された場合、原本 `tasks.yaml` の `assigned_to` や実績記録作業者よりも優先して未来の担当者として適用されること。
  - 完了済みタスク（`status: completed` または `remaining_hours: 0.0`）に対する `handoff_to` の指定は無効とし、バリデーションエラーとする。
  - 引き継ぎタスクにおいては、前任者（最大1名）と引き継ぎ先後任者の双方が `actuals.work_logs` に実績を記録することを許容する（1タスク1担当者原則の例外緩和）。
- **FR-20 (引き継ぎ先の存在性およびスキル充足バリデーション - Issue #54)**:
  - `validator.py` において、`validate_actuals` は `handoff_to` が非空文字列（または `null`）であることを構文検証し、完了済みタスクへの指定を検出すること。
  - `validate_logical_integrity` および `validate_schedule_inputs` において、引き継ぎ先メンバー（Handoff Recipient）が `members.yaml` に定義されており、かつタスクの必須スキル（`required_skills`）をすべて満たしていることを論理検証すること。
- **FR-21 (起算日 As-of Date による実績固定と残工数の引き継ぎ先割当 - Issue #54)**:
  - `engine.py` の再計画（`_solve_replan`）において、起算日（As-of Date）以前の実績工数・作業ログは前任者の実績として固定し、起算日以降の残工数（Remaining Hours）のみを引き継ぎ先メンバーのキャパシティに割り当てること。
- **FR-22 (出力スキーマの単一担当者互換性と引き継ぎメタデータ付与 - Issue #54)**:
  - 再計画出力（`result["tasks"][t_id]`）において、単一担当者モデルとの整合性を保つため `assigned_to: <後任者>` を基本としつつ、`handoff: {"from": <前任者>, "as_of": <起算日>}` メタデータを付与すること。
- **FR-23 (レポーティング出力における前任者・後任者の分割描画 - Issue #54)**:
  - Mermaid ガントチャート出力（`format_replan_mermaid`）において、前任者のセクションに過去実績期間（`[実績]`）を、後任者のセクションに未来予定期間（`[残工数]`）をそれぞれ分割描画し、可視化上の矛盾（後任者が過去に作業したかのような誤表示）を防ぐこと。
  - Markdown 表出力（`format_replan_markdown`）においても、同様に過去実績と未来予定を明確に分離して表示すること。
- **FR-24 (CLI `taskweave log` の `--handoff-to` オプションおよび差分表示 - Issue #54)**:
  - `taskweave log` コマンドで進捗更新時に引き継ぎ担当者を指定できる `--handoff-to <member_id>` オプションをサポートすること。
  - `taskweave replan` / `taskweave apply` の差分表示（`format_diff_summary`）において、引き継ぎ・再割当の差分を表示すること。

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

| フィールド名                              | 型             | 必須 | デフォルト | 説明・制約                                                                                                                                                                                                                                                                                                                              |
| :---------------------------------------- | :------------- | :--- | :--------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `actuals`                                 | object         | 推奨 | -          | 実績データのルートオブジェクト。                                                                                                                                                                                                                                                                                                        |
| `actuals.work_logs`                       | list of object | 任意 | `[]`       | 作業実績ログのリスト。                                                                                                                                                                                                                                                                                                                  |
| `actuals.work_logs[].date`                | string (date)  | 必須 | -          | 作業実施日。実在する `YYYY-MM-DD` 形式の日付文字列。                                                                                                                                                                                                                                                                                    |
| `actuals.work_logs[].member_id`           | string         | 必須 | -          | 作業を担当したメンバの ID。`members.yaml` に定義が存在すること。                                                                                                                                                                                                                                                                        |
| `actuals.work_logs[].task_id`             | string         | 必須 | -          | 作業対象のタスク ID。`tasks.yaml` に定義が存在すること。                                                                                                                                                                                                                                                                                |
| `actuals.work_logs[].hours`               | number         | 必須 | -          | 投入した実績工数（時間）。`0.1` 以上の `0.1` 刻みの正の有限数値。                                                                                                                                                                                                                                                                       |
| `actuals.task_progress`                   | list of object | 任意 | `[]`       | タスク進捗ステータスおよび明示的残工数のリスト。                                                                                                                                                                                                                                                                                        |
| `actuals.task_progress[].task_id`         | string         | 必須 | -          | 対象タスク ID。`tasks.yaml` に定義が存在すること。同一リスト内で重複不可。                                                                                                                                                                                                                                                              |
| `actuals.task_progress[].remaining_hours` | number         | 必須 | -          | 見積もり直した残工数（時間）。`0.0` 以上の `0.1` 刻みの有限数値。`status: completed` 時は `0.0`。                                                                                                                                                                                                                                       |
| `actuals.task_progress[].status`          | string         | 必須 | -          | タスク状態。`not_started`, `in_progress`, `completed` のいずれか。                                                                                                                                                                                                                                                                      |
| `actuals.task_progress[].handoff_to`      | string \| null | 任意 | `null`     | 引き継ぎ先メンバー ID。未完了タスク（残工数 > 0）の未来担当者を明示的に指定し、原本 `tasks.yaml` の `assigned_to` よりも優先される。`null` 許容。完了済みタスク（`status: completed` または `remaining_hours: 0.0`）への指定は不可。`members.yaml` に定義され、タスクの必須スキル（`required_skills`）をすべて満たすこと（Issue #54）。 |

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

### 3.5 `tasks.yaml` 拡張スキーマ (担当者指定・推奨 - Issue #52)

```yaml
tasks:
  - id: task-api
    title: "REST API 設計と実装"
    estimate_hours: 16.0
    required_skills:
      - backend
    assigned_to: alice # ハード制約: Alice 以外への割当を禁止
    depends_on: []
    deadline: "2026-09-20"

  - id: task-ui
    title: "フロントエンド画面実装"
    estimate_hours: 24.0
    required_skills:
      - frontend
    preferred_member: bob # ソフト制約: 全体工期を延ばさない限り Bob を優先割当
    depends_on:
      - task-api
    deadline: "2026-09-25"
```

#### フィールド詳細 (`tasks[]` 拡張)

| フィールド名               | 型     | 必須 | デフォルト | 説明・制約                                                                                                                                                           |
| :------------------------- | :----- | :--- | :--------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tasks[].assigned_to`      | string | 任意 | `null`     | ハード割当メンバー ID。指定メンバー以外への割当が禁止される。`members.yaml` に存在し、必須スキルをすべて満たす必要がある。`preferred_member` と同時指定不可。        |
| `tasks[].preferred_member` | string | 任意 | `null`     | ソフト割当メンバー ID。全体工期を阻害しない範囲で優先的に割り当てられる。`members.yaml` に存在し、必須スキルをすべて満たす必要がある。`assigned_to` と同時指定不可。 |

---

### 3.6 タスク引き継ぎ・再割当スキーマ (Handoff - Issue #54)

#### 3.6.1 `actuals.yaml` での引き継ぎ指定

```yaml
actuals:
  work_logs:
    - date: "2026-09-08"
      member_id: alice
      task_id: task-api
      hours: 8.0
    - date: "2026-09-09"
      member_id: alice
      task_id: task-api
      hours: 4.0

  task_progress:
    - task_id: task-api
      remaining_hours: 8.0
      status: in_progress
      handoff_to: bob # Alice から Bob への引き継ぎ指定 (Bob が残工数 8.0h を担当)
```

#### 3.6.2 再計画出力スキーマ (`result["tasks"][t_id]`)

再計画計算結果において、単一担当者モデルとの整合性を保つため `assigned_to` は後任者（`bob`）としつつ、引き継ぎ情報メタデータ `handoff` を付与します。

```json
{
  "tasks": {
    "task-api": {
      "assigned_to": "bob",
      "start_date": "2026-09-08",
      "end_date": "2026-09-11",
      "workdays_count": 4,
      "estimate_hours": 16.0,
      "total_logged_hours": 12.0,
      "remaining_hours": 8.0,
      "status": "in_progress",
      "daily_hours": {
        "2026-09-08": 8.0,
        "2026-09-09": 4.0,
        "2026-09-10": 4.0,
        "2026-09-11": 4.0
      },
      "handoff": {
        "from": "alice",
        "as_of": "2026-09-10"
      },
      "deadline": "2026-09-11",
      "delay_days": 0
    }
  }
}
```

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

### シナリオ 14: `assigned_to` による固定割当 (Issue #52 AC-1, AC-3, AC-7)

- **前提 (Given)**: `tasks.yaml` のタスクに `assigned_to: alice` が指定されている。Alice は必須スキルを満たしている。
- **操作 (When)**: `taskweave plan` または `solve_schedule` を実行する。
- **期待結果 (Then)**: 対象タスクの `assigned_to` が `alice` に確定し、他メンバーへの割当が行われないこと。

### シナリオ 15: `preferred_member` による推奨割当と工期最短化優先 (Issue #52 AC-1, AC-4, AC-7)

- **前提 (Given)**: 同一スキルを持つ Alice と Bob が存在し、タスクに `preferred_member: bob` が指定されている。
- **操作 (When)**: `taskweave plan` または `solve_schedule` を実行する。
- **期待結果 (Then)**:
  - 工期最短化（Makespan）が阻害されない状況では、優先的に Bob に割り当てられること。
  - Bob の稼働上限逼迫により全体工期が延びる場合は、ペナルティを許容して Alice に割り当てられ工期最短化が優先されること。

### シナリオ 16: `assigned_to` と `preferred_member` の同時指定エラー (Issue #52 AC-5)

- **前提 (Given)**: 同一タスクに `assigned_to: alice` と `preferred_member: bob` の双方が指定された `tasks.yaml` が存在する。
- **操作 (When)**: `validate_tasks` または `validate_project_data` を実行する。
- **期待結果 (Then)**: `valid == False` となり、同時指定不可のエラーメッセージが出力されること。

### シナリオ 17: 未定義メンバーおよびスキル不適合メンバー指定エラー (Issue #52 AC-2)

- **前提 (Given)**:
  - ケース A: `tasks.yaml` の `assigned_to` または `preferred_member` に存在しないメンバー ID が指定されている。
  - ケース B: `tasks.yaml` の `assigned_to` または `preferred_member` に、タスクの `required_skills` を持たないメンバーが指定されている。
- **操作 (When)**: `validate_project_data` を実行する。
- **期待結果 (Then)**: `valid == False` となり、適切な未定義参照エラーまたはスキル不適合エラーが出力されること。

### シナリオ 18: `actuals.yaml` 実績作業者の優先原則 (Issue #52 AC-6)

- **前提 (Given)**: 原本 `tasks.yaml` で `assigned_to: alice` と指定されているが、`actuals.yaml` で Bob による作業実績ログが記録されている着手済みタスクがある。
- **操作 (When)**: `taskweave replan --as-of <date>` または `_solve_replan` を実行する。
- **期待結果 (Then)**: 原本 `tasks.yaml` の指定に関わらず、実績に記録された Bob が担当者として優先・固定されること。

### シナリオ 19: `assigned_to` による Infeasible 検出とボトルネック診断 (Issue #52 AC-3)

- **前提 (Given)**: タスクに `assigned_to: alice` が指定されているが、Alice のキャパシティ不足や不在、先行依存等により納期・期間制約を満たせず解が存在しない。
- **操作 (When)**: `solve_schedule` または `taskweave plan` を実行する。
- **期待結果 (Then)**: `status` が `INFEASIBLE` となり、`diagnostics` および CLI 標準エラー出力に明確なボトルネック診断メッセージが出力されること。

### シナリオ 20: pytest 品質ゲート全通過 (Issue #51 AC-7, Issue #52 AC-7)

- **操作 (When)**: `test_validator.py`, `test_engine.py`, `test_cli.py` を含む全 pytest テストおよびリポジトリ品質ゲートを実行する。
- **期待結果 (Then)**: すべてのテストケースが成功すること。

### シナリオ 21: `handoff_to` による引き継ぎ指定と原本優先 (Issue #54 AC-1)

- **前提 (Given)**: 原本 `tasks.yaml` で `assigned_to: alice` のタスクに対し、Alice が過去に実績ログを記録しており、`actuals.yaml` の `task_progress` に `handoff_to: bob` が指定されている。
- **操作 (When)**: `taskweave replan --as-of <date>` または `_solve_replan` を実行する。
- **期待結果 (Then)**: 原本 `tasks.yaml` の `assigned_to: alice` よりも `handoff_to: bob` が優先され、起算日以降の残工数が Bob に割り当てられること。

### シナリオ 22: 引き継ぎ先の存在性、スキル検証および完了タスク制約 (Issue #54 AC-2)

- **前提 (Given)**:
  - ケース A: `actuals.yaml` の `task_progress` の `handoff_to` に存在しないメンバー ID が指定されている。
  - ケース B: `actuals.yaml` の `task_progress` の `handoff_to` に、タスクの `required_skills` を持たないメンバーが指定されている。
  - ケース C: 完了済みタスク（`status: completed` または `remaining_hours: 0.0`）に `handoff_to` が指定されている。
- **操作 (When)**: `validate_project_data` または `validate_schedule_inputs` を実行する。
- **期待結果 (Then)**: `valid == False`（または `ValueError`）となり、未定義メンバー参照、必須スキル不適合、または完了済みタスクへの指定不可の明確なエラーが出力されること。

### シナリオ 23: 起算日前後の実績固定と残工数割当 (Issue #54 AC-3)

- **前提 (Given)**: タスク `task-api` に対し、起算日（`2026-09-10`）以前に Alice が 12 時間の実績を記録しており、`task_progress` で `handoff_to: bob`、`remaining_hours: 8.0` が指定されている。
- **操作 (When)**: `replan` を実行する。
- **期待結果 (Then)**:
  - 起算日以前の 12 時間は Alice の作業実績（`member_daily_work["alice"]`）として固定されること。
  - 起算日以降の残工数 8 時間のみが Bob のキャパシティ（`member_daily_work["bob"]`）に割り当てられること。

### シナリオ 24: 出力スキーマでの単一担当者互換性と引き継ぎメタデータ (Issue #54 AC-4)

- **前提 (Given)**: Alice から Bob への引き継ぎタスクを含む再計画が実行される。
- **操作 (When)**: 出力 JSON の `result["tasks"][t_id]` を確認する。
- **期待結果 (Then)**:
  - `assigned_to` が後任者 `"bob"` であること。
  - `handoff` オブジェクトが存在し、`{"from": "alice", "as_of": <起算日>}` が正しく記録されていること。

### シナリオ 25: レポーティング出力における前任者・後任者の分割描画 (Issue #54 AC-5)

- **前提 (Given)**: Alice から Bob への引き継ぎタスクを含む再計画結果が存在する。
- **操作 (When)**: `format_replan_mermaid` および `format_replan_markdown` を実行する。
- **期待結果 (Then)**:
  - Mermaid ガントチャートにおいて、`section alice` に `task-api [実績] : done, ...` が描画され、`section bob` に `task-api [残工数] : active, ...` が描画されること。
  - Markdown 表において、前任者の過去実績期間と後任者の未来予定期間が矛盾なく分割表示されること。

### シナリオ 26: CLI `taskweave log --handoff-to` および差分表示 (Issue #54 AC-6)

- **前提 (Given)**: 有効な原本ディレクトリが存在する。
- **操作 (When)**: `taskweave log <date> --member alice --task task-api --hours 4.0 --remaining 8.0 --handoff-to bob` を実行し、続いて `taskweave replan` / `taskweave apply` を実行する。
- **期待結果 (Then)**:
  - `actuals.yaml` の `task_progress` に `handoff_to: bob` が記録されること。
  - `taskweave replan` および `taskweave apply` の差分表示において、引き継ぎ情報（Alice -> Bob）が表示されること。

---

## 5. 制約事項・スコープ外 (Out of Scope)

- **旧形式の強制エラー化**: Milestone 5 では後方互換性を最優先し、エラーにはせず非推奨警告（Warning）にとどめる。
- **他原本ファイルのルートキー省略許容**: `members.yaml`, `tasks.yaml`, `calendar.yaml` は現行どおりルートキー必須を維持し、ルートキーなしは許容しない（RFC #38 の合意に基づく）。
- **一括マイグレーション専用 CLI**: `taskweave migrate` 等の専用コマンドは現時点では実装せず、`taskweave log` による通常運用時の安全な自動変換で対応する（YAGNI 原則）。
- **計画系 CLI コマンド（plan, replan, apply）での警告出力抑制**: JSON や Mermaid の標準出力パイプラインおよび自動化スクリプトとの親和性を保つため、警告出力は検証専門コマンド（`taskweave validate`）に集約し、`plan`, `replan`, `apply` などの計算・適用系コマンドでは warnings の標準エラー出力を抑制する設計とする（バリデーション失敗のエラーのみ stderr に出力）。
- **複数担当者の同時割り当て（ペア作業）**: 1タスク1担当者制約（FR-5）を維持し、複数人での同時分担は対象外とする。
- **`preferred_member` のペナルティ調整**: ペナルティ係数は固定値 `100` とし、動的重み付け設定やユーザー任意指定は対象外とする（YAGNI 原則）。
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
- **設計判断 E: 推奨メンバーペナルティ係数の選定**:
  - **検討**: 目的関数における `preferred_member` 非割り当て時のペナルティ係数。
  - **決定**: `100`。
  - **理由**: Makespan 最小化の重み（`1,000`）より小さく、かつ各タスクの前倒し重み（`1`）や中抜け抑制重み（`1`）より大きく設定することで、完了日のズレ（1/日）で推奨割当が逆転することなく、「工期が延びない限りは確実に推奨メンバーへ割り当て、工期が延びる場合は工期短縮を最優先する」という振る舞いを決定論的に保証するため。
- **設計判断 F: `assigned_to` と `preferred_member` の相互排他**:
  - **検討**: 同一タスクに両方指定された場合、`assigned_to` を優先適用して `preferred_member` を無視する案。
  - **決定**: バリデーションエラーとして弾く。
  - **理由**: ハード制約（完全固定）とソフト制約（推奨）を同一タスクに書くことは意図が矛盾しており、設定者の記述ミスを早期に検知・防止するため。
