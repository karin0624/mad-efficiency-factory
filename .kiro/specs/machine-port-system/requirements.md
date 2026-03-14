# Requirements Document

## Introduction
機械入出力ポートシステムは、全機械タイプ（採掘機・精錬機・納品箱）に共通のポート仕様を提供し、隣接ベルトとのアイテム自動受け渡しを実現する機能である。機械の配置時にタイプに応じたポートが決定され、回転に追従し、隣接するベルトとの空間的な接続条件を満たす場合にアイテムが自動転送される。出力先や入力元が満杯の場合はバックプレッシャーにより転送を停止し、空きが生じると自動再開する。本機能はMVPコアループ「採掘→ベルト輸送→加工→納品」における機械-ベルト間の接続を担う。

## Requirements

### Requirement 1: ポート定義と回転 (Layer 1)
**Objective:** プレイヤーとして、機械を配置・回転させたときにポートの位置と方向が自動的に決定・更新されてほしい。これにより機械の向きを変えるだけで入出力方向を自由に調整できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 機械が配置された, the MachinePortSystem shall その機械タイプに応じた入力ポートおよび出力ポートの位置と方向を決定する
2. The MachinePortSystem shall 以下のMVP機械タイプのポート構成をサポートする: 採掘機（出力ポート1つ）、精錬機（入力ポート1つ・出力ポート1つ）、納品箱（入力ポート1つ）
3. When プレイヤーが機械を回転させた, the MachinePortSystem shall ポートの方向を回転に追従させて更新する
4. The MachinePortSystem shall 4方向（北・東・南・西）すべてのポート回転で一貫した振る舞いを保証する
5. The MachinePortSystem shall ポート位置を機械定義で静的に決定し、実行時に動的変更しない

### Requirement 2: ポート接続解決 (Layer 1)
**Objective:** プレイヤーとして、機械とベルトを隣接配置するだけで自動的に接続が成立してほしい。これにより明示的なリンク設定なしで工場ラインを構築できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 機械ポートとベルトが直交方向に隣接し、かつ転送方向が互換である, the MachinePortSystem shall 両者の接続を成立させる
2. If 機械ポートとベルトが隣接していない, the MachinePortSystem shall 接続を成立させない
3. If 機械ポートとベルトの転送方向が互換でない, the MachinePortSystem shall 接続を成立させない
4. The MachinePortSystem shall 接続解決を空間的隣接関係のみで行い、プレイヤーによる明示的リンク操作を不要とする

### Requirement 3: 出力ポートからベルトへの転送 (Layer 1)
**Objective:** プレイヤーとして、機械の出力ポートからアイテムが隣接ベルトへ自動的に押し出されてほしい。これにより機械の生産物がベルトネットワークに自動投入される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 出力ポートにアイテムが準備され、隣接ベルトに空きがある, the MachinePortSystem shall アイテムを出力ポートから隣接ベルトへ転送する
2. If 出力ポートに隣接するベルトが満杯である, the MachinePortSystem shall 出力ポートからの転送を行わず、アイテムを出力ポートに保持する
3. If 出力ポートに接続されたベルトが存在しない, the MachinePortSystem shall アイテムを出力ポートに保持する
4. The MachinePortSystem shall 1つのポートに同時に最大1個のアイテムのみバッファする

### Requirement 4: ベルトから入力ポートへの引き込み (Layer 1)
**Objective:** プレイヤーとして、隣接ベルト上のアイテムが機械の入力ポートへ自動的に引き込まれてほしい。これにより原材料の供給が自動化される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 入力ポートが空で、隣接ベルト上にアイテムがある, the MachinePortSystem shall ベルトからアイテムを入力ポートへ引き込む
2. If 入力ポートが既にアイテムを保持している, the MachinePortSystem shall ベルトからの引き込みを行わない
3. If 入力ポートに接続されたベルトが存在しない, the MachinePortSystem shall 引き込みを行わない
4. The MachinePortSystem shall 1つのポートに同時に最大1個のアイテムのみバッファする

### Requirement 5: バックプレッシャー (Layer 1)
**Objective:** プレイヤーとして、受け入れ先が満杯の場合にアイテムが消失せず安全に停止し、空きが生じたら自動再開してほしい。これによりアイテムの保存則が保証される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. While 入力ポートが満杯である, the MachinePortSystem shall 隣接ベルトからのアイテム引き込みを停止する
2. While 出力先ベルトが満杯である, the MachinePortSystem shall 出力ポートからのアイテム転送を停止する
3. When 入力ポートのアイテムが消費され空きが生じた, the MachinePortSystem shall 隣接ベルトからの引き込みを自動的に再開する
4. When 出力先ベルトに空きが生じた, the MachinePortSystem shall 出力ポートからの転送を自動的に再開する
5. While バックプレッシャーが発生している, the MachinePortSystem shall すべてのアイテムを保存する（消失・重複なし）

### Requirement 6: ポート接続の動的更新 (Layer 1)
**Objective:** プレイヤーとして、機械やベルトを配置・撤去した後にポート接続が自動的に更新されてほしい。これにより工場レイアウトの動的な変更が可能になる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 機械またはベルトが新たに配置された, the MachinePortSystem shall 影響を受けるポート接続関係を次回のシミュレーション更新までに再評価する
2. When 機械またはベルトが撤去された, the MachinePortSystem shall 影響を受けるポート接続関係を次回のシミュレーション更新までに再評価する
3. When 機械が撤去された, the MachinePortSystem shall その機械のポートからの転送を即座に停止する
4. While 配置・撤去が発生していない, the MachinePortSystem shall ポート接続関係を変化させない

### Requirement 7: アイテム保存則 (Layer 1)
**Objective:** プレイヤーとして、ポート転送においてアイテムが消失・重複しないことを保証してほしい。これにより工場の物流が信頼できるものになる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When アイテムが出力ポートからベルトへ転送される, the MachinePortSystem shall 出力ポートから正確に1個を除去しベルトに正確に1個を追加する
2. When アイテムがベルトから入力ポートへ引き込まれる, the MachinePortSystem shall ベルトから正確に1個を除去し入力ポートに正確に1個を追加する
3. The MachinePortSystem shall いかなる状態でもアイテムの重複生成を行わない
4. The MachinePortSystem shall いかなる状態でもアイテムの消失を発生させない（撤去による消失はスコープ外 — ベルトspecで定義）

### Requirement 8: E2E統合フロー (Layer 2)
**Objective:** プレイヤーとして、出力ポート付き機械→ベルト→入力ポート付き機械の構成でアイテムが正しく流れることを確認したい。これによりMVPコアループの機械-ベルト接続が検証される。
**Testability:** Layer 2 (Range-Testable)

#### Acceptance Criteria
1. When 出力ポート付き機械、ベルト5本、入力ポート付き機械を直線配置した, the MachinePortSystem shall 出力ポートに投入されたアイテムが入力ポートに到達することを保証する
2. The MachinePortSystem shall 投入アイテム数と受取アイテム数が一致することを保証する
3. When 出力ポート付き機械を4方向それぞれに回転配置した, the MachinePortSystem shall すべての向きでベルトへの転送が正常に動作する

#### Non-Testable Aspects
- ティック処理タイミングによる微小な転送遅延の変動
- レビュー方法: ベルト5本を介した出力→入力フローの自動テストで、投入数と受取数の一致を検証
- 受け入れ閾値: 100アイテム投入で100アイテム受取（誤差0）
