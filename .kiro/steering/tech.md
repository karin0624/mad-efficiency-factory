# Technology Stack

## Architecture

ハイブリッドECS構成。シミュレーション層はUnity DOTS (ECS)、プレゼンテーション層はMonoBehaviour + UI Toolkit。
データフローは単方向: 入力→コマンド→ECSシミュレーション→共有データ→描画/UI。

```
入力(MonoBehaviour) → EntityCommandBuffer → ECS Simulation → SharedData → Rendering/UI
```

**原則**: シミュレーション層はMonoBehaviourの状態を読まない。描画/UI層はECSに直接書き込まない。

## Core Technologies

- **Language**: C#
- **Engine**: Unity 6 (6000.x)
- **ECS**: Unity DOTS (Entities, Jobs, Burst, Collections)
- **UI**: UI Toolkit (UXML + USS)
- **Runtime**: Mono / IL2CPP

## Key Libraries

- **Unity Entities** (`com.unity.entities`): ECSフレームワーク
- **Unity Burst** (`com.unity.burst`): パフォーマンス最適化コンパイラ
- **Unity Collections** (`com.unity.collections`): NativeHashMap, NativeQueue等
- **Unity Test Framework** (`com.unity.test-framework`): テスト基盤
- **Nyamu MCP** (`dev.polyblank.nyamu`): AI-エディタ連携 — 詳細は `.kiro/steering/unity-mcp.md`

## Development Standards

### Type Safety
- blittable型を使用してECSコンポーネントを設計（バイナリ直列化・Jobs互換）
- 列挙型は明示的な基底型を指定（`byte`, `ushort`等）

### Testability (3層テストモデル)
- **Layer 1 (EditMode)**: 純粋ロジック → NUnit自動テスト
- **Layer 2 (PlayMode)**: 制約・統合 → 許容範囲付きアサーション
- **Layer 3 (Human Review)**: ビジュアル・操作感 → スクリーンショット + 人間レビュー

### Code Pattern: MonoBehaviour分離
- ロジックはPure C#クラス(POCO)に分離し、MonoBehaviourは薄いアダプタに留める
- POCOに対してEditModeテスト、MonoBehaviourに対してPlayModeテスト

## Development Environment

### Required Tools
- Unity 6.0.60f1 以降
- Nyamu MCP (`dev.polyblank.nyamu`)
- cc-sdd (Spec-Driven Development skills)

### AI-Editor Integration
Nyamu MCPを通じてAIエージェントがエディタ操作を実行:
- `Write`/`Edit` + `assets_refresh`/`scripts_compile` によるスクリプト管理
- `tests_run_all`/`tests_run_single` + `tests_run_status` によるTDDサイクル
- C# EditorScript + `menu_items_execute` によるシーン構築
- `editor_log_tail`/`editor_log_grep` によるエラー診断

## ECS System実行順序

`TickSimulationSystemGroup`内のSystem実行順序（順序が正しくないとデータ破損が起きる）:

```
TickAdvance → MinerExtraction → BeltTransport → MachineProcessing → Delivery
                                                                      ↓
BeltConnectionCache（構造変更時のみ実行）
```

### ブリッジ層（ECS ↔ Presentation）

| System | 方向 | 責務 |
|---|---|---|
| `PlacementInputBridge` | Input → ECS | マウス入力→EntityCommandBuffer |
| `UIDataBridgeSystem` | ECS → UI | ECSデータ→managed singletonへコピー |
| `RenderingSyncSystem` | ECS → GO | GridPosition→GameObject Transform同期 |
| `EventDrainSystem` | ECS → managed | NativeQueue→managed EventBus |

### Authoring層

ScriptableObject → Baker → ECS Componentsのパイプライン:
- `ItemDefinition` → ItemType コンポーネント
- `MachineDefinition` → 機械タイプ固有コンポーネント
- `RecipeDefinition` → Recipe バッファ

## Key Technical Decisions

| 決定 | 理由 |
|---|---|
| タイルはシングルトン`NativeHashMap`で管理（個別エンティティにしない） | 64x64=4096エンティティの爆発を回避 |
| ベルト上アイテムはスロットバッファ（個別エンティティにしない） | パフォーマンス最優先 |
| ベルトは4スロット/タイル、チェーン末尾→先頭の順で処理 | アイテム重複・消失を防止 |
| 30tps固定ティック（フレームレート分離） | 決定的シミュレーション、将来のマルチプレイ対応 |
| ポートベース機械I/O（空間的接続判定） | 明示的リンク不要、シンプルな配置ロジック |
| コマンドベース入力（EntityCommandBuffer経由） | 単方向データフロー、ロックステップ対応 |
| 回転=4方向(N/E/S/W)、`Direction`=byte enum | ポートオフセットは北基準定義、クエリ時に回転 |
| 資源は無限採取（枯渇しない） | MVP簡素化、枯渇は将来拡張ポイント |

## Simulation Domain

### Port Offsets（北基準）

| 装置 | サイズ | ポートオフセット |
|---|---|---|
| Miner (2x2) | Output (1, 2) | 上辺右 |
| Smelter (2x2) | Input (0, -1), Output (1, 2) | 下辺左、上辺右 |
| DeliveryBox (1x1) | Input (0, -1) | 下辺 |

- オフセットは北基準で定義、Direction回転で実際のオフセットが変わる
- `PortMath.RotateOffset()`でクエリ時に回転適用

### Belt Slot Model

- 4スロット/タイル（移動方向にインデックス0-3）
- Slot 0 = 入口辺、Slot 3 = 出口辺
- 1tick = 1スロット進行
- チェーン処理: 末尾→先頭順で重複防止

## Performance Constraints

### MVP Targets

- 30 FPS minimum: ベルト500本 + アイテム2000個
- シミュレーションティック: 33.3ms/tick（30tps）、実処理10ms以下目標

### Memory Budget

- TilemapSingleton: NativeHashMap容量4096（64x64）
- ベルトバッファ: 4スロット × 最大500本 = 2000スロット
- エンティティ数: 1000以下目標

### Burst Requirements

- TickSimulationSystemGroup内: `[BurstCompile]`必須
- ブリッジ層（managed参照使用）: Burst免除
- Authoring/Baker: Burst免除

---
_Document standards and patterns, not every dependency_
