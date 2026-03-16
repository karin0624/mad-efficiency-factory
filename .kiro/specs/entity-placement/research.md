# Research & Design Decisions

## Summary
- **Feature**: `entity-placement`
- **Discovery Scope**: 拡張（既存のCoreGridシステムを拡張）
- **Key Findings**:
  - CoreGridが既に`occupy_rect`/`vacate_rect`メソッドを持ち、2パス（検証→コミット）の原子性パターンを実装済み
  - `Enums.Direction`が既にN/E/S/Wの4方向enumを定義済み — 新規定義不要
  - `ItemDefinition`/`ItemCatalog`パターンが存在し、エンティティ定義にも同様のカタログパターンを適用可能

## Research Log

### 既存CoreGridの占有管理能力
- **Context**: 配置・撤去システムの基盤となるグリッド占有管理がどこまで実装済みか
- **Findings**:
  - `CoreGrid.occupy_rect(origin, size, entity_id)` — 矩形領域の一括占有（2パス: 全セル検証→全セルコミット）
  - `CoreGrid.vacate_rect(origin, size)` — 矩形領域の一括解放
  - `CoreGrid.is_occupied(pos)` / `CoreGrid.get_occupying_entity(pos)` — 単セルの占有問い合わせ
  - `_occupancy: Dictionary = {}` — `Vector2i -> int (entity_id)` の疎マップ
- **Implications**: PlacementSystemはCoreGridの既存APIを直接活用でき、占有管理ロジックの重複実装は不要。ただし、entity_idの採番とエンティティメタデータ（種別・方向）の管理は新規に必要。

### 方向enumの既存定義
- **Context**: 回転機能に必要な方向定義が存在するか
- **Findings**:
  - `Enums.Direction { N = 0, E = 1, S = 2, W = 3 }` が定義済み
  - int enumのため `(direction + 1) % 4` で時計回り回転が可能
- **Implications**: 回転ロジックはEnums.Directionをそのまま使用。新規の方向型は不要。

### エンティティ定義のパターン
- **Context**: MVPエンティティの種別とフットプリントをどう定義するか
- **Findings**:
  - `ItemDefinition`/`ItemCatalog`パターンが既存（ID + メタデータの値オブジェクト + カタログによる一元管理）
  - エンティティ定義にも同パターンを適用可能: `EntityDefinition`（種別ID, 表示名, フットプリントサイズ）+ `EntityRegistry`（カタログ）
- **Implications**: 既存パターンとの一貫性を維持するため、RefCountedベースの値オブジェクト + カタログクラスで設計する。

### 配置済みエンティティの状態管理
- **Context**: 配置後のエンティティのメタデータ（基準セル、種別、方向）をどう管理するか
- **Findings**:
  - CoreGridの`_occupancy`はentity_id（int）のみ保持 — メタデータは別管理が必要
  - `entity_id -> PlacedEntity`（基準セル、種別、方向）のマッピングが必要
  - セル→エンティティの逆引きはCoreGrid._occupancyで既に可能
- **Implications**: PlacementSystemがentity_idの採番と`PlacedEntity`の管理を担当する。CoreGridは下位レイヤーとしてセル占有のみ管理。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| CoreGrid拡張 | CoreGridに配置ロジックを直接追加 | 実装が単純 | CoreGridの責務肥大化、テスト困難化 | 却下 |
| 独立PlacementSystem | CoreGridを利用する上位システムとして配置ロジックを分離 | 責務分離、テスト容易、既存パターン準拠 | 間接層が1つ増える | 採用 |

## Design Decisions

### Decision: PlacementSystemをCoreGridの上位レイヤーとして配置
- **Context**: 配置・撤去・回転のロジックをどこに配置するか
- **Alternatives Considered**:
  1. CoreGridに直接配置ロジックを追加
  2. 独立したPlacementSystemクラスを作成
- **Selected Approach**: 独立したPlacementSystemクラス（RefCounted）
- **Rationale**: structure.mdの「ロジック ≠ プレゼンテーション」原則とsystems/パターンに準拠。CoreGridはデータレイヤー、PlacementSystemはビジネスロジックレイヤーとして責務を分離。
- **Trade-offs**: 間接層が増えるが、テスト容易性と拡張性が向上
- **Follow-up**: PlacementSystemのインスタンス管理方針（依存性注入）

### Decision: EntityDefinition/EntityRegistryパターンの採用
- **Context**: MVPエンティティの種別とフットプリントの定義方法
- **Alternatives Considered**:
  1. enumとswitch文で直接定義
  2. ItemDefinition/ItemCatalogと同パターンの値オブジェクト+カタログ
- **Selected Approach**: EntityDefinition + EntityRegistry（ItemDefinition/ItemCatalogパターンの踏襲）
- **Rationale**: 既存パターンとの一貫性、データ駆動で拡張容易
- **Trade-offs**: 小規模MVPにはやや過剰だが、将来のエンティティ追加に対応可能

### Decision: PlacedEntityによる配置済みエンティティの状態管理
- **Context**: 配置後のエンティティのメタデータ（基準セル、種別、方向）の管理方法
- **Selected Approach**: PlacedEntity値オブジェクト + PlacementSystem内のDictionary管理
- **Rationale**: CoreGridはセル占有のみ管理し、エンティティのメタデータはPlacementSystemが管理する。entity_idによる双方向参照が可能。

### Miner/Smelterフットプリント 2x2→1x1 変更の影響分析
- **Context**: ADR 0001により、Miner/Smelterのフットプリントが2x2から1x1に変更
- **Findings**:
  - `EntityRegistry.create_default()` の登録データ変更のみで対応可能（`Vector2i(2,2)` → `Vector2i(1,1)`）
  - 可変サイズフットプリントのシステム設計（EntityDefinition, PlacementSystem, CoreGrid）に変更不要
  - MVPでは全エンティティが1x1になるが、2x2以上のフットプリントサポートはシステムとして維持
  - MachinePortCatalogのポートオフセット定義にも影響あり（entity-placement specスコープ外）
- **Implications**: design.mdのcreate_default() postconditionを更新。アーキテクチャ変更なし。

## Risks & Mitigations
- entity_idの採番がオーバーフローするリスク — MVPでは64x64グリッドのため実質的に問題なし。将来的にはID再利用またはBigInt化
- CoreGridのoccupy_rectとPlacementSystemの状態が不整合になるリスク — PlacementSystem経由でのみ配置・撤去を行うことで防止
- ゴーストプレビューのパフォーマンス — フットプリント検証はO(footprint_size)で、MVPの1x1では1セルのみの検証で高速
