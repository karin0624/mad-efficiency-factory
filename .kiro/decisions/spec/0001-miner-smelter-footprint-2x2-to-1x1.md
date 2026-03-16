---
id: "spec/0001"
title: "MinerとSmelterのフットプリントを2x2から1x1に変更する"
status: proposed
date: "2026-03-17"
category: "spec"
spec: null
specs:
  - entity-placement
  - machine-port-system
supersedes: null
superseded_by: null
tags: []
enforcement: null
---

## Context

MVP機械であるMiner・Smelterは当初2x2フットプリントとして設計・実装された（product.md steering の MVP登場要素表、entity-placement Req 7.1/7.2、machine-port-system の MachinePortConfig デフォルト値）。しかし、ゲームのMVPスコープおよびUI操作性の観点から、これらの機械を1x1フットプリントに縮小する変更要求が生じた。

この変更はentity-placementとmachine-port-systemの両specにまたがる仕様変更であり、完了済みの実装タスク（計8件）の再実装を伴う。また、product.md steeringのMVP登場要素表とも整合性を保つ必要がある。

## Decision Drivers

- Req 7.1/7.2の受入基準（Miner・Smelterのフットプリントサイズ）をセマンティックに変更する必要がある
- PortMathの回転計算ロジックはmachine_sizeパラメータ化済みであり、ロジック変更なしにサイズ変更が可能
- EntityDefinition/EntityRegistryのアーキテクチャは可変サイズ（1x1〜NxN）をサポート済みのため、具体的なデフォルト値のみ変更すれば対応できる
- 将来の2x2以上の大型機械追加を想定した汎用設計を維持する必要がある
- steering/product.md のMVP登場要素表との整合性確保が求められる

## Considered Options

1. **現行の2x2フットプリントを維持する**: Miner・Smelterを2x2のまま変更しない
   - 利点: 完了済みタスクの再実装が不要。実装コストゼロ。
   - 欠点: 変更要求を満たせない。MVPスコープの意図と乖離が生じる。

2. **Miner・Smelterを1x1フットプリントに変更する**: MachinePortConfigのmachine_sizeとポートオフセットを更新し、entity-placementの要件・設計・タスクも同期する
   - 利点: 変更要求を満たす。PortMathの汎用回転計算は1x1でidentity変換になりシンプル。将来の2x2大型機械は別のEntityDefinitionとして追加可能。
   - 欠点: 完了済みタスク（entity-placement: 1.2, 3.1, 3.2, 3.3、machine-port-system: 1.1, 2.1, 2.2, 3.1）の再実装が必要。

## Decision

MinerとSmelter（machine-port-system の type_id=1, type_id=2）のフットプリントを2x2から1x1に変更する。

具体的には以下を採用する:
- MachinePortConfigのMiner・Smelterの`machine_size`を2x2→1x1に変更する
- 出力ポートのoffset `(1,1)` → `(0,0)` に再配置する（Smelterの入力ポート offset=(0,0) は変更なし）
- entity-placement の Req 7.1/7.2 受入基準・Introduction・design.md postcondition・tasks.md 記述を1x1に更新する
- 2x2テストケースはMiner/Smelterではなく汎用テスト用2x2エンティティに差し替える
- PortMathの回転計算ロジックは変更しない（machine_sizeパラメータ化済みのため1x1でも正しく動作する）

この選択肢を採用する理由: アーキテクチャ変更なしにデフォルト値の変更のみで対応でき、将来の大型機械追加に対する汎用設計も維持できるため。

## Consequences

### Positive

- Miner・Smelterが1x1になり、グリッド上の配置自由度が向上する
- PortMathの1x1 identity変換（全方向でoffset=(0,0)→(0,0)）がテストで明示的に保証される
- 2x2以上の大型機械はEntityDefinitionとして独立して追加可能であり、汎用アーキテクチャが維持される
- steering/product.mdとspec群の整合性が保たれる

### Negative (accepted trade-offs)

- 完了済みタスク計8件（entity-placement: 1.2, 3.1, 3.2, 3.3、machine-port-system: 1.1, 2.1, 2.2, 3.1）の再実装が必要となる
- テストコード内のMiner/Smelter 2x2参照とcreate_default()の戻り値が変更となり、既存テストの修正コストが発生する
- Task 6.1/6.2のE2Eテストでベルト隣接座標の調整が必要な可能性がある

### Constraints Created

- 今後、Miner・Smelterは1x1フットプリントとして扱われる
- 2x2以上のフットプリントを持つ機械は、Miner/Smelterとは別のEntityDefinitionとして定義・追加する必要がある
- steering/product.mdのMVP登場要素表（Miner/Smelterのフットプリント欄）は1x1に同期更新することが必要

## Enforcement

N/A — レビューで確認
