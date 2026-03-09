# Testing Standards

> **Initial Defaults**: 以下は初期実装前の設計仮説。最初のspec実装完了後に実態と照合し改訂すること。

## Philosophy

- 振る舞いをテストする（実装詳細ではなく）
- 高速で信頼性の高いテストを優先
- クリティカルパスを深くカバーし、100%カバレッジは追求しない

## Test Organization

```
Assets/Tests/
  EditMode/
    {Domain}/          # ECSドメイン構造をミラー
      {TargetClass}Tests.cs
  PlayMode/
    {Feature}/
      {TargetClass}Tests.cs
```

- EditMode: ドメイン単位でディレクトリ分割（Tilemap/, Belt/, Machine/ 等）
- PlayMode: フィーチャー単位でディレクトリ分割
- テストファイル命名: `{対象クラス}Tests.cs`

## Naming Convention

メソッド名パターン: `MethodName_Condition_ExpectedResult`

```csharp
// 正常系
GetTile_ValidCoordinate_ReturnsTileData()
RotateOffset_East90Degrees_ReturnsRotatedOffset()

// 異常系
SetOccupant_OutOfBounds_ThrowsArgumentException()
GetSingleton_NoEntity_ThrowsInvalidOperation()
```

## Layer Classification Rules

テストをどの層に分類するかの判断基準:

| Layer | 種別 | 判断基準 | 例 |
|---|---|---|---|
| **Layer 1** | EditMode | Unity runtime依存なし。純粋関数・データ変換 | CameraMath, PortMath, GridCoord計算 |
| **Layer 2** | PlayMode | runtime必要だが数値検証可能。ECS System統合 | System実行順序, フレーム間データ整合性 |
| **Layer 3** | Human Review | 自動テスト不可。視覚的品質・操作感 | レイアウト, アニメーション, 操作フィール |

**迷ったらLayer 1**: ロジックをPOCOに分離してEditModeテスト可能にする設計を優先する。

## ECS Test Patterns

### EditMode — 純粋ロジック（Layer 1）

POCOクラスの直接テスト。World/EntityManager不要、標準NUnit。

```csharp
[Test]
public void RotateOffset_East_ReturnsRotated()
{
    var offset = new int2(1, 2);
    var result = PortMath.RotateOffset(offset, Direction.E);
    Assert.AreEqual(new int2(2, -1), result);
}
```

### EditMode — ECSロジック（Layer 1-2境界）

テスト用Worldを手動構築:

```csharp
private World world;
private EntityManager em;

[SetUp]
public void SetUp()
{
    world = new World("Test");
    em = world.EntityManager;
}

[TearDown]
public void TearDown()
{
    world.Dispose();
}

[Test]
public void MinerSystem_AfterTicks_ProducesItem()
{
    // シングルトン: テスト用エンティティを手動作成
    var entity = em.CreateEntity();
    em.AddComponentData(entity, new TilemapSingleton { ... });

    var system = world.GetOrCreateSystem<MinerSystem>();
    system.Update(world.Unmanaged);
    // Assert...
}
```

### PlayMode — 統合テスト（Layer 2）

```csharp
[UnityTest]
public IEnumerator BeltTransport_AfterFrame_MovesItem()
{
    // Setup scene/entities...
    yield return null; // 1フレーム進行
    Assert.AreEqual(expected, actual, 0.001f); // 許容範囲アサーション
}
```

## Test Data Patterns

| データ種別 | パターン |
|---|---|
| NativeContainer | `Allocator.Temp`で割り当て（テスト内で自動破棄） |
| グリッド座標 | 既知の固定座標: `int2(0,0)`, `int2(1,0)` |
| ティック | TickStateコンポーネントを手動インクリメント |
| ベルトチェーン | 最小構成: source → belt → destination |

## Structure (AAA)

全テストはArrange-Act-Assertパターンに従う:

```csharp
[Test]
public void Method_Condition_Expected()
{
    // Arrange: テストデータ・前提条件を構築
    // Act: テスト対象を実行
    // Assert: 結果を検証
}
```

---
_Initial defaults — revise after first spec implementation_
