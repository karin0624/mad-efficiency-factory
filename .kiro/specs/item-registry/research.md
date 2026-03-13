# Research & Design Decisions

---
**Purpose**: Item Registry機能の設計判断の根拠と調査結果を記録する。
---

## Summary
- **Feature**: `item-registry`
- **Discovery Scope**: New Feature（グリーンフィールド — 既存のアイテム管理コードなし）
- **Key Findings**:
  - プロジェクトはGodot 4.3 + GDScriptで構成され、コアロジックは`RefCounted`ベースの純粋クラスとして実装される既存パターンがある
  - 外部依存なし（Phase 0基盤機能）、シーン非依存で設計可能
  - 既存の`Enums.ResourceType`（地形資源）とは概念的に分離したアイテム種別IDが必要

## Research Log

### 既存コードベースのアーキテクチャパターン
- **Context**: 新規コンポーネントが既存パターンに整合するか確認
- **Sources Consulted**: `scripts/core/`配下の既存ファイル（enums.gd, grid_cell_data.gd, tick_clock.gd）
- **Findings**:
  - コアロジックは`RefCounted`を継承し、`class_name`でグローバル登録
  - シーンツリーに依存しない純粋ロジッククラスとして実装
  - テストはgdUnit4の`GdUnitTestSuite`を使用
  - ファイル配置: `godot/scripts/core/` にロジック、`godot/tests/core/` にテスト
  - 定数は`const`でクラス内に定義するパターン
- **Implications**: ItemDefinition、ItemQuantity、ItemCatalogはすべて`RefCounted`ベースで実装すべき

### アイテムIDと既存ResourceTypeの関係
- **Context**: `Enums.ResourceType`が既に存在し、IRON_ORE=1が定義されている
- **Sources Consulted**: enums.gd
- **Findings**:
  - `Enums.ResourceType`は地形上の資源種別（地面に存在する鉄鉱石など）を表す
  - planの制約: 「地形上の資源種別と流通アイテム種別は概念的に関連するが、別の識別子として管理する」
  - アイテムIDは独立した整数IDとして管理し、ResourceTypeとは別の名前空間を持つ
- **Implications**: ItemDefinitionのIDはEnums.ResourceTypeとは独立したint値として設計する

### GDScriptにおけるnull安全パターン
- **Context**: 存在しないIDでの検索時にnullに相当する結果を返す設計
- **Sources Consulted**: Godot 4.3 GDScript仕様
- **Findings**:
  - GDScriptでは`null`が使用可能で、`RefCounted`型の変数にnullを代入できる
  - 辞書（Dictionary）の`get(key, default)`メソッドでデフォルト値としてnullを返せる
- **Implications**: `get_by_id()`はnullを返すシンプルなパターンで十分

### 数量値の上限設計
- **Context**: planで「上限値は設計フェーズで決定する」と指定されている
- **Sources Consulted**: ファクトリーゲームの一般的な数量設計
- **Findings**:
  - Godotのintは64bit整数（-2^63 ~ 2^63-1）
  - ファクトリーゲームでは999や9999が一般的な上限
  - 上限値はItemQuantityの生成時パラメータとして設定可能にすべき
- **Implications**: デフォルト上限999とし、生成時に任意の上限値を指定可能にする

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 単純RefCountedクラス群 | ItemDefinition、ItemQuantity、ItemCatalogをそれぞれ独立したRefCountedクラスとして実装 | 既存パターンと整合、シンプル、テスト容易 | 大規模拡張時にリファクタが必要になる可能性 | MVPに最適、既存コードと同じアプローチ |

## Design Decisions

### Decision: データクラスの基底クラス選択
- **Context**: シーン非依存のデータ構造に適した基底クラスの選択
- **Alternatives Considered**:
  1. `RefCounted` — 参照カウント方式のメモリ管理、シーンツリー不要
  2. `Resource` — Godotリソースシステムとの統合、ディスク保存対応
  3. `Node` — シーンツリーに組み込み可能
- **Selected Approach**: `RefCounted`
- **Rationale**: 既存のcore/クラス（TickClock、GridCellData）と同じパターン。シーン非依存の要件を自然に満たし、テストが容易。ディスク保存は現時点のスコープ外。
- **Trade-offs**: Resourceと異なりエディタ上での編集ができないが、MVPでは不要
- **Follow-up**: 将来的にリソースとしての保存が必要になった場合、Resourceへの移行を検討

### Decision: 数量値の上限デフォルト値
- **Context**: 数量の有効範囲上限を決定する必要がある
- **Alternatives Considered**:
  1. 固定値999 — シンプルだが柔軟性に欠ける
  2. コンストラクタパラメータで可変、デフォルト999 — 柔軟かつ合理的なデフォルト
  3. INT_MAX — 実質制限なし
- **Selected Approach**: コンストラクタパラメータで可変、デフォルト999
- **Rationale**: ベルトのスロット容量やインベントリサイズなど、用途によって異なる上限が必要になる可能性がある。デフォルト999は一般的なファクトリーゲームの慣例に合う。
- **Trade-offs**: コンストラクタの引数が増えるが、柔軟性を確保
- **Follow-up**: 実際のゲームプレイバランスでデフォルト値の調整が必要になる可能性

## Risks & Mitigations
- アイテムIDとResourceTypeの混同 — ドキュメントとクラス命名で明確に区別する
- MVP後のアイテム種別増加時のパフォーマンス — Dictionary検索はO(1)であり、数百種程度では問題にならない

## References
- Godot 4.3 GDScript Reference — RefCounted、Dictionary仕様
- gdUnit4 Testing Framework — テストパターン
