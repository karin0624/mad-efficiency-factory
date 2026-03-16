# Implementation Journal — machine-port-system
_Design deviations captured during implementation. Run `/kiro:design-reconcile machine-port-system` to reconcile._

## Task 6.1 — [DATA_MODEL]
- **Date**: 2026-03-17
- **Design says**: タスク6.1「出力ポート→ベルト5本→入力ポートのアイテム到達」—— 精錬機の入力ポートまでの完全フローを検証。
- **Actually implemented**: `test_e2e_output_belt5_input_flow` では Miner 出力ポート→ベルト(5,1) の1ステップ転送のみを検証。Smelter の入力ポート接続を同一テストに含めなかった理由: 1x1 Smelter (dir=N) の入力ポート world_dir=N は隣接位置(5,5)のベルトが dir=N を持つ必要があるが、出力テスト用ベルト5本はすべて dir=S。BeltTransportSystem によるベルト搬送シミュレーションは本スペックのスコープ外。代わりに `test_e2e_100_items_conservation` で 100 アイテムの保存則を検証。
- **Reason**: 入力ポート接続にはベルト方向一致が必要（設計の条件: `belt.direction == port.world_direction`）。完全Miner→Smelterフローは BeltTransportSystem 統合が必要で、本スペックのスコープ外。出力転送・入力引き込みの個別テストで両方向を網羅済み（タスク4.1, 4.3）。

## Task 5.2 — [ARCHITECTURE]
- **Date**: 2026-03-15
- **Design says**: design.md「Systems / Adapter」セクションで `MachinePortSystemNode` を `extends Node` として定義。TickEngineNodeのtick_firedシグナルを直接受信するNodeアダプターとして記述。
- **Actually implemented**: `MachinePortSystemNode` を `extends RefCounted` として実装（`godot/scripts/systems/machine_port_system_node.gd`）。`tick_output()` / `tick_input()` / `on_entity_placed()` / `on_entity_removed()` の4メソッドを公開し、`factory_placement.gd` のNodeレイヤーから呼び出すパターンを採用。
- **Reason**: BeltTransportSystemと同一のパターン（RefCountedコア + Nodeアダプターからの呼び出し）に準拠。SceneTree非依存でL1テストが可能になり、テスト容易性が向上。シグナルの直接接続はNodeラッパー（factory_placement.gd）が担う。設計書のアーキテクチャ原則「コアロジックのSceneTree非依存」に即している。
