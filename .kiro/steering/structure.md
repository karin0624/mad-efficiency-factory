# プロジェクト構造

## 編成方針

機能レイヤードアプローチ: コアゲームロジックはSceneTree/Node APIに非依存とし、Godot固有のコードは別レイヤーに配置。これによりヘッドレスでのユニットテストが可能になり、シミュレーションの決定性を維持。

## ディレクトリパターン

### コアロジック (`godot/scripts/core/`)
**目的**: 純粋なゲームロジック — 資源タイプ、グリッドデータ、ベルトシミュレーション、機械加工
**ルール**: `extends Node` やSceneTree APIは禁止。ランタイム状態は`extends RefCounted`、編集用定義データは`extends Resource`。
**例**: `entity_definition.gd`, `belt_grid.gd`, `placement_system.gd`, `grid_cell_data.gd`

### ECS / システム (`godot/scripts/systems/`)
**目的**: ティック駆動のシミュレーションシステム（ベルト輸送、機械加工、資源フロー）
**ルール**: シーンツリーへの直接アクセスは禁止。描画・入力等のプレゼンテーションロジックは`scenes/`に配置すること
**2つのサブパターン**:
- **純粋ロジック（推奨）**: `extends RefCounted` — tick engineから呼び出される。例: `belt_transport_system.gd`
- **ティック受信**: `extends Node` — `_physics_process`でティックを駆動する薄いノード。例: `tick_engine_node.gd`

### シーン＆ノード (`godot/scenes/`)
**目的**: Godotシーンファイル(.tscn)とアタッチされたスクリプト
**ルール**: 薄いアダプター — ロジックはcore/systemsに委譲し、レンダリングと入力を処理
**例**: `main.tscn`, `factory_grid.tscn`, `conveyor_belt.tscn`

### UI (`godot/scenes/ui/`)
**目的**: HUD、メニュー、パレット（Godot Controlノード使用）
**例**: `hud.tscn`, `device_palette.tscn`, `delivery_counter.tscn`

### リソース定義 (`godot/resources/`)
**目的**: `extends Resource`のデータ定義（アイテム、レシピ、機械スペック等の`.tres`ファイル）
**ルール**: ゲームデザインデータのみ。ランタイム状態は含めない
**例**: `items/iron_ore.tres`, `recipes/iron_plate.tres`

### テスト (`godot/tests/`)
**目的**: GdUnit4によるテスト
**パターン**: ソース構造をミラー + E2E専用ディレクトリ
- `tests/core/`: `scripts/core/`のユニットテスト（L1）
- `tests/systems/`: `scripts/systems/`の統合テスト（L1/L2）
- `tests/e2e/`: SceneRunnerによるフルシーンE2Eテスト（L3）
**命名**: `test_<対象クラス名>.gd`（例: `test_belt_grid.gd`, `test_machine_port_e2e.gd`）

### スペック (`.kiro/specs/`)
**目的**: 機能ごとの仕様書（要件、設計、タスク）
**パターン**: 機能ごとに1ディレクトリ、cc-sddパイプラインで管理

## 命名規則

- **GDScriptファイル**: snake_case (`belt_transport_system.gd`)
- **シーンファイル**: snake_case (`factory_grid.tscn`)
- **クラス**: PascalCase (`class_name BeltTransportSystem`)
- **シグナル**: snake_case 過去形 (`item_delivered`, `machine_started`)
- **定数**: UPPER_SNAKE_CASE
- **インポート**: 同一モジュール内は`class_name`参照を優先。外部リソースの動的読み込みは`load()`、静的参照は`preload()`

## コード編成原則

- **ロジック ≠ プレゼンテーション**: コアロジックはGodotノードを参照してはならない。Godotスクリプトがデータとビジュアルをブリッジする。
- **シグナル駆動**: プレゼンテーション層↔ロジック層の通知にGodotシグナルまたはイベントバスを使用。シミュレーション内部はティック順序で同期実行し、シグナルに頼らない。（autoload方針はtech.mdを参照）
- **深い継承を避ける**: 継承より合成を優先。シーンは子ノードで動作を構成する。

---
_ファイルツリーではなく、パターンを文書化すること。パターンに従う新しいファイルは更新を必要としない_
