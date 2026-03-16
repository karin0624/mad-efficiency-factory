# Implementation Journal — entity-placement
_Design deviations captured during implementation. Run `/kiro:design-reconcile entity-placement` to reconcile._

## Task 1.2 — [CONSTRAINT]
- **Date**: 2026-03-16
- **Design says**: `create_default()` Postconditions に「Miner(1x1), Smelter(1x1), Belt(1x1), DeliveryBox(1x1)が登録済み」と記載（modification後の設計）
- **Actually implemented**: entity_registry.gd の create_default() を Miner=Vector2i(2,2)→Vector2i(1,1)、Smelter=Vector2i(2,2)→Vector2i(1,1) に修正
- **Reason**: modification ID=1 による仕様変更（Miner/Smelterフットプリント2x2→1x1）の適用

## Tasks 3.1, 3.2, 3.3 — [CONSTRAINT]
- **Date**: 2026-03-16
- **Design says**: PlacementSystem テストで「矩形フットプリントエンティティ」を使用して境界・多セル動作を検証する
- **Actually implemented**: Miner(ID=1)が1x1になったため、既存テストのMiner=2x2参照をすべてテスト専用2x2エンティティ(ID=99, "TestLarge")に置き換えた。before_test()でEntityRegistry.create_default()後にID=99を追加登録するパターンを使用。影響ファイル: test_placement_system_can_place.gd, test_placement_system_place.gd, test_placement_system_remove.gd, test_placement_system_rotate.gd, test_ghost_preview_node.gd
- **Reason**: MVPエンティティが全て1x1になったことで、多セル動作検証にはテスト専用エンティティが必要となった
