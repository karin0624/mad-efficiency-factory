# Implementation Plan

- [x] 1. DOTS パッケージ導入とアセンブリ定義の構築
- [x] 1.1 DOTS パッケージを manifest.json に追加する
  - Unity Entities と Entities Graphics パッケージをプロジェクトの依存に追加する
  - `assets_refresh` → `scripts_compile` + `scripts_compile_status` でコンパイル成功を確認する
  - コンパイルエラーが発生した場合は `editor_log_tail` で診断し、バージョンを調整する
  - _Requirements: 7.1, 7.2_

- [x] 1.2 Core、ECS、テスト用のアセンブリ定義ファイルを作成する
  - Core アセンブリは Mathematics、Collections、Entities を参照する
  - ECS アセンブリは Core に加えて Burst を参照する
  - テストアセンブリは Core と ECS の両方を参照し、テストアセンブリとして構成する
  - 各ファイル作成後に `assets_refresh` → `scripts_compile` + `scripts_compile_status` でコンパイル確認する
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 2. データ型定義（列挙型と構造体）
- [x] 2.1 (P) 地形種別と資源種別の列挙型を定義する
  - 地形は Empty と Ground の 2 値を byte 基底型で定義する
  - 資源は None と IronOre の 2 値を byte 基底型で定義する
  - blittable 型として ECS および Burst と互換性を持つことを保証する
  - `assets_refresh` → `scripts_compile` + `scripts_compile_status` でコンパイル確認する
  - _Requirements: 1.3, 1.4, 1.6_

- [x] 2.2 (P) タイル 1 枚のデータ構造体を定義する
  - 地形種別、資源種別、占有エンティティ参照の 3 フィールドを持つ blittable struct とする
  - 未占有状態は Entity.Null で表現する
  - `assets_refresh` → `scripts_compile` + `scripts_compile_status` でコンパイル確認する
  - _Requirements: 1.3, 1.4, 1.5, 1.6_

- [x] 3. ECS コンポーネント定義
- [x] 3.1 (P) タイルマップシングルトンコンポーネントを定義する
  - マップサイズ（int2）とタイルデータの NativeArray を保持する IComponentData struct を定義する
  - シングルトンとして SystemAPI.GetSingleton で取得可能にする
  - `assets_refresh` → `scripts_compile` + `scripts_compile_status` でコンパイル確認する
  - _Requirements: 1.1, 1.2_

- [x] 3.2 (P) グリッド座標とフットプリントコンポーネントを定義する
  - グリッド座標を表す IComponentData（int2 値）を定義する
  - フットプリントサイズを表す IComponentData（int2 値）を定義する
  - `assets_refresh` → `scripts_compile` + `scripts_compile_status` でコンパイル確認する
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 4. 座標変換・境界チェックユーティリティの TDD 実装
- [x] 4.1 座標変換と境界チェックの EditMode テストを作成する
  - 原点座標のインデックス変換テスト（0,0 → 0）
  - 有効座標のインデックス変換テスト（正しい計算式の検証）
  - 範囲内座標、負の座標、境界超過座標、エッジ座標 (63,63) の境界チェックテスト
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Red 確認
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 4.2 座標変換と境界チェックのユーティリティ関数を実装する
  - 2D 座標からフラット配列インデックスへの変換関数を実装する
  - 座標がマップ範囲内かどうかを判定する関数を実装する
  - 全メソッドは static で状態を持たず、Burst 互換とする
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Green 確認
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 5. 占有クエリユーティリティの TDD 実装
- [x] 5.1 占有クエリの EditMode テストを作成する
  - 空きタイル・占有済みタイルの占有状態チェックテスト
  - 境界外座標での占有クエリが false を返すテスト
  - 鉄鉱石タイル・資源なしタイルの資源種別取得テスト
  - 境界外座標での資源クエリが None を返すテスト
  - 全空きエリア・一部占有エリア・境界はみ出しエリアのエリア空き判定テスト
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Red 確認
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

- [x] 5.2 占有クエリのユーティリティ関数を実装する
  - 単一タイルの占有状態を判定する関数を実装する（境界外は false）
  - 単一タイルの資源種別を取得する関数を実装する（境界外は None）
  - 矩形エリア全体の空き判定関数を実装する（境界はみ出しは false）
  - 全関数で内部的に境界チェックをガードとして使用する
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Green 確認
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

- [x] 6. 占有変異操作ユーティリティの TDD 実装
- [x] 6.1 占有設定・解除の EditMode テストを作成する
  - 有効座標での占有設定が true を返し、エンティティが更新されるテスト
  - 境界外座標での占有設定が false を返すテスト
  - 占有済みタイルの占有解除が true を返し、エンティティがクリアされるテスト
  - 境界外座標での占有解除が false を返すテスト
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Red 確認
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 6.2 占有設定・解除のユーティリティ関数を実装する
  - タイルの占有エンティティを設定する関数を実装する（境界外は false、成功時は true）
  - タイルの占有エンティティをクリアする関数を実装する（境界外は false、成功時は true）
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Green 確認
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 7. タイルマップ初期化システムの TDD 実装
- [x] 7.1 タイルマップ初期化システムの EditMode テストを作成する
  - テスト用 World を手動構築し、システムの OnCreate を実行するテスト環境を用意する
  - マップサイズが 64x64 = 4096 タイルであることを検証するテスト
  - 全タイルの地形種別が Ground であることを検証するテスト
  - 座標 (27,27) から (36,36) の鉄鉱石エリアに IronOre が設定されていることを検証するテスト
  - 鉄鉱石エリア外のタイルが None であることを検証するテスト
  - シングルトンが既に存在する場合に重複生成されないことを検証するテスト
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Red 確認
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 7.2 タイルマップ初期化システムを実装する
  - ISystem + BurstCompile で初期化システムを作成する
  - OnCreate で Persistent アロケータによる NativeArray 割り当て、全タイル Ground 初期化、鉄鉱石エリア設定、シングルトンエンティティ生成を行う
  - 初期化完了後に state.Enabled = false で自身を無効化する
  - シングルトン重複ガードを OnCreate 内に実装する
  - OnDestroy で NativeArray を Dispose する
  - テスト実行: `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で Green 確認
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1, 8.2_

- [x] 8. 全体統合検証
- [x] 8.1 全 EditMode テストを一括実行して Green を確認する
  - `tests_run_all` (test_mode: "EditMode") + `tests_run_status` で全テストが通過することを確認する
  - テスト失敗がある場合はエラー内容を診断し修正する
  - `scripts_compile` + `scripts_compile_status` でコンパイルエラーがないことを最終確認する
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2_
