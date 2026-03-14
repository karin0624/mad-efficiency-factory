# Research & Design Decisions: Conveyor Belt

## Summary
- **Feature**: `conveyor-belt`
- **Discovery Scope**: New Feature（グリーンフィールド — ベルトシミュレーションは新規コンポーネント群で構築）
- **Key Findings**:
  - 既存コードベース（CoreGrid, PlacementSystem, TickClock, EntityRegistry）はRefCountedベースの純粋ロジックパターンを一貫して採用しており、ベルトシステムも同パターンに従う
  - tech.mdに「スロットベース(4スロット/タイル)」と記載があるが、planでは「1タイル=最大1アイテム」と明記されており、MVPでは1スロット/タイルを採用する
  - ベルト接続グラフは配置/撤去時のみダーティ再構築する方針がtech.mdで決定済み

## Research Log

### ベルトデータモデルの設計
- **Context**: ベルトタイルごとのアイテム保持と進行状態をどのように表現するか
- **Sources Consulted**: tech.md（ベルトシステム方針）、planファイル（制約と前提）
- **Findings**:
  - tech.mdでは「スロットベース(4スロット/タイル)、ItemType+Progress格納」と記載
  - planでは「1タイルあたりの搬送容量は最大1個」「搬送速度は1タイル/秒」と明記
  - 60tpsで1タイル/秒 → 1ティックあたり1/60タイル進行
  - アイテムのプログレス（0.0〜1.0）を管理し、1.0到達で次タイルへ転送
- **Implications**: MVPでは1タイル=1アイテムの単純モデルを採用。将来の4スロット拡張に備え、progress値を保持する設計とする

### ベルト接続グラフと更新戦略
- **Context**: ベルト間の転送関係をどう管理し、配置/撤去時にどう更新するか
- **Sources Consulted**: tech.md、plan（ベルト接続の更新セクション）
- **Findings**:
  - tech.md: 「ベルト接続グラフは配置/撤去時のみダーティ再構築（毎ティック再構築しない）」
  - 各ベルトは`downstream`（向き方向の隣接ベルト/機械入力ポート）への参照を保持
  - PlacementSystemの配置/撤去後に影響範囲のベルトの接続を再計算
- **Implications**: BeltGraphコンポーネントが接続関係を管理し、ダーティフラグで遅延再構築する

### ティック処理順序とバックプレッシャー
- **Context**: 複数ベルト上のアイテムを1ティックでどの順序で処理するか
- **Sources Consulted**: tech.md（チェーン末尾→先頭処理順）、plan（バックプレッシャー、FIFO）
- **Findings**:
  - tech.md: 「チェーン末尾→先頭処理順」— 下流から上流へ処理することでFIFOと飛び越え防止を自然に実現
  - バックプレッシャー: 下流が移動不可→上流も移動不可、連鎖的に伝播
  - 末尾から処理すると、空きが即座に反映されて上流のアイテムが1ティック内で転送可能
- **Implications**: BeltTransportSystemはベルトチェーンを末尾→先頭の順で処理する

### 既存コードベースとの統合ポイント
- **Context**: 新規ベルトコンポーネントが既存システムとどう接続するか
- **Sources Consulted**: 既存コードの分析（CoreGrid, PlacementSystem, TickClock, EntityRegistry, ItemCatalog）
- **Findings**:
  - EntityRegistry: Belt(ID=3)は既に登録済み。フットプリント Vector2i(1,1)
  - PlacementSystem: 配置/撤去のロジックは既存。ベルト固有の後処理（接続グラフ更新）を追加する必要がある
  - TickClock: 60tps固定。BeltTransportSystemはティックごとに呼び出される
  - CoreGrid: 占有管理は既存。ベルト固有のデータ（アイテム、progress）は別ストレージ
  - ItemCatalog: アイテム種別IDでベルト上のアイテムを識別
- **Implications**: 既存クラスは変更せず、新規コンポーネントが既存APIを利用する形で統合

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| フラットDictionary | Vector2i→BeltTileDataのDictionaryでベルト状態を管理 | シンプル、既存パターン（_occupancy）と一致 | チェーン処理順序の事前計算が必要 | MVPに適切 |
| チェーンリスト | ベルトチェーンをリンクリストで管理 | 処理順序が自然 | 接続更新時のリスト再構築が複雑 | 将来拡張で検討 |
| ECSコンポーネント | ベルトデータをECSコンポーネントとして管理 | 拡張性が高い | GDScriptでは過剰な抽象化 | 不採用 |

## Design Decisions

### Decision: ベルトデータの保持方式
- **Context**: ベルトタイルごとのアイテムと進行状態をどう保持するか
- **Alternatives Considered**:
  1. CoreGridに新フィールドを追加 — CoreGridの責務が肥大化する
  2. BeltGrid（専用Dictionary）で独立管理 — 既存パターンと一貫、CoreGridは変更不要
- **Selected Approach**: BeltGrid（Dictionary<Vector2i, BeltTileData>）として独立管理
- **Rationale**: CoreGridの単一責務を維持し、ベルト固有のデータを分離することで、テスタビリティと保守性を確保
- **Trade-offs**: CoreGridとBeltGridの整合性を外部で保証する必要がある
- **Follow-up**: PlacementSystemの配置/撤去時にBeltGridも同期更新すること

### Decision: ティック内処理順序
- **Context**: FIFOとバックプレッシャーを保証するための処理順序
- **Alternatives Considered**:
  1. ランダム順 — FIFO保証が困難
  2. 上流→下流順 — 1ティックで飛び越えが発生する可能性
  3. 下流→上流順（末尾→先頭） — tech.mdの既定方針
- **Selected Approach**: 下流→上流順（末尾→先頭）
- **Rationale**: tech.mdで決定済みの方針に従う。下流から処理することで空きスロットが即座に利用可能になり、FIFOと飛び越え防止が自然に実現される
- **Trade-offs**: 処理順序の事前計算が必要（トポロジカルソートまたは深さベースのソート）
- **Follow-up**: ベルト追加/撤去時に処理順序キャッシュを再構築

### Decision: 接続グラフの更新タイミング
- **Context**: ベルト間の転送関係をいつ更新するか
- **Alternatives Considered**:
  1. 毎ティック再構築 — パフォーマンスコストが高い
  2. 配置/撤去時にダーティフラグ付き遅延再構築 — tech.mdの既定方針
- **Selected Approach**: 配置/撤去時にダーティフラグ付き遅延再構築
- **Rationale**: tech.mdで決定済み。配置/撤去が発生しない通常ティックでは再構築コストゼロ
- **Trade-offs**: ダーティフラグの管理が必要
- **Follow-up**: ティック処理の冒頭でダーティフラグを確認し、必要時のみ再構築

## Risks & Mitigations
- 処理順序の事前計算コスト — 配置/撤去時のみ発生するため、通常のゲームプレイには影響しない。ベルト数500本程度では十分高速
- CoreGridとBeltGridの整合性 — PlacementSystemのplace/remove後にBeltGridを同期更新するフックを設ける
- 機械ポートI/Oとの統合 — 本機能のスコープでは機械ポートとの基本的な受け渡しのみ。詳細な接続解決は「機械ポートI/O」機能として別途定義

## References
- tech.md — ベルトシステムの設計方針（スロットベース、チェーン末尾→先頭処理順、ダーティ再構築）
- structure.md — ディレクトリ構造とコード編成原則
- testing.md — テスト戦略とパフォーマンスベンチマーク基準
