# Implementation Plan

- [x] 1. Godotプロジェクトの初期セットアップ
  - 最小構成のGodot 4.3プロジェクトを作成する（config_version=5）
  - GdUnit4テストフレームワークのアドオンを有効化する
  - ディレクトリ構造（scripts/core/, tests/core/）を準備する
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 2. 共有Enum定義とセルデータスナップショット
- [x] 2.1 (P) 共有Enum定義を作成する
  - TerrainType列挙（EMPTY=0, GROUND=1）を定義する
  - ResourceType列挙（NONE=0, IRON_ORE=1）を定義する
  - Direction列挙（N=0, E=1, S=2, W=3）を定義する
  - ゼロ値がデフォルト/未設定を表す規約を適用する
  - RefCountedベースのスクリプトクラスとして実装する
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 11.4_

- [x] 2.2 (P) GridCellDataスナップショットクラスを作成する
  - 地形・資源・占有エンティティの3プロパティを持つRefCountedクラスを定義する
  - コンストラクタで値を受け取り、読み取り専用スナップショットとして機能させる
  - _Requirements: 8.1, 8.2, 11.2_

- [x] 3. CoreGridテストスイートの作成（RED）
- [x] 3.1 グリッド生成と寸法のテストを書く
  - 生成時の幅64・高さ64の検証
  - 全セルの初期地形がEMPTY（0）であることの検証
  - 全セルの初期資源がNONE（0）であることの検証
  - widthとheightプロパティの公開を検証
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 3.2 境界チェックのテストを書く
  - 範囲内座標（0,0）〜（63,63）でis_in_boundsがtrueを返すことを検証
  - 範囲外座標（負値、64以上）でis_in_boundsがfalseを返すことを検証
  - 範囲外座標へのset/get操作がクラッシュしないことを検証
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3.3 地形・資源データの読み書きテストを書く
  - set_terrainで設定した値がget_terrainで取得できることを検証
  - set_resourceで設定した値がget_resourceで取得できることを検証
  - 複数セルへの独立した読み書きを検証
  - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3_

- [x] 3.4 単一セル占有管理のテストを書く
  - 未占有セルへのoccupyが成功することを検証
  - 占有済みセルのis_occupiedがtrueを返すことを検証
  - get_occupying_entityが正しいエンティティIDを返すことを検証
  - 占有済みセルへの二重占有が拒否されることを検証
  - vacate後にセルが未占有に戻ることを検証
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 3.5 矩形占有管理のテストを書く
  - 全セル未占有時のoccupy_rectが成功することを検証
  - 1セルでも占有済みの場合にoccupy_rectが全体を拒否することを検証（原子性）
  - 拒否時にいずれのセルも変更されないことを検証
  - 範囲外にはみ出す矩形が拒否されることを検証
  - vacate_rectが矩形領域全体の占有を解除することを検証
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 3.6 隣接セルクエリのテストを書く
  - グリッド内部セルで4つの隣接座標が返されることを検証
  - 角セルで2つの隣接座標が返されることを検証
  - 辺セルで3つの隣接座標が返されることを検証
  - _Requirements: 7.1, 7.2_

- [x] 3.7 セルデータスナップショットのテストを書く
  - get_cellがGridCellDataオブジェクトを返すことを検証
  - 返却されたGridCellDataが正しい地形・資源・占有値を含むことを検証
  - GridCellDataの変更がCoreGridの内部状態に影響しないことを検証
  - _Requirements: 8.1, 8.2_

- [x] 4. CoreGridの実装（GREEN）
  - 3で作成した全テストが通過するようにCoreGridを実装する
  - 64x64固定サイズのグリッドをPackedInt32Array×2とDictionaryで構成する
  - 境界チェック、地形/資源の読み書き、占有管理、隣接クエリ、スナップショット取得を実装する
  - occupy_rectの2パス原子性（検証→コミット）を実装する
  - 全public methodの入口でis_in_boundsによる境界チェックを実施する
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 8.1, 8.2, 11.1_

- [x] 5. TilemapInitializerのテストとImplementation
- [x] 5.1 TilemapInitializerのテストを書く（RED）
  - create_gridが64x64のCoreGridを返すことを検証
  - 全セルの地形がGROUNDであることを検証
  - グリッド上に鉄鉱石（IRON_ORE）が存在することを検証
  - 同一seedで同一結果が得られることを検証（決定性）
  - 異なるseedで異なる結果が得られることを検証
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [x] 5.2 TilemapInitializerを実装する（GREEN）
  - RefCountedベースのクラスとしてcreate_gridメソッドを実装する
  - RandomNumberGeneratorをインスタンス生成してseedを設定する
  - 全セルをGROUND地形で初期化する
  - 3x3〜5x5の鉄鉱石パッチを5個、ランダム位置に配置する
  - グローバルrandi()を使用せず、RandomNumberGeneratorのみを使用する
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 11.3_
