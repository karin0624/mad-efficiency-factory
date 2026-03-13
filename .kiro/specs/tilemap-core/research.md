# Research & Design Decisions

## Summary
- **Feature**: `tilemap-core`
- **Discovery Scope**: New Feature（グリーンフィールド）
- **Key Findings**:
  - GDScriptの`PackedInt32Array`はゼロ初期化されるため、`EMPTY=0`/`NONE=0`の規約と自然に整合する
  - 占有データは疎（全セルの一部のみ使用）であるため、`Dictionary<Vector2i, int>`が最適
  - `RandomNumberGenerator`はインスタンス単位のシード管理を提供し、グローバル状態を汚染しない

## Research Log

### PackedInt32Arrayのゼロ初期化動作
- **Context**: CoreGridの密データストレージとして`PackedInt32Array`を採用する際、初期値の保証が必要
- **Sources Consulted**: Godot 4.3公式ドキュメント — PackedInt32Array.resize()
- **Findings**: `resize()`で拡張された要素はゼロ初期化される。明示的な`fill(0)`は不要
- **Implications**: enum定義でEMPTY=0、NONE=0とすることで、配列生成後の追加初期化コストを排除

### 密データ vs 疎データの選択基準
- **Context**: 地形・資源・占有の3種類のセルデータを効率的に格納する方法の選定
- **Sources Consulted**: tech.md（タイルマップ実装方針）、planファイル
- **Findings**:
  - 地形・資源: 全64x64セルに値が存在 → 密データ（PackedInt32Array）が最適
  - 占有: 配置済みエンティティのみ → 疎データ（Dictionary）が最適。メモリ効率とルックアップ性能のバランス
- **Implications**: 2つのPackedInt32Array（terrain, resource）+ 1つのDictionary（occupancy）の3層構造

### occupy_rectの原子性保証パターン
- **Context**: 2x2機械配置で部分占有を防止するための設計パターン
- **Sources Consulted**: planファイル（設計上の注意）
- **Findings**: 2パスアプローチ（検証→コミット）が最もシンプルで信頼性が高い
  - パス1: 全セルの境界チェック + 未占有チェック
  - パス2: 全チェック通過後にのみ一括書き込み
- **Implications**: ロールバック不要。検証失敗時は書き込みが発生しないため、部分状態が存在しない

### GridCellDataのスナップショット設計
- **Context**: 呼び出し側にセルデータを公開する際、内部状態の不正変更を防止する必要がある
- **Sources Consulted**: planファイル、structure.md
- **Findings**: RefCountedベースの読み取り専用オブジェクトとして毎回新規生成する。GDScriptにはimmutableフィールドの言語サポートがないため、規約ベースで読み取り専用を保証
- **Implications**: get_cell()は毎回新しいGridCellDataインスタンスを返す。パフォーマンスへの影響は軽微（呼び出し頻度が低い）

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| データ指向（採用） | PackedArrayベースの密データ + Dictionary疎データ | メモリ効率、キャッシュフレンドリー、SceneTree非依存 | GDScriptの型安全性が弱い | tech.mdのハイブリッドデータ指向方針に完全準拠 |
| ノードベース | 各セルをNode2Dとして管理 | Godotエディタとの親和性 | 64x64=4096ノードは重い、SceneTree依存 | tech.md方針に違反 |
| Resourceベース | 各セルをResourceサブクラスで管理 | シリアライズ容易 | ランタイム変更のオーバーヘッド | ランタイム状態にはRefCountedが適切 |

## Design Decisions

### Decision: インデックス計算方式
- **Context**: 2D座標(x, y)から1D配列インデックスへの変換方式の選定
- **Alternatives Considered**:
  1. `y * width + x`（行優先）
  2. `x * height + y`（列優先）
- **Selected Approach**: `y * width + x`（行優先）
- **Rationale**: Godot組み込みのTileMapLayerと同じ行優先順序。将来のレンダリング同期で変換が不要
- **Trade-offs**: なし（業界標準的な選択）

### Decision: 占有の拒否 vs 例外
- **Context**: 占有済みセルへの再占有や範囲外占有の試行時の振る舞い
- **Alternatives Considered**:
  1. bool返却（成功/失敗）
  2. 例外/アサーション
- **Selected Approach**: bool返却
- **Rationale**: GDScriptでは例外機構が限定的。呼び出し側が結果を確認して分岐する設計がGDScript慣習に合致。design-principlesの「Fail Fast」は入力検証で担保
- **Trade-offs**: 呼び出し側が戻り値を無視するリスクがあるが、テストで検証可能

## Risks & Mitigations
- GDScriptの型安全性の限界（enumがintエイリアス）→ 静的型付けアノテーションを徹底し、テストでカバー
- GridCellDataの不変性が言語レベルで保証されない → 規約と命名で読み取り専用を明示、テストで検証
- PackedInt32Arrayのサイズ変更時のパフォーマンス → 初期化時に一括resize、ランタイム中のリサイズは禁止

## References
- Godot 4.3 PackedInt32Array — https://docs.godotengine.org/en/stable/classes/class_packedint32array.html
- Godot 4.3 RandomNumberGenerator — https://docs.godotengine.org/en/stable/classes/class_randomnumbergenerator.html
- プロジェクトsteering: tech.md（タイルマップ実装方針）
- プロジェクトsteering: structure.md（ディレクトリパターン）
- プロジェクトsteering: testing.md（テスト戦略）
