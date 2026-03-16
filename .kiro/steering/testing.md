# テスト戦略

## 哲学

- **振る舞いテスト**: 内部実装ではなく公開APIの入出力を検証する。リファクタリングでテストが壊れないことが理想
- **ロジック分離がテスト可能性を生む**: `scripts/core/`と`scripts/systems/`がSceneTree非依存であることで、高速なCLIテスト（xvfb-run経由）が可能になる（分離ルール自体はtech.md参照）
- **クリティカルパス優先**: カバレッジ100%は追求しない。資源フロー・ベルト輸送・機械加工など、ゲームの根幹ロジックを深くテストする

## テスト層の選択基準

Layer定義はtech.mdを参照。ここでは**どの層を選ぶかの判断基準**を示す。

| 判断条件 | 選択層 | 理由 |
|----------|--------|------|
| テスト対象がRefCounted/Resourceのみ | L1 | SceneTree不要、xvfb-runで高速 |
| Node間のシグナル通信・`add_child`が必要 | L2 | SceneTree依存、xvfb-run + GdUnit4で実行（SceneRunner/InputEvent対応） |
| セマンティックダンプ＋スクショでAI判定可能な状態・視覚検証（数値メトリクスはアサーションで判定） | L3 | SceneRunner フルシーン+アーティファクト出力+AI評価、spec-implが実行 |
| 主観的で再現困難な品質確認 | L4 | 自動化不可、人間が目視で判断 |

**迷ったらL1を選ぶ**。テスト対象をリファクタリングしてSceneTree依存を外せないか検討する。

### L3とL4の振り分け基準

- **L3（E2Eテスト）**: セマンティックダンプ（状態データ）が主、スクショは視覚品質のみ。**数値メトリクス（FPS、応答時間等）はアサーションで確定的に判定し、AI評価の対象外**
  - 例: アイテムが正しい位置に存在するか（セマンティックダンプ）、ベルトの視覚描画が正しいか（スクショ）
- **L4（ヒューマンレビュー）**: 主観的で再現が困難、AIでは判定できない項目
  - 例: UIの操作感・ゲームフィール・芸術的な品質判断

### テストディレクトリと層の対応

| ディレクトリ | 対応層 | 必須条件 |
|-------------|--------|---------|
| `tests/core/` | L1 | RefCounted/Resourceのみ |
| `tests/systems/` | L2 | Node依存（add_child/シグナル） |
| `tests/e2e/` | L3 | SceneRunner使用、アーティファクト出力 |

`tests/e2e/` に配置するテストは必ず `scene_runner()` を使用すること。
SceneRunnerを使わないテストは `tests/core/` または `tests/systems/` に配置する。

## GdUnit4パターン

### テストスイート基本構造

```gdscript
extends GdUnitTestSuite

var _sut: GridCoord  # System Under Test

func before_test() -> void:
    _sut = GridCoord.new()

func after_test() -> void:
    _sut = null

func test_adjacent_returns_four_neighbors() -> void:
    # Arrange
    var origin := Vector2i(5, 5)
    # Act
    var neighbors := _sut.get_adjacent(origin)
    # Assert
    assert_array(neighbors).has_size(4)
    assert_array(neighbors).contains([
        Vector2i(5, 4), Vector2i(5, 6),
        Vector2i(4, 5), Vector2i(6, 5)
    ])
```

### フック

- `before()` / `after()`: スイート単位（全テストの前後に1回）
- `before_test()` / `after_test()`: テストケース単位（各テストの前後に毎回）
- Nodeを使うテストでは`after_test()`で`auto_free()`を確実に行う

### よく使うアサーション

- 値: `assert_that()`, `assert_str()`, `assert_int()`, `assert_float()`, `assert_bool()`
- コレクション: `assert_array()`, `assert_dict()`
- シグナル: `assert_signal(emitter).is_emitted("signal_name")`
- オブジェクト: `assert_object(obj).is_instanceof(ExpectedClass)`

## モック戦略

- **RefCountedクラス**: 直接`new()`で生成。モック不要 — これがデフォルト
- **Nodeが必要な場合**: `auto_free()`でリーク防止 + GdUnit4の`mock()`/`spy()`を使用
- **外部依存の分離**: シグナル経由のインターフェースで切り離し、テスト時はスタブシグナルを発火
- **モック禁止**: テスト対象自体をモックしない。Godotエンジン内部APIもモックしない

```gdscript
# L2: Node依存テストの例
func test_belt_emits_item_transferred() -> void:
    var belt := auto_free(BeltNode.new())
    add_child(belt)
    var item := ResourceType.new()

    belt.transfer(item)

    await assert_signal(belt).is_emitted("item_transferred")
```

## GoPeak連携

GoPeak MCPツールが利用可能な場合、テストワークフローを強化する。**全てベストエフォート — 不可時はスキップまたはBashフォールバック**。

| ツール | 用途 | 不可時の対応 |
|--------|------|-------------|
| `mcp__gopeak__lsp_diagnostics` | テスト実行前の静的解析 | スキップし「LSP unavailable」と出力 |
| `mcp__gopeak__editor_run` | L2のランタイム検証 | `xvfb-run godot`で代替 |
| `mcp__gopeak__editor_debug_output` | ランタイムログ取得 | Bash出力で代替 |
| `mcp__gopeak__editor_stop` | ランタイム検証後のクリーンアップ | Bashプロセスは自動終了 |
| `mcp__gopeak__script_create` | テストファイル生成 | `Write`ツールで代替 |

### テスト実行環境

GdUnit4公式推奨の `xvfb-run` + X11仮想ディスプレイ方式を使用する。

**理由**: `--headless`モードではDisplayServerHeadlessが使われ、InputEventが伝播しないためSceneRunner/InputEventベースのL2テストが動作しない。`xvfb-run`でX11仮想ディスプレイを提供することで、DisplayServerがx11モードで動作しInputEventが正常に処理される。

**コマンド**:
```bash
# ヘルパースクリプト経由（推奨）
./scripts/run-tests.sh

# 直接実行
xvfb-run --auto-servernum godot --display-driver x11 --rendering-driver opengl3 --audio-driver Dummy --path godot/ -s addons/gdUnit4/bin/GdUnitCmdTool.gd --continue
```

**前提パッケージ**: `sudo apt-get install -y xvfb`

## E2Eテストパターン (L3)

L3 E2EテストはSceneRunnerを使用してフルシーンを起動し、セマンティックダンプとスクショをAIが評価する。

### ハイブリッド評価アプローチ (L3)

検証手段は対象に応じて使い分ける。AI評価はプログラム的に検証困難な項目のみに適用する。

| 検証対象 | 手法 | 理由 |
|----------|------|------|
| ロジック状態（アイテム位置、ポート接続、ベルトトポロジー） | GameStateDump + AI評価 | 確定的・高速・トークン効率的 |
| ビジュアル品質（描画、アニメーション、レイアウト） | スクショ + AI評価 | 視覚的判断が必要 |
| 数値メトリクス（FPS、応答時間） | GdUnit4アサーション | 確定的に判定可能、AI評価不要 |
| シーン構造 | SceneTreeDump + AI評価 | ノード階層・可視性を確認 |

### L3 評価プロトコル

L3タスクの完了判定:

1. **GdUnit4アサーション**: プログラム的に検証可能な項目（数値閾値、状態一致等）は**アサーションで判定完結**
2. **セマンティックダンプ評価**: アサーションでは捉えきれない状態の妥当性（トポロジー、接続関係等）をAIが `test_snapshots/*.txt` を読んで確認
3. **スクショ評価**（視覚検証タスクのみ）: `test_screenshots/*.png` をAIが読み、視覚的に妥当か確認

数値メトリクス（FPS、応答時間）はアサーション成功で十分。
AI評価はプログラム的に検証困難な項目のみに適用する。

E2Eテストが出力すべきアーティファクト:
- **必須**: セマンティックダンプ（`GameStateDump.save()` → `test_snapshots/<test_name>.txt`）
- **推奨**: スクショ（`_save_screenshot()` → `test_screenshots/<test_name>.png`）
- **必須**: メトリクス（`print()` でテスト出力に含める）

### 基本パターン

```gdscript
extends GdUnitTestSuite

func test_e2e_belt_visual() -> void:
    var runner := scene_runner("res://scenes/game.tscn")
    await runner.simulate_frames(60)  # 1秒待機

    var scene_root := runner.scene()

    # セマンティックダンプを保存
    var dumper := GameStateDump.new()
    var catalog := ItemCatalog.create_default()
    var content := dumper.snapshot(
        scene_root._belt_grid,
        scene_root._tick_engine.clock,
        scene_root._system,
        scene_root._port_grid,
        scene_root._registry,
        catalog,
    )
    GameStateDump.save(content, "belt_visual_state.txt")

    # スクショを保存
    var img := get_viewport().get_texture().get_image()
    img.save_png("res://test_screenshots/belt_visual.png")

    # AI評価: Readツールでセマンティックダンプとスクショを読み込み確認
    pass
```

### フィルムストリップパターン

連続スクショによる動作検証 — アニメーションや時系列変化を確認する場合に使用する。

```gdscript
func test_e2e_item_movement_filmstrip() -> void:
    var runner := scene_runner("res://scenes/game.tscn")

    # 複数のフレームでスクショを撮影
    for i in range(5):
        await runner.simulate_frames(12)  # 0.2秒ごと
        var img := get_viewport().get_texture().get_image()
        img.save_png("res://test_screenshots/item_move_%02d.png" % i)

    # AIがフィルムストリップを評価:
    # - アイテムが各フレームで前進していること
    # - アイテムが消失・重複していないこと
    pass
```

### スクショ戦略

| シナリオ | 撮影タイミング | 評価ポイント | セマンティックダンプ併用 |
|----------|---------------|-------------|------------------------|
| ベルト上アイテム移動 | 投入直後・中間・到達時 | 位置の前進、消失なし | はい（アイテム位置確認） |
| バックプレッシャー | 末端塞ぎ後数ティック | アイテム停止の視覚表現 | はい（ベルト状態確認） |
| ゴーストプレビュー | カーソル移動中 | 半透明表示、位置正確性 | いいえ（視覚のみ） |
| 性能メトリクス | 500ベルト配置後 | FPSカウンター値（print出力） | はい（セットアップ確認） |
| 一時停止/再開 | 操作前後 | UI状態の変化 | はい（tick状態確認） |

### スクショ保存先

E2Eテストのスクショは `godot/test_screenshots/` に保存する（`.gitignore`で除外済み）。

### セマンティックダンプ保存先

E2Eテストのセマンティックダンプは `godot/test_snapshots/` に保存する（`.gitignore`で除外済み）。

### GameStateDump ユーティリティ

**場所**: `scripts/core/game_state_dump.gd`

**API**:
```gdscript
class_name GameStateDump extends RefCounted

# コンストラクタ（詳細表示の最大アイテム数、デフォルト20）
func _init(max_detail: int = 20) -> void

# 全状態スナップショット
func snapshot(belt_grid, tick_clock, placement, port_grid,
              entity_registry = null, item_catalog = null) -> String

# 個別ダンプ
func dump_tick(clock: TickClock) -> String
func dump_belts(grid: BeltGrid, catalog: ItemCatalog = null) -> String
func dump_placement(system: PlacementSystem, registry: EntityRegistry = null) -> String
func dump_ports(grid: MachinePortGrid, catalog: ItemCatalog = null) -> String
func dump_summary(belt_grid, port_grid, placement) -> String

# ファイル保存（ベストエフォート）
static func save(content: String, filename: String) -> void
```

**出力フォーマット**:
```
=== GAME STATE SNAPSHOT (tick=1234, paused=false) ===

--- BELTS (500 tiles, 450 items) ---
  [SUMMARY MODE: tile_count=500, item_count=450]

--- MACHINES (3 entities) ---
  #1 Miner at (0,0) dir=N footprint=1x1
  #2 Smelter at (4,0) dir=N footprint=1x1

--- PORTS (4 active, 3 connected) ---
  #1 OUTPUT at (1,1) dir=S item=none belt=(1,2) connected=true
  #2 INPUT at (4,0) dir=N item=鉄鉱石 belt=(4,-1) connected=false
```

**詳細制御**: 閾値（デフォルト20）を超えるとサマリーモードに自動切替。`GameStateDump.new(50)` で50件まで詳細表示。

**使用パターン**:
```gdscript
# E2Eテスト内でのダンプ出力
var dumper := GameStateDump.new()
var catalog := ItemCatalog.create_default()
var content := dumper.snapshot(belt_grid, clock, system, port_grid, registry, catalog)
print(dumper.dump_summary(belt_grid, port_grid, system))
GameStateDump.save(content, "test_state.txt")
```

### SceneTreeDump ユーティリティ

**場所**: `tests/helpers/scene_tree_dump.gd`（テスト専用、Node依存のためcore/には配置不可）

**API**:
```gdscript
class_name SceneTreeDump extends RefCounted

# シーンツリーをテキストダンプ
static func dump(root: Node, max_depth: int = 6) -> String
```

**使用パターン**:
```gdscript
# E2Eテスト内でのシーンツリーダンプ
var tree_dump := SceneTreeDump.dump(scene_root)
GameStateDump.save(tree_dump, "scene_tree.txt")  # save()はGameStateDumpを使用
```

## テストしないもの

- **Godotエンジン内部**: 物理演算、レンダリング、シーンツリーのライフサイクル
- **アドオン内部**: GdUnit4自体、サードパーティプラグインの内部動作
- **宣言的設定**: `.tres`リソースの値、エクスポート変数のデフォルト値
- **薄いアダプター**: `scenes/`配下のスクリプトが`core/`/`systems/`へ単純委譲しているだけの場合

## パフォーマンスベンチマーク

- **主指標**: シミュレーション予算 — 1ティックあたりの処理時間上限(ms/tick)
- **副指標**: FPS — ベルト500本+アイテム2000個の状態で30FPS以上を維持
- テストはL1（xvfb-run CLIモード）でティック処理時間を計測し、閾値超過で失敗とする
- FPS計測はL2またはL3で実施（レンダリング込みの実測が必要）

## MVP完了条件

1. **L1全通過**: コアロジック（グリッド、ベルト、機械、資源フロー）のユニットテストが全てグリーン
2. **E2E統合テスト**: 採掘→ベルト5本→精錬→ベルト5本→納品のフローを自動テストで検証
3. **L3 E2Eテスト**: セマンティックダンプ＋スクショによる状態・ビジュアル検証の自動確認完了
4. **L4ヒューマンレビュー**: 主観的品質・操作感・ゲームフィールの手動確認完了

---
_テストの判断基準とパターンを文書化する。ディレクトリ構造はstructure.md、実行コマンドはtech.mdを参照_
