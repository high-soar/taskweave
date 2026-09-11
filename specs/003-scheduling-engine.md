---
type: spec
title: 計算エンジンの入出力および制約モデル仕様
description: Python / OR-Tools CP-SAT を用いたスケジューリング計算モデル、入出力データ構造、および制約充足仕様
tags: [scheduling, engine, or-tools, milestone-2]
status: accepted
issues: [12, 13, 14, 15, 16]
generated: { by: antigravity/gemini-3.8-flash, at: 2026-09-10T15:15:00Z }
verified: { by: human:high-soar, at: 2026-09-11T11:42:00Z }
---

# 計算エンジンの入出力および制約モデル仕様 (003-scheduling-engine)

## 1. 概要とユーザーストーリー

- **ユーザーストーリー**:
  - **As a**: コーディングエージェントおよびプロジェクト計画担当者
  - **I want**: 原本 YAML（メンバ・タスク・カレンダー）を読み込み、制約（稼働上限・依存関係・スキル・納期）を満たす最適なスケジュール案を Python / OR-Tools で自動計算・診断したい
  - **So that**: 手作業での複雑な調整を排除し、チームの稼働日やスキルに即した実行可能な最短計画を立案し、納期超過時にはボトルネックを早期に特定するため
- **背景と目的**:
  Taskweave では原本 YAML（`members.yaml`, `tasks.yaml`, `calendar.yaml`）で計画の前提条件を管理します。
  本仕様は、原本データを入力として受け取り、Google OR-Tools の CP-SAT（Constraint Programming - Satisfiability）ソルバーを用いてスケジュール案（タスク開始日・終了日・日別工数・担当者）を自動計算し、制約を満たせない場合は診断結果を出力する計算エンジン（Scheduling Engine）の仕様を定義します。

---

## 2. 要件定義

### 2.1 機能要件 (FR: Functional Requirements)

- **FR-1 (原本 YAML 読み込み)**:
  - `members.yaml`、`tasks.yaml`、`calendar.yaml` を読み込み、計算エンジン内部のデータモデルに変換できること。
- **FR-2 (稼働上限制約)**:
  - 各メンバの1日稼働時間（標準 8 時間 × `max_capacity`）を超えるタスク割り当てを行わないこと。
- **FR-3 (タスク先行依存関係制約)**:
  - タスクの `depends_on` に指定された先行タスクがすべて完了した翌稼働日以降に、後続タスクの作業を開始すること。
- **FR-4 (スキル制約)**:
  - タスクの `required_skills` に指定されたすべてのスキルを保有するメンバにのみ、そのタスクを割り当てること。スキル指定が空の場合は全メンバを担当候補とすること。
- **FR-5 (1タスク1担当者制約 - YAGNI)**:
  - 1つのタスクは同時に1人のメンバのみが担当すること（複数メンバでの同時分担は初期 MVP では行わない）。
- **FR-6 (カレンダー・非稼働日考慮)**:
  - 週の標準非稼働日（土日等）および祝日・特別休暇（`calendar.yaml` の `holidays`）には作業工数を割り当てずスキップすること。
  - 実カレンダー日付（`YYYY-MM-DD`）ベースでタスクの開始日・終了日を出力すること。
- **FR-7 (工期最適化 - Makespan 最小化)**:
  - 全タスクの完了までの総所要稼働日数（Makespan）を最小化し、可能な限り前倒しで完了するスケジュールを探索すること。
- **FR-8 (納期制約 & Infeasible 診断)**:
  - 各タスクの `deadline` を評価し、納期超過が発生する場合は異常終了せず、超過日数・遅延タスク名などのボトルネック診断情報を出力できること。
  - プロジェクト開始日より前の過去日付が `deadline` に設定されている場合でも、開始日までの稼働日数を含めた正確な遅延日数が診断情報として算出されること。
- **FR-9 (中抜け抑制)**:
  - 稼働日ベースで、タスクの着手から完了までの間に不要な作業中断（中抜け）が発生しないよう最適化すること。
- **FR-10 (未定義依存関係の入力検証)**:
  - タスクの `depends_on` に存在しないタスク ID が含まれる場合、暗黙に無視せず入力エラー（`ValueError`）として計算を拒否すること（`001-yaml-schema` の FR-7 と整合）。
- **FR-11 (動的計画地平)**:
  - タスク総工数とメンバ稼働キャパシティに応じて、必要な計画地平（Horizon）を自動的に計算・拡張し、長期タスクであっても解が存在する限り `INFEASIBLE` と誤判定しないこと。

### 2.2 非機能要件 (NFR: Non-Functional Requirements)

- **NFR-1 (計算速度・スケーラビリティ)**:
  - タスク数数十件、メンバ数数名〜十数名程度の一般的なスプリント/プロジェクト計画において、数秒以内（タイムアウト上限: 10秒）で最適解または実行可能解を出力できること。
- **NFR-2 (決定論的再現性)**:
  - 同一の入力データ、同一のプロジェクト開始日に対しては、常に一貫した同一のスケジュール解を出力すること（ソルバーのランダムシード固定）。
- **NFR-3 (クリーンな依存分離)**:
  - 計算エンジン本体は CLI やフロントエンドに依存せず、純粋な Python ライブラリ / モジュールとしてインポート・単体テスト可能であること。

### 2.3 ディレクトリ構成およびパッケージ境界 (Node.js / Python 共存方針)

- **Python 実装配置**: Python 本体実装は `python/src/taskweave/` に配置し、`scripts/spikes/` のスパイクコードから本体コードを直接参照しない。
- **依存管理**: `python/pyproject.toml` および `python/uv.lock` で依存関係を管理する。
- **テスト配置**: Python のテストコードは `python/tests/` に配置し、`pytest` で実行する。
- **データと仕様の共有**: `examples/` の YAML 原本および `specs/` の仕様書は Node.js / Python 間で共通利用し、重複を持たない。
- **YAGNI 原則の遵守**: `models/`, `loader/`, `scheduler/` などの過剰なサブディレクトリ分割は行わず、フラットで簡潔なモジュール構成を維持する。
- **CI / 品質ゲート連携**: ルートの `npm test` から `uv run --project python pytest python/tests` を実行し、リポジトリ全体の一貫した検証入口を保つ。

---

## 3. 数理モデル定義 (OR-Tools CP-SAT)

### 3.1 時間の離散化単位 (Time Discretization)

CP-SAT は整数変数のみを扱うため、実数である工数・稼働上限を以下の整数スケーリングでモデル化します。

- **スケール係数 ($S$)**: `10`（$0.1\text{ 時間} = 1\text{ 単位}$）
- **標準稼働時間**: $8.0\text{ 時間} \rightarrow 80\text{ 単位}$
- **メンバ1日稼働上限 ($C_m$)**: $\text{round}(8.0 \times \text{max\_capacity}_m \times 10)$
  - 例: `max_capacity: 1.0` $\rightarrow 80$ (8.0h)
  - 例: `max_capacity: 0.8` $\rightarrow 64$ (6.4h)
- **タスク見積工数 ($E_t$)**: $\text{round}(\text{estimate\_hours}_t \times 10)$
  - 例: `estimate_hours: 16` $\rightarrow 160$ (16.0h)
  - 例: `estimate_hours: 24` $\rightarrow 240$ (24.0h)

### 3.2 計画地平とカレンダーマッピング (Planning Horizon & Calendar)

1. プロジェクト開始日（$D_{\text{start}}$）から、稼働日判定ルール（`workdays` および `holidays` を除外）を満たす稼働日を順に抽出し、稼働日インデックス配列 $W = [d_0, d_1, d_2, \dots, d_{H-1}]$ を構築します（計画地平 $H$: デフォルト 30〜60 稼働日）。
2. ソルバー内部の「日変数 $d$」は、実カレンダー日付ではなくこの**稼働日インデックス $0 \le d < H$** を表します。
3. これにより、土日・祝日は探索空間から完全に除外され、非稼働日への不正な割り当てが構造的に防止されます。

### 3.3 決定変数 (Decision Variables)

| 変数名                   | 定義域                                                 | 説明                                                                                |
| :----------------------- | :----------------------------------------------------- | :---------------------------------------------------------------------------------- |
| $\text{assigned}_{t, m}$ | $\{0, 1\}$ (Bool)                                      | タスク $t$ をメンバ $m$ が担当する場合に 1                                          |
| $\text{work}_{t, m, d}$  | $[0, \min(C_m, E_t)]$ (Int)                            | 稼働日 $d$ にメンバ $m$ がタスク $t$ に割り当てる工数（0.1h 単位）                  |
| $\text{start\_day}_t$    | $[0, H-1]$ (Int)                                       | タスク $t$ の開始稼働日インデックス                                                 |
| $\text{end\_day}_t$      | $[0, H-1]$ (Int)                                       | タスク $t$ の完了稼働日インデックス                                                 |
| $\text{delay}_t$         | $[0, \max(H, (H - 1) - \text{deadline\_day}_t)]$ (Int) | タスク $t$ の納期超過稼働日数（納期内なら 0。開始前納期でも動的上限により解を保証） |
| $\text{makespan}$        | $[0, H]$ (Int)                                         | 全タスク完了までの最大稼働日インデックス                                            |

### 3.4 制約条件 (Constraints)

1. **1タスク1担当者制約**:
   $$\sum_{m \in M} \text{assigned}_{t, m} = 1 \quad (\forall t \in T)$$
2. **スキル制約**:
   タスク $t$ の要求スキル $\text{required\_skills}_t$ をすべて満たさないメンバ $m$ に対して:
   $$\text{assigned}_{t, m} = 0$$
3. **担当メンバ限定の作業割当**:
   $$\text{work}_{t, m, d} \le E_t \times \text{assigned}_{t, m} \quad (\forall t, m, d)$$
4. **タスク総工数の充足**:
   $$\sum_{m \in M} \sum_{d=0}^{H-1} \text{work}_{t, m, d} = E_t \quad (\forall t \in T)$$
5. **メンバ日別稼働上限**:
   $$\sum_{t \in T} \text{work}_{t, m, d} \le C_m \quad (\forall m \in M, \forall d \in [0, H-1])$$
6. **作業期間のバインド (開始日・終了日)**:
   日 $d$ にタスク $t$ の作業が存在する場合（$\sum_m \text{work}_{t, m, d} > 0$）:
   $$\text{start\_day}_t \le d \quad \text{かつ} \quad \text{end\_day}_t \ge d$$
   また、期間外の作業は禁止（$d < \text{start\_day}_t \lor d > \text{end\_day}_t \implies \text{work} = 0$）。
7. **タスク先行依存関係 (depends_on)**:
   タスク $t_{\text{prev}} \in \text{depends\_on}(t)$ に対し:
   $$\text{start\_day}_t > \text{end\_day}_{t_{\text{prev}}}$$
   （先行タスクの完了日の翌稼働日以降に開始）
8. **納期評価と遅延変数の定義**:
   タスク $t$ の納期に対応する稼働日インデックスを $\text{deadline\_day}_t$ とするとき:
   $$\text{delay}_t \ge \text{end\_day}_t - \text{deadline\_day}_t, \quad \text{delay}_t \ge 0$$
   - プロジェクト開始日より前の過去納期が指定された場合、$\text{deadline\_day}_t$ は負の稼働日インデックス（開始日までの稼働日数差）として表現されます。
   - $\text{delay}_t$ の上限は各タスクの納期から動的に $\max(H, (H - 1) - \text{deadline\_day}_t)$ として導出され、数年前の極端な過去納期であっても解空間が飽和して `INFEASIBLE` になることを防ぎます。
9. **全体工期 (Makespan) の定義**:
   $$\text{makespan} \ge \text{end\_day}_t \quad (\forall t \in T)$$

### 3.5 目的関数 (Objective Function)

複数の目標を優先度順に重み付けして最小化します。

$$\min \left( 10000 \times \sum_{t \in T} \text{delay}_t + 100 \times \text{makespan} + 5 \times \sum_{t \in T} \text{end\_day}_t + 2 \times \sum_{t \in T} (\text{end\_day}_t - \text{start\_day}_t) \right)$$

- **第1項 (重み 10,000)**: 納期遅延の最小化（最優先）
- **第2項 (重み 100)**: 全体工期 Makespan の最小化
- **第3項 (重み 5)**: 各タスクの前倒し完了促進
- **第4項 (重み 2)**: 各タスクの所要スパンの最小化（不要な中抜けの抑制）

---

## 4. 入出力インターフェース仕様

### 4.1 入力データ

- 原本 YAML ディレクトリ（`members.yaml`, `tasks.yaml`, `calendar.yaml`）
- プロジェクト開始日（`project_start_date`: `YYYY-MM-DD` 形式）

### 4.2 出力データスキーマ (JSON / Dictionary)

計算結果は以下の構造で返却されます。

```json
{
  "status": "OPTIMAL", // OPTIMAL | FEASIBLE | INFEASIBLE
  "project_start_date": "2026-09-01",
  "makespan_workdays": 5,
  "tasks": {
    "task-api": {
      "assigned_to": "alice",
      "start_date": "2026-09-01",
      "end_date": "2026-09-02",
      "workdays_count": 2,
      "estimate_hours": 16.0,
      "daily_hours": {
        "2026-09-01": 8.0,
        "2026-09-02": 8.0
      },
      "deadline": "2026-09-20",
      "delay_days": 0
    },
    "task-ui": {
      "assigned_to": "alice",
      "start_date": "2026-09-03",
      "end_date": "2026-09-07",
      "workdays_count": 3,
      "estimate_hours": 24.0,
      "daily_hours": {
        "2026-09-03": 8.0,
        "2026-09-04": 8.0,
        "2026-09-07": 8.0
      },
      "deadline": "2026-09-25",
      "delay_days": 0
    }
  },
  "member_daily_work": {
    "alice": {
      "2026-09-01": 8.0,
      "2026-09-02": 8.0,
      "2026-09-03": 8.0,
      "2026-09-04": 8.0,
      "2026-09-07": 8.0
    },
    "bob": {}
  },
  "diagnostics": {
    "is_deadline_violated": false,
    "delayed_tasks": []
  }
}
```

#### 納期遅延・ボトルネック発生時の診断出力例 (`diagnostics`)

```json
{
  "diagnostics": {
    "is_deadline_violated": true,
    "delayed_tasks": [
      {
        "task_id": "task-ui",
        "delay_workdays": 3,
        "deadline": "2026-09-02",
        "projected_end_date": "2026-09-07",
        "reason": "先行タスク task-api の完了待ちおよび日別稼働上限により納期に未達"
      }
    ]
  }
}
```

---

## 5. 受入基準とテストシナリオ (TDD 連携)

### シナリオ 1: 稼働上限とタスク依存関係を満たす基本計算 (#12)

- **前提 (Given)**:
  - メンバ Alice (稼働上限 1.0 = 8h/日) が存在。
  - 先行タスク A (16h) と後続タスク B (24h, A に依存) が存在。
- **操作 (When)**:
  - 計算エンジンでスケジュールを解く。
- **期待結果 (Then)**:
  - Alice の 1 日の稼働合計時間が 8.0h を超えないこと。
  - タスク B の開始日がタスク A の完了日よりも後（翌稼働日以降）であること。
  - 総工期が 5 稼働日（A: 2日 + B: 3日）となること。

### シナリオ 2: 祝日および非稼働曜日のスキップ (#13)

- **前提 (Given)**:
  - 開始日が 2026年9月11日（金）。土日は非稼働。2026年9月15日（火）が祝日。
  - 16h (2稼働日) のタスクが存在。
- **操作 (When)**:
  - 計算エンジンでスケジュールを解く。
- **期待結果 (Then)**:
  - 1日目: 2026-09-11 (金, 8h)。
  - 2日目: 2026-09-12 (土), 09-13 (日), 09-15 (祝) をスキップし、2026-09-14 (月, 8h) に割り当てられること。
  - 祝日や土日に作業時間が割り当てられないこと。

### シナリオ 3: 必須スキルに基づく割当制約 (#14)

- **前提 (Given)**:
  - Alice はスキル `[frontend, backend]`、Bob は `[backend, devops]` を保有。
  - タスク X は `required_skills: [frontend]`、タスク Y は `required_skills: [devops]`。
- **操作 (When)**:
  - スケジュールを計算する。
- **期待結果 (Then)**:
  - タスク X の担当者が Alice に、タスク Y の担当者が Bob に自動的に割り当てられること。

### シナリオ 4: 納期超過時の検知とボトルネック診断 (#15)

- **前提 (Given)**:
  - 開始後 2 稼働日で完了不可能な工数（合計 40h）のタスク群に対して、`deadline` が開始後 2 日目、あるいは開始日より前の日付に指定されている。
- **操作 (When)**:
  - スケジュールを計算する。
- **期待結果 (Then)**:
  - 計算エンジンが異常終了せず結果を返すこと。
  - `diagnostics.is_deadline_violated` が `true` となり、遅延タスク ID と超過日数が報告されること。

### シナリオ 5: 未定義依存関係の検証エラー

- **前提 (Given)**:
  - タスクの `depends_on` に `tasks.yaml` 内に存在しないタスク ID が指定されている。
- **操作 (When)**:
  - スケジュールを計算する。
- **期待結果 (Then)**:
  - 暗黙に先行制約を無視せず、`ValueError`（未定義タスク参照エラー）を送出して計算を中断すること。

### シナリオ 6: 動的計画地平による長期タスクの解決

- **前提 (Given)**:
  - 30 稼働日を超える工数（例: 248h、1.0 capacity のメンバで 31 稼働日必要）のタスクが存在する。
- **操作 (When)**:
  - 地平日数を指定せず（デフォルト）スケジュールを計算する。
- **期待結果 (Then)**:
  - 地平が自動的に必要十分な日数まで拡張され、`INFEASIBLE` にならず `OPTIMAL` でスケジュールが算出されること。

---

## 6. 制約事項・スコープ外 (Out of Scope)

YAGNI 原則（不要な複雑性の排除）に基づき、以下の項目は本マイルストーンのスコープ外とします。

1. **タスクの複数メンバ同時担当**:
   - 1 つのタスクを複数メンバで分担する機能は見送ります（タスクは 1 人が担当）。
2. **日単位より細かい粒度（分・時間帯指定）**:
   - 計画は「日」単位、工数は「時間（0.1h 単位）」とし、9:00〜11:00 といった時間帯の割り当ては含めません。
3. **実績工数（Actuals）の反映**:
   - 消化実績を踏まえた再計画は Milestone 3 で扱います。

---

## 7. 代替案と設計判断 (Spike 検証結果)

- **日別スロット変数 vs インターバル変数 (`NewIntervalVar`)**:
  - **採択**: 日別スロット変数 `work[t, m, d]` + 稼働日インデックス。
  - **理由**: 小数稼働上限（例: 0.8 capacity = 6.4h/日）において、日ごとの作業時間を柔軟かつ厳密に管理でき、土日・祝日のスキップ処理も稼働日インデックスとの事前マッピングにより最もシンプルかつ高速に実現できるため。
- **ハード制約での解なし vs ペナルティ付きソフト制約**:
  - **採択**: 納期遅延ペナルティ最小化（ソフト制約）による最適化。
  - **理由**: ハード制約にすると納期オーバー時に単に `INFEASIBLE`（解なし）となり、どのタスクが何日超過しているのか、どうすれば計画が成立するかの診断情報を得られないため。ペナルティを重く設定することで、納期厳守可能な場合は最短納期で解き、不可能な場合は遅延最小のベストエフォート解とボトルネック診断を同時に出力できるため。
