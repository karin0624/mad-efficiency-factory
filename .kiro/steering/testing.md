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
| 見た目・アニメーション・操作感の確認 | L3 | 自動化不可、人間が目視で判断 |

**迷ったらL1を選ぶ**。テスト対象をリファクタリングしてSceneTree依存を外せないか検討する。

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
3. **L3人間レビュー**: ビジュアル品質・操作感・ゲームフィールの手動確認完了

---
_テストの判断基準とパターンを文書化する。ディレクトリ構造はstructure.md、実行コマンドはtech.mdを参照_
