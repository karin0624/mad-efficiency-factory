# ECS Patterns

> **Initial Defaults**: 以下は初期実装前の設計仮説。最初のspec実装完了後に実態と照合し改訂すること。

## System Design

ISystem と SystemBase の使い分け:

| 基準 | ISystem | SystemBase |
|---|---|---|
| Burst対応 | 必須 | 不可 |
| managed参照 | 不可 | 可 |
| 用途 | シミュレーション層 | ブリッジ層 |

- シミュレーション層（TickSimulationSystemGroup内）→ ISystem + `[BurstCompile]`
- ブリッジ層（ECS↔Presentation）→ SystemBase（managed参照が必要なため）
- `[UpdateInGroup(typeof(TickSimulationSystemGroup))]` でグループ所属を明示
- PresentationSystemGroup: 描画同期系のSystem向け

ライフサイクル: `OnCreate`（初期化・キャッシュ取得） → `OnUpdate`（毎フレーム処理） → `OnDestroy`（リソース破棄）

## Component Design

型の選択基準:

| 型 | 用途 | 例 |
|---|---|---|
| `IComponentData` | エンティティ固有の値データ | GridPosition, MachineType |
| `IBufferElementData` | 可変長データ配列 | BeltSlot, RecipeInput |
| `ISharedComponentData` | 同値でチャンクをグループ化 | RenderMesh等 |
| `ICleanupComponentData` | エンティティ破棄時のクリーンアップ | （必要時に導入） |

**Blittable型制約**: ECSコンポーネントは全フィールドがblittable必須。

- 許可: `int`, `float`, `bool`, `byte`, `int2`, `float3`, `FixedString`, `Entity`, enum（明示的基底型）
- 禁止: `string`, `class`参照, `List<T>`, managed型全般

**Tag Component**: 空structでアーキタイプフィルタリング。データなしでエンティティを分類する。

```csharp
public struct IsActiveTag : IComponentData { }
```

## Singleton Pattern

プロジェクト標準: TilemapSingletonを参照パターンとする。

```
// 作成（InitializationSystem.OnCreate）
Entity e = EntityManager.CreateEntity();
EntityManager.AddComponentData(e, new TilemapSingleton { ... });

// 取得（読み取り専用）
var tilemap = SystemAPI.GetSingleton<TilemapSingleton>();

// 取得（書き込み）
var tilemap = SystemAPI.GetSingletonRW<TilemapSingleton>();

// 破棄（OnDestroy）
var tilemap = SystemAPI.GetSingleton<TilemapSingleton>();
tilemap.Data.Dispose(); // NativeContainerは手動Dispose必須
```

## EntityCommandBuffer

構造変更と値変更の判断:

| 操作 | 手段 |
|---|---|
| Create/Destroy Entity | ECB必須 |
| Add/Remove Component | ECB必須 |
| SetComponent（値変更） | `RefRW<T>`で直接書き込み可 |

- プロジェクトデフォルト: `BeginSimulationEntityCommandBufferSystem`
- 入力コマンドパターン: MonoBehaviour → PlacementInputBridge → ECB → deferred playback

## NativeContainer Lifecycle

Allocator選択基準:

| Allocator | 寿命 | 用途 |
|---|---|---|
| `Persistent` | 明示的Dispose | シングルトンデータ、長寿命コレクション |
| `TempJob` | ジョブ完了まで | ジョブ内一時アロケーション |
| `Temp` | 単一フレーム | 即時使用の一時計算 |

**Dispose規約**: `Allocator.Persistent`で確保したコンテナは、所有Systemの`OnDestroy`で必ずDisposeする。

## Query Patterns

用途別の選択:

```
// デフォルト: 可読性優先
foreach (var (pos, speed) in SystemAPI.Query<RefRO<GridPosition>, RefRO<MoveSpeed>>())
{
    // ...
}

// パフォーマンスクリティカル: IJobEntity
[BurstCompile]
partial struct TransportJob : IJobEntity
{
    public void Execute(ref BeltSlot slot, in MoveSpeed speed) { ... }
}
```

- `RefRW<T>`: 書き込みあり、`RefRO<T>`: 読み取り専用 — 必ず使い分ける
- `SystemAPI.Query` foreach がデフォルト。IJobEntityはプロファイリングで必要性が確認された場合のみ

## Burst Compilation Rules

- `[BurstCompile]`: TickSimulationSystemGroup内の全Systemに必須
- ブリッジ層・Authoring/Baker: Burst免除

Burst内で許可/禁止:

| 許可 | 禁止 |
|---|---|
| NativeContainer | managed型 |
| Unity.Mathematics | virtual呼び出し |
| FixedString | try/catch |
| fixed-size buffer | string操作 |
| blittable struct | Debug.Log |

## Direction & Rotation

4方向モデル:

```csharp
public enum Direction : byte { N = 0, E = 1, S = 2, W = 3 }
```

- ポートオフセットは**北基準**で定義し、クエリ時に`PortMath.RotateOffset()`で回転
- 回転計算: `(direction + rotationSteps) % 4`

---
_Initial defaults — revise after first spec implementation_
