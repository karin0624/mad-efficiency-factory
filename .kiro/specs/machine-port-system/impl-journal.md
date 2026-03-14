# Implementation Journal — machine-port-system
_Design deviations captured during implementation. Run `/kiro:design-reconcile machine-port-system` to reconcile._

## Task 5.2 — [ARCHITECTURE]
- **Date**: 2026-03-15
- **Design says**: design.md「Systems / Adapter」セクションで `MachinePortSystemNode` を `extends Node` として定義。TickEngineNodeのtick_firedシグナルを直接受信するNodeアダプターとして記述。
- **Actually implemented**: `MachinePortSystemNode` を `extends RefCounted` として実装（`godot/scripts/systems/machine_port_system_node.gd`）。`tick_output()` / `tick_input()` / `on_entity_placed()` / `on_entity_removed()` の4メソッドを公開し、`factory_placement.gd` のNodeレイヤーから呼び出すパターンを採用。
- **Reason**: BeltTransportSystemと同一のパターン（RefCountedコア + Nodeアダプターからの呼び出し）に準拠。SceneTree非依存でL1テストが可能になり、テスト容易性が向上。シグナルの直接接続はNodeラッパー（factory_placement.gd）が担う。設計書のアーキテクチャ原則「コアロジックのSceneTree非依存」に即している。
