---
id: "spec/0001"
title: "Miner/Smelterフットプリントを2x2から1x1に変更し、汎用矩形アーキテクチャを維持する"
status: proposed
date: "2026-03-16"
category: "spec"
spec: "entity-placement"
supersedes: null
superseded_by: null
tags: ["footprint", "entity-definition", "mvp", "architecture"]
enforcement: null
---

## Context

entity-placement specの初期設計では、MinerとSmelterのフットプリントを2x2として定義していた（Req 7.1, 7.2）。しかし上流のspec修正により、MVPエンティティのサイズを全て1x1に統一する方針となった。この変更は単なる値の変更にとどまらず、Req 2.4の境界テストケースの判定が「(63,63)への2x2配置を拒否する」から「(63,63)への1x1配置を許可する」へと反転するセマンティック変更を含む。また、Req 1.3では2x2エンティティの具体例示としてMiner/Smelterを参照していたが、この参照も汎用記述に変更する必要がある。一方で、将来的に2x2以上の大型機械を追加できるよう、汎用矩形フットプリントアーキテクチャ（EntityDefinition.footprint: Vector2i、CoreGrid.occupy_rect、PlacementSystemの汎用矩形処理）は設計上維持することが求められた。

## Decision Drivers

- MVPスコープの簡素化: 全エンティティを1x1にすることで初期実装・テストのコストを削減できる
- 上流spec整合性: product.mdステアリングの修正に追従し、specとの齟齬を解消する必要がある
- 将来拡張性の担保: 2x2以上の大型機械追加に備え、汎用矩形処理を捨てずに維持する設計的価値がある
- テスト戦略の安定性: 多セルフットプリント検証はテスト専用エンティティ定義を使用することで、実エンティティのサイズ変更に左右されないテストを実現できる
- Req 2.4の境界テスト判定反転（reject→allow）は受入基準のセマンティック変更であり、記録と追跡が必要

## Considered Options

1. **Miner/Smelterを1x1に変更し、汎用矩形アーキテクチャを維持する（採用）**
   - 利点: MVPのシンプルさを保ちながら、将来の大型機械拡張に備えられる。テスト専用2x2エンティティで多セル処理の検証を継続できる
   - 欠点: コアアーキテクチャと実エンティティサイズの乖離が生まれ、「なぜ汎用処理があるのに全部1x1か」という疑問が生じやすい

2. **Miner/Smelterを1x1に変更し、汎用矩形アーキテクチャも1x1専用に簡略化する**
   - 利点: コードとデータの整合性が高まり、不要な複雑さを除去できる
   - 欠点: 将来2x2以上のエンティティを追加する際にアーキテクチャの再設計が必要になる。MVP後のリファクタリングコストが高い

## Decision

MinerとSmelterのフットプリント定義値を2x2から1x1に変更する。同時に、汎用矩形フットプリントアーキテクチャ（EntityDefinition.footprint: Vector2i、CoreGrid.occupy_rect、PlacementSystemの汎用矩形処理）は変更せず維持する。多セルフットプリントの検証はテスト専用エンティティ定義（例: 2x2のテスト用エントリ）を使用して継続する。これにより、MVPのシンプルさと将来の大型機械拡張性を両立させる。

## Consequences

### Positive

- MVPの全エンティティが1x1になり、初期実装・テストが単純化される（SPEC_DIFF: requirements.md Introduction行の更新で確認）
- Req 2.4の境界テスト: (63,63)への配置が許可されるケースになり、グリッド端での正常動作を検証できる（SPEC_DIFF: requirements.md Req 2.4の変更で確認）
- テスト専用エンティティ定義により、実エンティティのサイズに依存しない矩形フットプリントテストが実現する（SPEC_DIFF: design.md TestingStrategy更新で確認）
- EntityRegistry.create_default()のPostconditionsがコード実装と一致し、ドキュメントと実装の齟齬がなくなる（SPEC_DIFF: design.md create_default()コメント更新で確認）

### Negative (accepted trade-offs)

- 汎用矩形アーキテクチャを維持するため、MVPフェーズではそのコードパスがエンティティの通常使用では実行されず、テスト専用エンティティでのみ検証される
- product.md（steering）には旧来のMiner:2x2, Smelter:2x2の記述が残存しており、steeringドキュメントの別途更新が必要（SPEC_DIFF: design.md注記で確認）
- Task 1.2/3.1/3.2/3.3は完了済みタスクへの遡及修正を含み、実装コード（create_defaultのフットプリント値）とテストコードの両方に変更が必要

### Constraints Created

- MVPエンティティ（Miner, Smelter, Belt, DeliveryBox）のフットプリントは全て1x1として扱う。1x1以外のフットプリントを持つ実エンティティをMVPに追加する場合は、このADRを参照し意思決定を更新すること
- 汎用矩形フットプリント処理（occupy_rect等）の削除・簡略化は行わない。将来の大型機械追加時に活用すること
- 多セルフットプリントのテストはテスト専用エンティティ定義を用いること（実エンティティへの依存を避けるため）

## Enforcement

N/A — レビューで確認
