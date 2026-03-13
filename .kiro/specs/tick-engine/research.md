# Research & Design Decisions

## Summary
- **Feature**: `tick-engine`
- **Discovery Scope**: New Feature（グリーンフィールド）
- **Key Findings**:
  - Godot 4.3+の`_physics_process(delta)`は固定レートコールバックだが、Tick Engineのコアロジックはこれに依存せず純粋なRefCountedクラスとして実装すべき
  - 浮動小数点累積誤差を回避するため、蓄積時間の管理にはマイクロ秒整数方式を採用する
  - コアロジック（RefCounted）とGodotブリッジ（Node）の2層構成により、L1テストの完全な独立性を確保できる

## Research Log

### Godotの_physics_processと固定ティックの関係
- **Context**: tech.mdでは「`_physics_process`（デフォルト60Hz）でシミュレーション更新」と記載。Tick Engineがこれをどう活用すべきか
- **Sources Consulted**: Godot 4.3公式ドキュメント、tech.md、structure.md
- **Findings**:
  - `_physics_process(delta)`はGodotが固定間隔で呼び出すコールバック。デフォルト60Hz（ProjectSettings: `physics/common/physics_ticks_per_second`）
  - Godot自体がdelta蓄積とキャッチアップを内部で管理している
  - しかし、Tick Engineのコアロジックをこの仕組みに直接依存させると、SceneTree非依存の原則に反する
  - コアロジックは「deltaTimeを受け取り、ティック発火数を返す」純粋関数として設計し、Godot Nodeは薄いアダプターとしてdeltaを渡す役割のみ持たせるべき
- **Implications**: コアロジックはRefCountedクラスとして実装し、`_physics_process`はアダプターNodeが受け持つ。これにより完全なL1テスト可能性を確保

### 浮動小数点累積誤差の回避方式
- **Context**: 要件7で決定性の保証が求められている。浮動小数点の蓄積時間管理は長時間実行で誤差が蓄積するリスクがある
- **Sources Consulted**: ゲームプログラミングパターン（Game Programming Patterns — Robert Nystrom）、Fixed Timestep実装事例
- **Findings**:
  - 方式A: float蓄積（シンプルだが累積誤差リスク）
  - 方式B: マイクロ秒整数蓄積（整数演算で誤差ゼロ、ただしGDScriptのintは64bit整数なのでオーバーフローの心配は実質不要）
  - 方式C: ティックカウントベース（期待ティック数と実ティック数の差分で管理）
  - GDScriptのfloatは64bit doubleなので、実用上は数十時間程度では問題ないが、決定性要件を厳密に満たすには整数方式が安全
- **Implications**: マイクロ秒整数方式を採用。ティック間隔 = 16667μs、蓄積時間もμs単位で管理。deltaTime（float秒）からの変換は入口で1回のみ行う

### キャッチアップ制限の実装パターン
- **Context**: 要件3でスパイラルオブデス防止のため1フレーム最大5ティックに制限
- **Sources Consulted**: Fixed Timestepパターン実装事例
- **Findings**:
  - 標準パターン: whileループ内でカウンタを管理し、上限到達時にループを抜ける
  - 超過分の蓄積時間は破棄する（繰り越さない）ことで次フレームへの影響を防止
  - 破棄方式: 蓄積時間を0にリセットするか、ティック間隔未満にクランプするか。後者が端数保持の点で正確だが、要件では「破棄」と明記されているため、蓄積時間を0にリセットする方式を採用
- **Implications**: キャッチアップ上限到達時は蓄積時間を0にリセット

### 並列実装の可能性分析
- **Context**: タスク生成フェーズでの並列化機会の特定
- **Findings**:
  - コアロジック（TickClock）とGodotブリッジ（TickEngineNode）は独立して実装可能
  - テストはコアロジック完成後に実装可能（依存）
  - TickClockの内部機能（蓄積・発火・停止/再開）は相互依存が強く並列化困難

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 純粋RefCounted + Nodeアダプター | コアロジックをRefCountedに、Godot連携をNodeアダプターに分離 | L1テスト完全対応、決定性保証、steering準拠 | アダプター層のオーバーヘッド（微小） | tech.md/structure.mdの分離原則に完全合致 |
| Node直接実装 | `_physics_process`内に全ロジック実装 | シンプル、レイヤー数最小 | L1テスト不可、SceneTree依存 | steering原則に違反 |
| Autoloadシングルトン | グローバルAutoloadとしてティック管理 | アクセス容易 | tech.md「ゲーム状態にグローバルシングルトンを使わない」に違反 | 明示的に禁止されている |

## Design Decisions

### Decision: コアロジックの実装基盤
- **Context**: Tick Engineのコアティックロジックをどこに配置するか
- **Alternatives Considered**:
  1. Node直接実装 — `_physics_process`内に全ロジック
  2. RefCounted純粋クラス — SceneTree非依存の純粋ロジック
- **Selected Approach**: RefCounted純粋クラス（TickClock）
- **Rationale**: structure.mdの「コアロジックはSceneTree/Node APIに非依存」、tech.mdの「ゲームロジックはSceneTree/Node APIに依存しない純粋なデータ＋システム」に合致。L1テストでの完全な検証が可能
- **Trade-offs**: アダプター層が必要になるが、コードは薄い（deltaを渡すだけ）
- **Follow-up**: Nodeアダプターが正しくdeltaを変換・転送していることのL2テスト

### Decision: 蓄積時間の管理方式
- **Context**: 浮動小数点累積誤差を回避しつつ、決定性を保証する必要がある
- **Alternatives Considered**:
  1. float蓄積方式 — シンプルだが長時間実行で誤差リスク
  2. マイクロ秒整数方式 — 整数演算で誤差ゼロ
  3. ティックカウントベース方式 — 蓄積をティック数で管理
- **Selected Approach**: マイクロ秒整数方式
- **Rationale**: GDScriptのintは64bit整数のため、マイクロ秒単位でも約29万年分を表現可能。決定性要件を確実に満たす。deltaTime（float）からの変換は入口で1回のみ行うため、変換誤差の影響は最小
- **Trade-offs**: deltaTime→μs変換時に丸めが発生するが、これは各フレームで独立しており累積しない
- **Follow-up**: 変換精度のテストケースを追加

### Decision: キャッチアップ超過時の蓄積時間処理
- **Context**: 最大5ティック発火後の蓄積時間をどう扱うか
- **Alternatives Considered**:
  1. 蓄積時間を0にリセット — 超過分を完全破棄
  2. 蓄積時間をティック間隔未満にクランプ — 端数のみ保持
- **Selected Approach**: 蓄積時間を0にリセット
- **Rationale**: planで「超過分は破棄」と明記されている。端数保持はキャッチアップ制限の意図（過負荷からの回復）に反する可能性がある
- **Trade-offs**: フレームスパイク直後に端数分の微小な遅延が失われるが、体感上の影響はない
- **Follow-up**: テストで100ms入力時に正確に5ティック発火し、蓄積時間が0であることを検証

## Risks & Mitigations
- **リスク1**: deltaTime→μs変換の丸め誤差 — 各フレーム独立のため累積しない。テストで検証
- **リスク2**: GDScriptのint演算性能 — 64bit整数演算はfloatと同等以上の性能。ボトルネックにならない
- **リスク3**: Godotの`_physics_process`のdeltaが厳密に1/60でない場合 — コアロジックは任意のdeltaTimeに対応する設計のため問題なし

## References
- Godot 4.3 Engine Documentation — `_physics_process`, `ProjectSettings.physics/common/physics_ticks_per_second`
- Game Programming Patterns (Robert Nystrom) — Game Loop chapter, Fixed Timestep pattern
- structure.md — `scripts/core/`の配置ルール、`extends RefCounted`の制約
- tech.md — ハイブリッドデータ指向アーキテクチャ、分離原則、シミュレーション制約
