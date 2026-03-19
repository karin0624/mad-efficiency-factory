# Spec ライフサイクル運用ルール

根拠ADR: `.kiro/decisions/governance/0001-role-based-spec-classification.md`

## 5層モデルと管理戦略

仕様情報を役割に基づき5層に分類し、層ごとに管理戦略を定める。

| 層 | 名称 | 役割 | 管理戦略 |
|---|------|------|---------|
| 1 | Steering | 前提（目的・制約・規約） | 永続 |
| 2 | Requirements | 契約（受入条件・外部仕様） | 永続 |
| 3 | Design | 設計（判断と構造説明の混在） | 部分的に永続 |
| 4 | ADR | 意思決定ログ（なぜその設計か） | 永続 |
| 5 | Tasks | 実行計画（タスク分解・進捗） | 一時的 |

## Requirements（層2）の運用

- Requirements はコードとは**役割が異なる**規範的権威を持つ。コードとの内容重複は二重管理ではない
- ドリフト検出時（コードが requirements と乖離した場合）は、自動修正せず**人間判断を必須**とする
- フィードバック対象は**要求認識のズレ**に限定する（制約上の不成立、暗黙的な実装固定、エラー時の抜け漏れ等）
- 内部実装の詳細な差異は報告しない

## Design（層3）の運用

design.md には**判断セクションのみ**を永続化する。生成可能なセクションは書かない。

### 永続化する（判断セクション）
- Overview
- Architecture Pattern 選択
- Tech Stack
- コンポーネント Intent / Responsibilities / Constraints
- Error Handling Strategy
- Testing Strategy

### 書かない（生成可能）
- Mermaid 図
- Requirements Traceability 表
- Service Interface シグネチャ
- 物理 Data Models
- Implementation Changelog

レビュー用の図表資料が必要な場合は、Plan/Modify コマンドの拡張で「レビュー用文書」として別途生成する。

## Tasks（層5）の運用

- tasks.md は**ファイルとして残す**。削除やアーカイブは不要
- 完了判別は `spec.json` の `phase` フィールドで行う
- 再生成時は**無条件上書き**（前回の tasks 内容は保存しない）
- 履歴が必要な場合は git log で確認する

## 生成で十分な情報

以下は永続管理せず、必要時にAIが生成する:
- レビュー用サマリー（変更の概要説明）
- 補助的な図表（構造説明に該当するもの）
- 内部説明資料
- 一時的な分析

---
_本ルールは governance/0001 ADR の Decision および Resolved Items を運用レベルに落とし込んだもの_
