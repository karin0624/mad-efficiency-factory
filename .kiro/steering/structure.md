# Project Structure

## Organization Philosophy

**レイヤー分離 + ドメイン分割**。3つのアーキテクチャレイヤー（ECS Simulation / Presentation / Authoring）を維持しつつ、ECS内部はドメイン（Tilemap, Tick, Conveyor, Machine等）ごとにSystem/Componentを配置する。

## Layer Architecture

```
┌─ PRESENTATION ─┐   ┌─ BRIDGE ─┐   ┌─ ECS SIMULATION ─┐   ┌─ AUTHORING ─┐
│ UI Toolkit      │   │ Sync     │   │ TickSimulation    │   │ SO → Bake   │
│ MonoBehaviour   │◄──│ Systems  │◄──│ SystemGroup       │◄──│ → ECS       │
│ (Camera, Input) │   │          │   │ (DOTS)            │   │ Components  │
└─────────────────┘   └──────────┘   └───────────────────┘   └─────────────┘
```

## Directory Patterns

### Unity Project Source (`Assets/Scripts/`)

**Core (Pure C#)**
**Location**: `Assets/Scripts/Core/`
**Purpose**: Unity非依存の純粋ロジック（POCO）。Layer 1テストの対象。
**Example**: `CameraMath.cs`, `PortMath.cs`, `ResourceQuantity.cs`

**ECS Components & Systems**
**Location**: `Assets/Scripts/ECS/{Components,Systems,SystemGroups,Authoring}/`
**Purpose**: DOTS ECSのデータ定義とシミュレーションロジック
**Example**: `Components/TilemapSingleton.cs`, `Systems/BeltTransportSystem.cs`
**ドメイン分割**: ドメインごとにファイルを配置。Tilemap系(`TilemapSingleton`, `TilemapInitializationSystem`)、Tick系(`TickState`, `TickAdvanceSystem`)、Conveyor系(`BeltSegment`, `BeltTransportSystem`)、Machine系(`MiningState`, `MinerExtractionSystem`)等。同一ドメインのComponentとSystemは同じドメイン名で対応付ける

**MonoBehaviours**
**Location**: `Assets/Scripts/MonoBehaviours/`
**Purpose**: カメラ制御、入力処理、ECS→描画ブリッジ
**Example**: `CameraController.cs`, `PlacementController.cs`

**UI**
**Location**: `Assets/Scripts/UI/{Controllers,UXML,USS}/`
**Purpose**: UI Toolkitのコントローラー、レイアウト、スタイル
**Example**: `Controllers/MachinePaletteController.cs`

**Data**
**Location**: `Assets/Scripts/Data/ScriptableObjects/`
**Purpose**: アイテム/機械/レシピのScriptableObject定義
**Types**: `ItemDefinition`(アイテム種別), `MachineDefinition`(機械パラメータ), `RecipeDefinition`(加工レシピ)

### Tests
**Location**: `Assets/Tests/{EditMode,PlayMode}/`
**Purpose**: EditMode = Layer1 (POCO + ECS純粋ロジック)、PlayMode = Layer2 (統合・制約)

### Specifications
**Location**: `.kiro/specs/<feature>/`
**Purpose**: フィーチャーごとの仕様（requirements.md, design.md, tasks.md）
**Example**: `.kiro/specs/tilemap-core/`, `.kiro/specs/conveyor-belt/`

## Naming Conventions

- **C# Files**: PascalCase (`BeltTransportSystem.cs`)
- **ECS Components**: 名詞 (`GridPosition`, `BeltSegment`, `MiningState`)
- **ECS Systems**: 動詞+名詞+System (`MinerExtractionSystem`, `BeltTransportSystem`)
- **POCO静的関数**: 動詞 (`CameraMath.ClampPosition()`, `PortMath.RotateOffset()`)
- **MonoBehaviour**: 役割+Controller/Manager (`CameraController`, `PlacementController`)
- **UXML/USS**: PascalCase (`MachinePalette.uxml`, `GameStyles.uss`)
- **ScriptableObject**: 定義名+Definition (`ItemDefinition`, `MachineDefinition`)

## Feature Decomposition

各フィーチャーは`.kiro/specs/<feature>/`に対応。実装順はPhase依存関係に従う:
- Phase 0 (基盤・並列可): `tilemap-core`, `tick-engine`, `item-registry`
- Phase 1 (配置・並列可): `entity-placement`→tilemap-core, `camera-navigation`→tilemap-core
- Phase 2 (輸送): `conveyor-belt`→tilemap-core, tick-engine, item-registry, entity-placement
- Phase 3 (I/O): `machine-port-system`→tilemap-core, conveyor-belt
- Phase 4 (機械・並列可): `machine-miner`→entity-placement, machine-port-system / `machine-smelter`→conveyor-belt, machine-port-system / `machine-delivery`→conveyor-belt, machine-port-system
- Phase 5 (UI/描画・並列可): `ui-machine-palette`→entity-placement / `ui-delivery-hud`→machine-delivery / `rendering-bridge`→全ECSフィーチャー

**クリティカルパス**: tilemap-core → entity-placement → conveyor-belt → machine-port-system → machine-smelter → 統合テスト

## Code Organization Principles

1. **単方向データフロー**: Presentation → Command → ECS → SharedData → Rendering
2. **ロジック分離**: 全ゲームロジックはCore/(POCO)またはECS/Systems/に配置。MonoBehaviourにロジックを書かない
3. **テスタビリティ優先**: 新しいロジックはまずPOCO/純粋関数として設計し、必要な場合のみECS Systemに組み込む
4. **ドメイン独立**: 各フィーチャーのSystemは他フィーチャーのComponentに直接依存しない（共通インターフェースまたはシングルトン経由）

---
_Document patterns, not file trees. New files following patterns shouldn't require updates_
