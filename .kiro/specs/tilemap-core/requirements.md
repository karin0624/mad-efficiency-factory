# Requirements Document

## Introduction
タイルマップ基盤（tilemap-core）は、Mad Efficiency Factoryの空間データ管理を担う最下層コンポーネントである。固定サイズ64x64の2Dグリッド上で、地形・資源・占有状態を管理し、上位システム（ベルト輸送、機械配置、レンダリング等）に対して高速な空間クエリを提供する。SceneTree非依存のRefCountedクラスとして実装し、ヘッドレス環境でのユニットテストと決定性を保証する。

## Requirements

### Requirement 1: グリッド生成と寸法
**Objective:** 開発者として、固定サイズのグリッドを生成できること。これにより、すべての上位システムが統一された空間座標系で動作できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The CoreGrid shall 64x64（幅64、高さ64）の固定寸法でグリッドを生成する
2. When CoreGridが生成された時, the CoreGrid shall すべてのセルの地形をEMPTY（値0）で初期化する
3. When CoreGridが生成された時, the CoreGrid shall すべてのセルの資源をNONE（値0）で初期化する
4. The CoreGrid shall width および height プロパティを通じてグリッド寸法を公開する

### Requirement 2: 境界チェック
**Objective:** 開発者として、任意の座標がグリッド範囲内かどうかを検証できること。これにより、範囲外アクセスによるエラーを防止できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 座標(x, y)が 0 <= x < 64 かつ 0 <= y < 64 を満たす時, the CoreGrid shall `is_in_bounds`クエリでtrueを返す
2. When 座標(x, y)が範囲外の時, the CoreGrid shall `is_in_bounds`クエリでfalseを返す
3. When 範囲外の座標に対してset/get操作が呼ばれた時, the CoreGrid shall 安全に処理する（クラッシュしない）

### Requirement 3: 地形データの読み書き
**Objective:** 開発者として、任意のセルの地形タイプを取得・設定できること。これにより、地形ベースのゲームロジック（配置可否判定等）を実装できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 有効な座標とTerrainType値が指定された時, the CoreGrid shall そのセルの地形を設定する
2. When 有効な座標が指定された時, the CoreGrid shall そのセルの現在の地形値を返す
3. When 地形が設定された後にget_terrainが呼ばれた時, the CoreGrid shall 直前に設定された値と一致する値を返す

### Requirement 4: 資源データの読み書き
**Objective:** 開発者として、任意のセルの資源タイプを取得・設定できること。これにより、資源の配置と採掘ロジックを実装できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 有効な座標とResourceType値が指定された時, the CoreGrid shall そのセルの資源を設定する
2. When 有効な座標が指定された時, the CoreGrid shall そのセルの現在の資源値を返す
3. When 資源が設定された後にget_resourceが呼ばれた時, the CoreGrid shall 直前に設定された値と一致する値を返す

### Requirement 5: 単一セル占有管理
**Objective:** 開発者として、セルの占有状態（どのエンティティが占有しているか）を追跡できること。これにより、機械やベルトの配置衝突を検出できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 未占有のセルに対してoccupyがエンティティIDとともに呼ばれた時, the CoreGrid shall そのセルを占有状態にする
2. When 占有済みセルに対してis_occupiedが呼ばれた時, the CoreGrid shall trueを返す
3. When 占有済みセルに対してget_occupying_entityが呼ばれた時, the CoreGrid shall 占有中のエンティティIDを返す
4. When 占有済みセルに対して別のエンティティがoccupyを試みた時, the CoreGrid shall 占有を拒否する（既存の占有を上書きしない）
5. When vacateが呼ばれた時, the CoreGrid shall そのセルの占有状態を解除する

### Requirement 6: 矩形占有管理（原子性保証）
**Objective:** 開発者として、複数セルにまたがる矩形領域を原子的に占有できること。これにより、2x2サイズの機械配置時に部分的な占有（不整合状態）を防止できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 矩形領域内のすべてのセルが未占有かつ範囲内の時, the CoreGrid shall すべてのセルを一括で占有する
2. When 矩形領域内に占有済みセルが1つでも含まれる時, the CoreGrid shall 占有を全セルについて拒否する（いずれのセルも変更しない）
3. When 矩形領域がグリッド範囲外にはみ出す時, the CoreGrid shall 占有を拒否する
4. When vacate_rectが呼ばれた時, the CoreGrid shall 指定矩形領域内のすべてのセルの占有を解除する

### Requirement 7: 隣接セルクエリ
**Objective:** 開発者として、指定セルの上下左右の隣接セルを取得できること。これにより、ベルト接続やポート解決等の空間的な隣接ロジックを実装できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When グリッド内部の座標に対してget_adjacentが呼ばれた時, the CoreGrid shall 上下左右の4つの隣接座標を返す
2. When グリッド端の座標に対してget_adjacentが呼ばれた時, the CoreGrid shall 範囲内の隣接座標のみを返す（範囲外座標は含まない）

### Requirement 8: セルデータスナップショット
**Objective:** 開発者として、セルの現在状態を読み取り専用スナップショットとして取得できること。これにより、呼び出し側がグリッド内部状態を直接変更することを防止できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When get_cellが有効な座標で呼ばれた時, the CoreGrid shall 地形・資源・占有エンティティを含むGridCellDataオブジェクトを返す
2. The GridCellData shall 読み取り専用のスナップショットであり、返却後のGridCellDataへの変更がCoreGridの内部状態に影響しない

### Requirement 9: 共有Enum定義
**Objective:** 開発者として、地形タイプ・資源タイプ・方向を統一されたenumで参照できること。これにより、複数の機能間でデータ型の一貫性を保てる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The Enums shall TerrainType列挙（EMPTY=0, GROUND=1）を定義する
2. The Enums shall ResourceType列挙（NONE=0, IRON_ORE=1）を定義する
3. The Enums shall Direction列挙（N=0, E=1, S=2, W=3）を定義する
4. The Enums shall ゼロ値がデフォルト/未設定状態を表す規約に従う（EMPTY=0, NONE=0）

### Requirement 10: グリッド初期化と鉄鉱石配置
**Objective:** 開発者として、シード値に基づいて地形と鉄鉱石を初期配置したグリッドを生成できること。これにより、決定的なマップ生成とテスト再現性を実現できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When TilemapInitializerのcreate_gridがseed値とともに呼ばれた時, the TilemapInitializer shall 64x64のCoreGridを生成する
2. When グリッドが初期化された時, the TilemapInitializer shall すべてのセルの地形をGROUNDに設定する
3. When グリッドが初期化された時, the TilemapInitializer shall 鉄鉱石パッチを5個配置する
4. The TilemapInitializer shall 各鉄鉱石パッチを3x3から5x5の矩形領域として配置する
5. When 同一のseed値でcreate_gridが複数回呼ばれた時, the TilemapInitializer shall 毎回同一のグリッド状態を生成する（決定性）
6. When 異なるseed値でcreate_gridが呼ばれた時, the TilemapInitializer shall 異なるグリッド状態を生成する
7. The TilemapInitializer shall 乱数生成にRandomNumberGeneratorを使用し、グローバルなrandi()を使用しない

### Requirement 11: SceneTree非依存
**Objective:** 開発者として、タイルマップ基盤のすべてのクラスがSceneTree/Node APIに依存しないこと。これにより、ヘッドレス環境でのユニットテストと、シミュレーションの決定性を保証できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The CoreGrid shall RefCountedを基底クラスとし、Nodeを継承しない
2. The GridCellData shall RefCountedを基底クラスとし、Nodeを継承しない
3. The TilemapInitializer shall RefCountedを基底クラスとし、Nodeを継承しない
4. The Enums shall スクリプトクラスとして定義され、Nodeを継承しない
