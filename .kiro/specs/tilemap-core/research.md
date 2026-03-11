# Research & Design Decisions

## Summary
- **Feature**: `tilemap-core`
- **Discovery Scope**: New Feature (グリーンフィールド、Phase 0 基盤)
- **Key Findings**:
  - NativeArray は 64x64 固定サイズ密グリッドに最適。NativeHashMap は将来のチャンクマップ拡張用
  - TilemapHelper は純粋 static 関数として Core 層に配置し、ECS 依存を最小化。Layer 1 テストに最適化
  - ISystem + BurstCompile パターンで初期化システムを設計。シングルトン重複ガードは OnCreate 内で完結

## Research Log

### NativeArray vs NativeHashMap（タイルデータ格納）
- **Context**: 64x64 = 4096 タイルのデータ格納方式の選定
- **Sources Consulted**: Unity DOTS ドキュメント、steering/tech.md の設計判断
- **Findings**:
  - NativeArray: O(1) インデックスアクセス、連続メモリ、キャッシュフレンドリー
  - NativeHashMap: キー指定アクセス、メモリオーバーヘッドあり、スパース向き
  - 64x64 は密グリッドのため NativeArray が最適
- **Implications**: `coord.y * mapSize.x + coord.x` による直接インデックス計算。将来チャンクマップ移行時に NativeHashMap へ切り替え

### TilemapHelper の配置レイヤー
- **Context**: ユーティリティ関数を Core 層と ECS 層のどちらに配置するか
- **Sources Consulted**: steering/structure.md のレイヤーアーキテクチャ
- **Findings**:
  - Core 層（純粋 C#）に配置すれば ECS World なしで EditMode テスト可能
  - NativeArray<TileData> を引数として受け取る設計で ECS 依存を回避
  - Entity 型は Unity.Entities に属するが、struct 値型のため Core 層で参照可能
- **Implications**: MadFactory.Core アセンブリに配置。Unity.Entities への参照は必要だが、World/EntityManager 不要

### ISystem vs SystemBase（初期化システム）
- **Context**: TilemapInitializationSystem の基底型選定
- **Sources Consulted**: steering/ecs-patterns.md
- **Findings**:
  - シミュレーション層のシステムは ISystem + BurstCompile が規約
  - 初期化処理は OnCreate のみで完結し、OnUpdate は不要（Enabled=false）
  - NativeArray 生成は Burst 内で可能
- **Implications**: ISystem を採用。初期化完了後に state.Enabled = false

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| ECS Singleton + 純粋ユーティリティ | シングルトンコンポーネントにデータ格納、静的関数でクエリ | テスタビリティ最高、Burst 互換 | シングルトン取得の定型コード | steering 規約と完全一致 |
| 個別エンティティ方式 | 各タイルをエンティティとして管理 | 柔軟なクエリ | 4096 エンティティ爆発、パフォーマンス劣化 | steering で明確に否定 |

## Design Decisions

### Decision: タイルデータを NativeArray で格納
- **Context**: 64x64 固定サイズマップのデータ格納
- **Alternatives Considered**:
  1. NativeArray — 連続メモリ、O(1) アクセス
  2. NativeHashMap — スパース向き、メモリオーバーヘッド
- **Selected Approach**: NativeArray（Allocator.Persistent）
- **Rationale**: 密グリッドでは全インデックスが使用される。連続メモリによりキャッシュ効率が高く、Burst 最適化の恩恵を最大化
- **Trade-offs**: マップサイズ変更時に再割り当てが必要。固定サイズ前提
- **Follow-up**: チャンクマップ拡張時に NativeHashMap への移行パスを検討

### Decision: 境界外アクセスを例外なしで処理
- **Context**: 境界外座標に対する TilemapHelper の振る舞い
- **Alternatives Considered**:
  1. 例外スロー — 呼び出し側にバグ検出を強制
  2. デフォルト値返却 — false / None を返す安全な API
- **Selected Approach**: デフォルト値返却（Try* パターン）
- **Rationale**: Burst コンパイラ内で例外は使用不可。ゲームループ内で高頻度に呼ばれるため、例外コストは許容できない
- **Trade-offs**: 呼び出し側のバグが静かに無視される可能性
- **Follow-up**: デバッグビルドでの条件付きログ出力を将来検討

## Risks & Mitigations
- NativeArray の Dispose 漏れ → OnDestroy での確実な Dispose + テストでの検証
- シングルトン重複生成 → OnCreate 内での存在チェックガード
- 鉄鉱石座標のハードコード → 定数として明示定義し、将来の設定ファイル化の拡張点を確保

## References
- Unity Entities ドキュメント — ISystem, IComponentData, NativeArray の基本パターン
- steering/ecs-patterns.md — プロジェクト固有の ECS パターン規約
- steering/tech.md — 技術スタック決定事項（NativeArray 選定根拠）
