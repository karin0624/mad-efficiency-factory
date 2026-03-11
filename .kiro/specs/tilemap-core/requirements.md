# Requirements Document

## Introduction

tilemap-core は Mad Efficiency Factory の最初の基盤フィーチャーである。64x64 の 2D グリッドワールドをデータとして表現し、タイル管理・空間クエリ・占有追跡・鉄鉱石の初期配置を提供する。全ての上位フィーチャー（配置、ベルト、機械等）がこの基盤に依存する Phase 0 コンポーネントである。

## Requirements

### Requirement 1: タイルマップデータ構造
**Objective:** 開発者として、64x64 の 2D グリッドワールドをメモリ効率の良い単一データ構造で管理したい。これにより全ての上位フィーチャーが統一的にタイル情報にアクセスできる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The TilemapSingleton shall マップサイズとして int2(64, 64) を保持する
2. The TilemapSingleton shall 4096 個の TileData を格納する連続メモリ領域を保持する
3. The TileData shall 地形種別（Empty, Ground）を表す列挙値を保持する
4. The TileData shall 資源種別（None, IronOre）を表す列挙値を保持する
5. The TileData shall 占有エンティティへの参照を保持する（未占有時は null 相当）
6. The TileData shall blittable 型として設計され、ECS コンポーネントおよび Burst コンパイラと互換性を持つ

### Requirement 2: グリッド座標コンポーネント
**Objective:** 開発者として、エンティティにグリッド上の位置とフットプリントサイズを付与したい。これにより配置・衝突判定・空間クエリが統一的に行える。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The GridPosition shall int2 型でエンティティのグリッド座標を表現する
2. The GridSize shall int2 型でエンティティのフットプリント（占有タイル範囲）を表現する
3. The GridPosition shall ECS IComponentData として全配置エンティティに付与可能である
4. The GridSize shall ECS IComponentData として複数タイルを占有するエンティティに付与可能である

### Requirement 3: 座標変換と境界チェック
**Objective:** 開発者として、2D 座標とフラット配列インデックスの相互変換および境界チェックをユーティリティ関数として利用したい。これにより座標計算の重複実装とバグを防ぐ。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 有効な int2 座標が渡された場合, the TilemapHelper shall `coord.y * mapSize.x + coord.x` に基づく正しいフラット配列インデックスを返す
2. When 原点座標 (0,0) が渡された場合, the TilemapHelper shall インデックス 0 を返す
3. When 座標がマップ範囲内にある場合, the TilemapHelper shall true を返す（境界チェック）
4. When 座標の x または y が負の値の場合, the TilemapHelper shall false を返す（境界チェック）
5. When 座標の x または y がマップサイズ以上の場合, the TilemapHelper shall false を返す（境界チェック）
6. When マップ端座標 (63,63) が渡された場合, the TilemapHelper shall true を返す（境界チェック）

### Requirement 4: 占有クエリ
**Objective:** 開発者として、特定のタイルが占有されているか、どの資源があるか、エリアが空いているかを安全にクエリしたい。これにより配置判定・資源検索ロジックを実装できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 空きタイルの座標が渡された場合, the TilemapHelper shall 占有状態として false を返す
2. When 占有済みタイルの座標が渡された場合, the TilemapHelper shall 占有状態として true を返す
3. If 境界外の座標で占有クエリが実行された場合, the TilemapHelper shall 例外をスローせず false を返す
4. When 鉄鉱石タイルの座標が渡された場合, the TilemapHelper shall 資源種別として IronOre を返す
5. When 資源のないタイルの座標が渡された場合, the TilemapHelper shall 資源種別として None を返す
6. If 境界外の座標で資源クエリが実行された場合, the TilemapHelper shall 例外をスローせず None を返す
7. When 全タイルが空きのエリアが渡された場合, the TilemapHelper shall エリア空き判定として true を返す
8. When 1 タイルでも占有されたエリアが渡された場合, the TilemapHelper shall エリア空き判定として false を返す
9. If エリアが部分的にマップ境界外にはみ出す場合, the TilemapHelper shall エリア空き判定として false を返す

### Requirement 5: 占有変異操作
**Objective:** 開発者として、タイルの占有エンティティを安全に設定・解除したい。これによりエンティティ配置・撤去時にタイルマップの整合性を維持できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 有効な座標とエンティティが渡された場合, the TilemapHelper shall 占有設定に成功し true を返す
2. When 占有設定が成功した場合, the TilemapHelper shall 対象タイルの OccupyingEntity を渡されたエンティティに更新する
3. If 境界外の座標で占有設定が実行された場合, the TilemapHelper shall 例外をスローせず false を返す
4. When 占有済みタイルの座標が渡された場合, the TilemapHelper shall 占有解除に成功し true を返す
5. When 占有解除が成功した場合, the TilemapHelper shall 対象タイルの OccupyingEntity を null 相当にクリアする
6. If 境界外の座標で占有解除が実行された場合, the TilemapHelper shall 例外をスローせず false を返す

### Requirement 6: タイルマップ初期化
**Objective:** 開発者として、ゲーム開始時に 64x64 のタイルマップが自動的に初期化され、鉄鉱石が所定のエリアに配置されていてほしい。これにより上位フィーチャーが即座にタイルマップを利用できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The TilemapInitializationSystem shall 起動時に 64x64 = 4096 タイルのマップを生成する
2. The TilemapInitializationSystem shall 全タイルの地形種別を Ground で初期化する
3. The TilemapInitializationSystem shall 座標 (27,27) から (36,36) の 100 タイルに資源種別 IronOre を設定する
4. The TilemapInitializationSystem shall 鉄鉱石エリア外のタイルの資源種別を None に設定する
5. The TilemapInitializationSystem shall 初期化完了後に自身を無効化し、以降の更新処理を行わない
6. If TilemapSingleton が既に存在する場合, the TilemapInitializationSystem shall 重複生成を行わずスキップする

### Requirement 7: Assembly 定義
**Objective:** 開発者として、ECS コード・Core コード・テストコードが適切に分離されたアセンブリ定義を持ちたい。これによりコンパイル時間の最適化と依存関係の明確化が実現できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The MadFactory.Core assembly shall Unity.Mathematics, Unity.Collections, Unity.Entities への参照を持つ
2. The MadFactory.ECS assembly shall MadFactory.Core, Unity.Entities, Unity.Mathematics, Unity.Collections, Unity.Burst への参照を持つ
3. The MadFactory.Tests.EditMode assembly shall MadFactory.Core, MadFactory.ECS, Unity.Entities, Unity.Mathematics, Unity.Collections への参照を持つ
4. The MadFactory.Tests.EditMode assembly shall テストアセンブリとして構成される

### Requirement 8: メモリ管理
**Objective:** 開発者として、タイルマップの NativeContainer が適切に管理され、メモリリークが発生しないことを保証したい。これにより長時間プレイ時の安定性が確保できる。
**Testability:** Layer 2 (Range-Testable)

#### Acceptance Criteria
1. The TilemapInitializationSystem shall Persistent アロケータで NativeArray を割り当てる
2. When TilemapInitializationSystem が破棄される場合, the system shall NativeArray を Dispose する

#### Non-Testable Aspects
- 長時間実行時のメモリリーク検出は自動テストでは困難
- Review method: Unity Profiler の Memory モジュールでアロケーション追跡
- Acceptance threshold: セッション中に TilemapSingleton 関連のメモリ増加がないこと
