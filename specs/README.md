---
type: index
title: Taskweave 仕様書
description: Taskweave の仕様書と仕様書ライフサイクルの案内
tags: [specifications, documentation, index]
status: stable
generated: { by: copilot/chat, at: 2026-09-10T12:09:08Z }
---

# Taskweave 仕様書 (Specs)

このディレクトリは、Taskweave の機能要件、原本 YAML スキーマ、計算制約、CLI インターフェースなどの仕様（Specification）を管理する正本（SSOT）です。

開発は **SDD（仕様駆動開発 / Spec-Driven Development）** に基づき、コードやテストを書く前に仕様書を作成・合意します。
すべての仕様書は **Open Knowledge Format (OKF v0.2)** に準拠し、YAML フロントマターによるメタデータ管理・アクター記録・トラストティア判定を行います（詳細は [okf スキル](../.github/skills/okf/SKILL.md) を参照）。

---

## 仕様書のライフサイクル

仕様書は以下のステータスで状態を管理します。

| ステータス         | 説明                                               | 次のアクション                                     |
| :----------------- | :------------------------------------------------- | :------------------------------------------------- |
| **`Draft`**        | 仕様の初期起草段階。未確定要素や検討事項を含む。   | 開発者やチームによる仕様のブラッシュアップ         |
| **`Under Review`** | 仕様案がまとまり、レビュー・合意を待っている状態。 | 仕様のレビュー、フィードバック対応                 |
| **`Accepted`**     | 仕様が合意された状態。                             | **TDD フェーズへの移行（テスト先行作成）**         |
| **`Implemented`**  | 仕様に基づくテストと実装が完了し、検証済みの状態。 | 保守・運用（改修時は新たな仕様書を作成または更新） |
| **`Superseded`**   | 新しい仕様によって置き換えられた状態。             | 参照用として保管（最新仕様へのリンクを記載）       |

---

## ファイル命名規則

仕様書ファイルは、識別しやすいように連番と英語のスラッグ（ハイフン区切り）を付けて命名します。

```text
specs/
├── README.md                          # このファイル
├── templates/
│   └── spec-template.md               # 仕様書テンプレート
└── 001-yaml-schema.md                 # 原本 YAML スキーマ定義 (M1)
```

---

## 仕様書一覧

仕様書のカタログ正本（AI・ツール向けインデックス）は [`index.md`](index.md) です。人間向けの概要は以下の表のとおりです。

| 連番 / ファイル名                                                  | タイトル                       | ステータス    | 関連 Issue                                                                                                                                                          | 概要                                                                    |
| :----------------------------------------------------------------- | :----------------------------- | :------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------- |
| [`001-yaml-schema.md`](001-yaml-schema.md)                         | 原本 YAML スキーマ定義         | `Implemented` | [#1](https://github.com/high-soar/taskweave/issues/1), [#2](https://github.com/high-soar/taskweave/issues/2), [#3](https://github.com/high-soar/taskweave/issues/3) | メンバ・タスク・制約・カレンダーの原本データモデルおよび検証 CLI の仕様 |
| [`002-okf-document-management.md`](002-okf-document-management.md) | OKF 文書管理とタグインデックス | `Accepted`    | -                                                                                                                                                                   | Git 管理 Markdown の frontmatter、タグ集約 index、検査 CLI の仕様       |

---

## 仕様書の作成フロー

1. [`templates/spec-template.md`](templates/spec-template.md) をコピーして `specs/<連番>-<タイトル>.md` を作成する。
2. 概要、要件、データ構造（YAML スキーマ）、受入基準（Acceptance Criteria）、エッジケースを明記する。
3. レビューを行い、ステータスを `Accepted` に更新する。
4. 受入基準をもとに TDD（テスト作成 -> 最小実装 -> リファクタリング）を開始する。
