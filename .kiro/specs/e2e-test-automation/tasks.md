# Implementation Plan

- [x] 1. steering docsのレイヤー体系を再定義する
- [x] 1.1 testing.mdにL3 E2Eテスト層を追加し、旧L3をL4に移行する
  - テスト層の選択基準テーブルにL3 E2E行を追加（手法: SceneRunner フルシーン+スクショ/メトリクス+AI視覚評価、決定性: 非決定的(AI)、実行者: spec-impl）
  - 旧L3（見た目・アニメーション・操作感の確認）をL4に変更し、「自動化不可、人間が目視で判断」の記述を維持
  - L3とL4の振り分け基準を明記する節を追加（L3: スクショ/メトリクスでAI判定可能、L4: 主観的で再現困難）
  - 4層体系（L1 Unit, L2 Integration, L3 E2E, L4 Human Review）が一貫して反映されていることを確認
  - _Requirements: 1.1, 1.3, 1.4_

- [x] 1.2 testing.mdにE2Eテストパターンを文書化する
  - E2Eテストパターン節を新設し、SceneRunnerフルシーン+スクショ+AI視覚評価の基本パターンを記述
  - フィルムストリップパターン（連続スクショによる動作検証）を文書化
  - スクショ戦略テーブル（どのシナリオでどのスクショを撮るかの指針）を追加
  - _Requirements: 9.1, 9.2, 9.3_

- [x] 1.3 (P) tech.mdのテストセクションを4層体系に更新する
  - Layer 3の記述を「E2Eテスト: スクショ+AI視覚評価」に変更
  - Layer 4として「ヒューマンレビュー: 手動検証」を追加
  - L1/L2の記述は変更しない
  - _Requirements: 1.2, 1.3_

- [x] 2. specテンプレートのレイヤー定義を4層体系に更新する
- [x] 2.1 (P) requirementsテンプレートのLayer定義コメントを更新する
  - Layer定義コメントにL3 E2E（スクショ/メトリクス+AI視覚評価で自動検証）を追加
  - 旧Layer 3（Human Review）をLayer 4に変更
  - _Requirements: 2.1_

- [x] 2.2 (P) designテンプレートのTesting Strategyセクションを更新する
  - Layer 3の見出しを「Layer 3: E2E Test」に変更し、E2Eテスト内容を記述
  - Layer 4として「Layer 4: Human Review (Non-Testable)」セクションを追加
  - _Requirements: 2.2_

- [x] 3. タスク生成パイプラインをE2E checkpointに対応させる
- [x] 3.1 (P) タスク生成ルールにL3 E2Eルールを追加する
  - レイヤー順序付けにL3 E2Eルールを追加し、`E2E checkpoint:`パターンを定義
  - 旧L3参照をL4に更新
  - _Requirements: 3.1_

- [x] 3.2 (P) タスクテンプレートにE2E checkpointフォーマット例を追加する
  - `- [ ] X.Y E2E checkpoint: [検証内容]` のフォーマット例を追加
  - _Requirements: 3.2_

- [x] 3.3 (P) spec-tasksコマンドにE2E checkpoint生成ルールを追加する
  - L3 E2E checkpoint生成ルール（テスト作成→xvfb実行→スクショ保存→AI評価のフロー）を追加
  - L3/L4の振り分け基準を追加
  - 旧L3参照をL4に更新
  - _Requirements: 3.3, 3.4_

- [x] 4. 実装パイプラインをE2E checkpointに対応させる
- [x] 4.1 (P) spec-implコマンドにE2E checkpoint実行フローを追加する
  - L3 E2E checkpoint実行フローを追加（テスト作成→xvfb-run実行→スクショ保存→AI視覚評価）
  - ヒューマンレビュー参照をL4に更新
  - _Requirements: 4.1, 4.2_

- [x] 4.2 (P) spec-requirementsコマンドにL3 E2E層の説明を追加する
  - L3 E2Eテスト層の説明を追加
  - 旧L3参照をL4に更新
  - _Requirements: 4.3_

- [x] 5. scene-reviewおよびplan/implementコマンドを更新する
- [x] 5.1 (P) scene-reviewコマンドをL4ヒューマンレビューに再定義する
  - descriptionと本文をL4（ヒューマンレビュー）に更新
  - スクショ自動読み込みモードを追加（E2Eテストで保存されたスクショをReadツールで読み込み評価する機能）
  - _Requirements: 5.1, 5.2_

- [x] 5.2 (P) planコマンドのレイヤー参照を更新する
  - Layer 3の参照を「Layer 3/4」に更新
  - _Requirements: 7.1_

- [x] 5.3 (P) implementコマンドのHuman Review参照を更新する
  - Human Review参照をL4に更新
  - _Requirements: 7.2_

- [x] 6. 既存specのレイヤー参照を新体系に移行する
- [x] 6.1 (P) tick-engine specのレイヤー参照をL3 E2Eに移行する
  - requirements.mdの`Layer 3 (Human Review)`を`Layer 3 (E2E Test)`に変更（性能・応答性はメトリクスで判定可能）
  - design.mdのLayer 3参照をL3 E2Eに更新
  - tasks.mdの`Human review:`を`E2E checkpoint:`に変更（性能メトリクス計測、応答時間計測）
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 6.2 (P) conveyor-belt specのレイヤー参照をL3 E2Eに移行する
  - requirements.mdの`Layer 3 (Human Review)`を`Layer 3 (E2E Test)`に変更（視覚品質はスクショ判定可能）
  - design.mdのLayer 3参照をL3 E2Eに更新
  - tasks.mdの`Human review:`を`E2E checkpoint:`に変更
  - _Requirements: 6.4, 6.5, 6.6_

- [x] 6.3 (P) entity-placement specのレイヤー参照をL4に移行する
  - design.mdのLayer 3参照をL4に更新（完了済みヒューマンレビュー）
  - tasks.mdのLayer参照がある場合はL4ラベルに更新
  - _Requirements: 6.7_

- [x] 6.4 (P) tilemap-core specのレイヤー参照をL4に移行する
  - design.mdのLayer 3参照をL4に更新
  - _Requirements: 6.8_

- [x] 7. インフラ設定を更新し最終検証を実施する
- [x] 7.1 (P) .gitignoreにE2Eテストスクショディレクトリを追加する
  - `godot/test_screenshots/` をignoreパターンに追加
  - _Requirements: 8.1_

- [x] 7.2 全変更完了後にLayer 3参照の一貫性を検証する
  - `grep -r "Layer 3" .kiro/steering/ .kiro/settings/ .claude/commands/` でLayer 3参照を検索し、E2E以外のコンテキストで残っていないことを確認
  - 検出された場合は該当箇所を報告し修正を実施
  - 変更対象20ファイルすべてが更新されていることを確認
  - _Requirements: 10.1, 10.2_
