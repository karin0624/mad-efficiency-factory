# Requirements Document

## Introduction
テストレイヤー体系を再定義し、L3にE2Eテスト層（SceneRunner+スクショ+AI視覚評価）を新設する。旧L3（ヒューマンレビュー）はL4に移行する。ステアリングドキュメント、specテンプレート、コマンド定義、既存specファイルを一貫して更新し、新レイヤー体系をプロジェクト全体に反映する。

## Requirements

### Requirement 1: レイヤー体系の再定義
**Objective:** 開発者として、テストレイヤー体系にL3 E2E層を追加しL4にヒューマンレビューを移行したい。これにより、スクショやメトリクスで自動判定可能な検証をAIに委ね、人的レビューコストを削減できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The steering document (`testing.md`) shall L3 E2Eテスト層の定義（手法: SceneRunner フルシーン+スクショ/メトリクス+AI視覚評価、決定性: 非決定的(AI)、実行者: spec-impl）を含むこと
2. The steering document (`tech.md`) shall Layer 3の記述を「E2Eテスト: スクショ+AI視覚評価」に更新し、Layer 4として「ヒューマンレビュー: 手動検証」を追加すること
3. When レイヤー体系を参照する場合, the steering documents shall L1(Unit Test), L2(Integration Test), L3(E2E Test), L4(Human Review)の4層構成を反映すること
4. The steering document (`testing.md`) shall L3とL4の振り分け基準を明記すること — L3はスクショまたはメトリクスでAI判定可能な項目、L4は主観的で再現困難な項目

### Requirement 2: specテンプレートの更新
**Objective:** 開発者として、specテンプレートが新しい4層レイヤー体系を反映するようにしたい。今後の新規spec生成時に正しいレイヤー定義が自動的に適用されるようにする。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The requirements template shall Layer定義コメントにL3 E2E（スクショ/メトリクス+AI視覚評価で自動検証）を含み、旧Layer 3をLayer 4（ヒューマンレビュー）に更新すること
2. The design template shall テスタビリティ分類にLayer 3: E2E TestとLayer 4: Human Reviewの両方を含むこと

### Requirement 3: タスク生成パイプラインの更新
**Objective:** 開発者として、タスク生成時にE2E checkpointパターンが正しく生成されるようにしたい。L3タスクがE2E自動検証用のチェックポイントとして適切にフォーマットされるようにする。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The tasks generation rules shall L3 E2Eルールを含み、`E2E checkpoint:`パターンをサポートすること
2. The tasks template shall E2E checkpointのフォーマット例を含むこと
3. The spec-tasks command shall L3 E2E checkpoint生成ルールとL3/L4の振り分け基準を含むこと
4. When タスクにE2E checkpointが指定された場合, the spec-tasks command shall テスト作成・実行・AI評価のフローを記述すること

### Requirement 4: 実装パイプラインのE2E対応
**Objective:** 開発者として、spec-implコマンドがE2E checkpointを検出し自動実行できるようにしたい。テスト作成からAI評価までの一連のフローが定義されることで、E2Eテストの実装手順が標準化される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The spec-impl command shall L3 E2E checkpoint実行フローを含むこと（テスト作成→xvfb実行→スクショ保存→AI評価）
2. The spec-impl command shall ヒューマンレビュー参照をL4に更新すること
3. The spec-requirements command shall L3 E2E層の説明を含み、旧L3参照をL4に更新すること

### Requirement 5: scene-reviewコマンドのL4対応
**Objective:** 開発者として、scene-reviewコマンドがL4（ヒューマンレビュー）として正しく位置付けられるようにしたい。E2Eテストで判定不能な場合のフォールバック先として機能する。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The scene-review command shall descriptionと本文をL4（ヒューマンレビュー）に更新すること
2. The scene-review command shall スクショ自動読み込みモードを含むこと（E2Eテストで保存されたスクショを活用）

### Requirement 6: 既存specの移行
**Objective:** 開発者として、既存specファイルのレイヤー参照が新体系に統一されるようにしたい。すべてのspecが一貫したレイヤー命名を使用することで混乱を防止する。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The tick-engine spec shall requirements.mdのLayer 3参照を「Layer 3 (E2E Test)」に更新すること（性能・応答性はメトリクスで判定可能なため）
2. The tick-engine spec shall design.mdのLayer 3参照をL3 E2Eに更新すること
3. The tick-engine spec shall tasks.mdの`Human review:`をE2E checkpointに変更すること（性能メトリクス計測、応答時間計測）
4. The conveyor-belt spec shall requirements.mdのLayer 3参照を「Layer 3 (E2E Test)」に更新すること（視覚品質はスクショ判定可能なため）
5. The conveyor-belt spec shall design.mdのLayer 3参照をL3 E2Eに更新すること
6. The conveyor-belt spec shall tasks.mdの`Human review:`をE2E checkpointに変更すること
7. The entity-placement spec shall design.mdのLayer 3参照をL4に更新すること（完了済みヒューマンレビュー）
8. The tilemap-core spec shall design.mdのLayer 3参照をL4に更新すること

### Requirement 7: planおよびimplementコマンドの更新
**Objective:** 開発者として、planコマンドとimplementコマンドのレイヤー参照が新体系を反映するようにしたい。コマンド間でレイヤー命名が統一される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The plan command shall Layer 3の参照を「Layer 3/4」に更新すること
2. The implement command shall Human Review参照をL4に更新すること

### Requirement 8: インフラ設定の更新
**Objective:** 開発者として、E2Eテストで生成されるスクショファイルがGit管理から除外されるようにしたい。テスト成果物がリポジトリを肥大化させることを防止する。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The `.gitignore` file shall `godot/test_screenshots/` をignoreパターンに含むこと

### Requirement 9: E2Eテストパターンの文書化
**Objective:** 開発者として、E2Eテストの実装パターンがsteeringドキュメントに文書化されるようにしたい。フィルムストリップパターンやスクショ戦略が標準化されることで、一貫したE2Eテスト実装が可能になる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The steering document (`testing.md`) shall E2Eテストパターン節を含むこと
2. The steering document (`testing.md`) shall フィルムストリップパターン（連続スクショによる動作検証）を文書化すること
3. The steering document (`testing.md`) shall スクショ戦略テーブル（どのシナリオでどのスクショを撮るかの指針）を含むこと

### Requirement 10: レイヤー参照の一貫性検証
**Objective:** 開発者として、変更完了後にLayer 3がE2E以外のコンテキストで残っていないことを検証したい。レイヤー参照の不整合を防止する。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When すべての変更が完了した場合, the steering documents, settings, and commands shall Layer 3の参照がE2Eテストのコンテキストでのみ使用されていること
2. If Layer 3がE2E以外の文脈で検出された場合, the verification process shall その箇所を報告し修正を促すこと
