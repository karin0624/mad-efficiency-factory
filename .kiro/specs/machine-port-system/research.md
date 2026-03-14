# Research & Design Decisions

## Summary
- **Feature**: `machine-port-system`
- **Discovery Scope**: Extension（既存システムの拡張）
- **Key Findings**:
  - BeltTransportSystemが既に `receive_item_from_machine()` / `deliver_item_to_machine()` インターフェースを提供しており、ベルト側の契約は確定済み
  - EntityDefinition/EntityRegistry パターンが確立されており、ポート定義もこれに準拠すべき
  - BeltGrid の dirty-flag 遅延再構築パターンがポート接続管理に適用可能

## Research Log

### 既存ベルト-機械インターフェース分析
- **Context**: MachinePortSystemがBeltTransportSystemと連携するための既存契約を調査
- **Sources Consulted**: `godot/scripts/systems/belt_transport_system.gd`, `godot/scripts/core/belt_grid.gd`
- **Findings**:
  - `BeltTransportSystem.receive_item_from_machine(pos: Vector2i, item_id: int) -> bool`: ベルトタイルが空なら item を配置し true を返す。満杯なら false
  - `BeltTransportSystem.deliver_item_to_machine(pos: Vector2i) -> int`: ベルトタイル末端（progress >= 1.0）にアイテムがあれば item_id を返しクリア。なければ 0
  - これらは BeltTransportSystem (Node) 上のメソッドだが、内部で BeltGrid (RefCounted) を操作している
- **Implications**: MachinePortTransferSystem は BeltGrid を直接操作するか、BeltTransportSystem 経由で転送するかの設計判断が必要。テスト容易性のため BeltGrid 直接操作を推奨

### エンティティ定義パターン分析
- **Context**: 機械タイプごとのポート構成をどのパターンで定義するか調査
- **Sources Consulted**: `entity_definition.gd`, `entity_registry.gd`, `item_definition.gd`, `item_catalog.gd`
- **Findings**:
  - EntityDefinition: `entity_type_id`, `display_name`, `footprint_size`, `placeable_on` を持つ Resource
  - EntityRegistry: `register()` / `get_by_id()` のカタログパターン
  - ItemDefinition/ItemCatalog: 同様のパターン
  - `create_default()` 静的メソッドでMVPデータを登録
- **Implications**: ポート構成は EntityDefinition を拡張するか、別の MachinePortConfig + MachinePortCatalog として定義。関心の分離のため後者を推奨

### ポート回転の数学
- **Context**: 2x2機械の相対オフセットをどう回転するか調査
- **Sources Consulted**: Godot座標系（Y軸下向き）、既存 `enums.gd`（Direction: N=0, E=1, S=2, W=3）
- **Findings**:
  - グリッド座標での90°時計回り回転公式（size_x × size_y グリッド）:
    - N (0°): `(x, y) → (x, y)`
    - E (90° CW): `(x, y) → (size_y - 1 - y, x)`
    - S (180°): `(x, y) → (size_x - 1 - x, size_y - 1 - y)`
    - W (270° CW): `(x, y) → (y, size_x - 1 - x)`
  - 方向の回転: `(port_dir + machine_dir) % 4`
  - Godot座標系ではY軸が下向きのため、北=Y減少方向
- **Implications**: PortMath は純粋関数として実装し、offset回転とdirection回転を分離する。正方形(2x2)は `size_x == size_y` なので公式が簡略化される

### ティック処理順序の決定
- **Context**: MachinePortTransferSystem と BeltTransportSystem のティック内実行順序を決定
- **Sources Consulted**: 既存 BeltTransportSystem の処理順序（downstream → upstream）、Factorio のベルト-機械連携
- **Findings**:
  - BeltTransportSystem は downstream→upstream 順に処理（消費者優先）
  - 3つの候補:
    1. `Output push → Belt transport → Input pull`: 1ティックで出力→輸送→入力が完結、最速スループット
    2. `Belt transport → Port transfer`: シンプルだが1ティック遅延
    3. `Input pull → Belt transport → Output push`: 消費者優先だが出力が1ティック遅延
  - 候補1が最もスループットが高く、プレイヤー体験として自然
- **Implications**: ティック内の実行順序: Output ports → Belt transport → Input ports。TickEngineNode のシグナル接続順序で制御

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| EntityDefinition拡張 | 既存EntityDefinitionにポート配列を追加 | 変更箇所が少ない | EntityDefinition の責務が肥大化、非機械エンティティにも不要なフィールド | ❌ 不採用 |
| 独立Config + Catalog | MachinePortConfig / MachinePortCatalog を新設 | 関心分離、非機械エンティティに影響なし | ファイル数増加 | ✅ 採用 |
| Dictionary直書き | ポート定義をコード内にハードコード | 最小構成 | 拡張性なし、テスト困難 | ❌ 不採用 |

## Design Decisions

### Decision: ポート定義を独立したConfig/Catalogパターンで管理
- **Context**: 機械タイプごとのポート構成（入力/出力の数・位置・方向）をどこに定義するか
- **Alternatives Considered**:
  1. EntityDefinition を拡張してポート配列を追加
  2. 独立した MachinePortConfig + MachinePortCatalog を新設
- **Selected Approach**: 独立した Config/Catalog パターン
- **Rationale**: EntityDefinition はエンティティ配置の関心事に特化すべき。ベルトなど非機械エンティティにポートフィールドは不要。既存の ItemDefinition/ItemCatalog パターンと一貫性がある
- **Trade-offs**: ファイル数は増えるが、各クラスの責務が明確になりテスト容易性が向上
- **Follow-up**: MachinePortCatalog.create_default() で MVP 3機械のポート構成を登録

### Decision: BeltGrid を直接操作してアイテム転送
- **Context**: MachinePortTransferSystem がベルトとアイテムをやり取りする方法
- **Alternatives Considered**:
  1. BeltTransportSystem (Node) の既存メソッドを呼び出す
  2. BeltGrid (RefCounted) を直接操作する
- **Selected Approach**: BeltGrid を直接操作
- **Rationale**: コアロジックを RefCounted 層に閉じることで、SceneTree 非依存のユニットテストが可能。既存の receive/deliver メソッドと同等のロジックを BeltGrid レベルで実行
- **Trade-offs**: BeltGrid の内部構造への依存が増えるが、同一レイヤーでの結合なので許容範囲
- **Follow-up**: BeltGrid に必要に応じてポート転送用のパブリックメソッドを追加

### Decision: ティック処理順序を Output → Belt → Input に固定
- **Context**: 1ティック内での処理順序がスループットと遅延に影響
- **Selected Approach**: Output ports → Belt transport → Input ports
- **Rationale**: 出力を先に処理することで、同一ティック内でベルトが輸送し入力ポートが受取可能。最小遅延で最大スループット
- **Trade-offs**: TickEngineNode でのシグナル接続順序に依存するが、明示的な優先度管理で解決可能

## Risks & Mitigations
- **ティック順序の暗黙的依存**: TickEngineNode のシグナル接続順序が処理順序を決定 → 明示的な優先度パラメータまたは単一のオーケストレーターで制御
- **2x2機械の回転によるポート位置ずれ**: 回転公式の誤りがポート接続を破壊 → PortMath の全4方向テストで網羅的に検証
- **BeltGrid の内部変更による破損**: BeltGrid のAPI変更がMachinePortTransferSystemに影響 → 契約ベースのインターフェースで分離

## References
- Godot 4.3 TileMap documentation — グリッド座標系とY軸方向
- 既存spec: conveyor-belt/design.md — BeltGrid/BeltTileData のデータモデルと処理順序
- 既存spec: entity-placement/design.md — EntityDefinition/PlacedEntity のパターン
