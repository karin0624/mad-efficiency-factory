# Requirements Document

## Introduction
ベルトコンベアは、機械間のアイテム自動輸送を実現する1x1方向付きの輸送エンティティである。ベルト上のアイテムは順序を保ちながら一定方向に移動し、隣接ベルトや機械ポートへ自動的に転送される。出力先が満杯の場合はバックプレッシャーにより停止し、アイテムの消失や重複を防ぐ。本機能はMVPコアループ「採掘→ベルト輸送→加工→納品」の中核を担う。

## Requirements

### Requirement 1: ベルトタイルのアイテム搬送 (Layer 1)
**Objective:** プレイヤーとして、配置したベルト上でアイテムが自動的に一定速度で進行してほしい。これにより手動操作なしで機械間のアイテム輸送が実現される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The BeltTransportSystem shall アイテムをベルトの向き方向に1秒あたり1タイルの速度で進行させる
2. The BeltTransportSystem shall 1つのベルトタイルに最大1個のアイテムのみ保持する
3. When ベルトタイルにアイテムが配置された, the BeltTransportSystem shall そのアイテムをベルトの向き方向へ搬送速度に従って移動させる
4. The BeltTransportSystem shall ベルトの向きとして北・東・南・西の4方向をサポートする

### Requirement 2: 隣接ベルト間の転送 (Layer 1)
**Objective:** プレイヤーとして、連続配置したベルト間でアイテムが自動的に転送されてほしい。これによりベルトチェーンによる長距離輸送が可能になる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When アイテムがベルト末端に到達した, the BeltTransportSystem shall ベルトの向き方向に隣接する受信可能なベルトへ正確に1回転送する
2. If 転送先のベルトが存在しない, the BeltTransportSystem shall アイテムをベルト末端で待機させる
3. If 転送先のベルトが既にアイテムを保持している, the BeltTransportSystem shall アイテムをベルト末端で待機させる
4. The BeltTransportSystem shall ベルトの向きと合致しない方向への転送を行わない（例: 東向きベルトは北の隣接ベルトへ転送しない）
5. When 直線状に5本以上のベルトを配置し一端にアイテムを投入した, the BeltTransportSystem shall 他端まで順序を保って自動輸送する
6. When L字やU字に曲がるベルト配置でアイテムを投入した, the BeltTransportSystem shall アイテムを消失・重複なく輸送する

### Requirement 3: バックプレッシャー (Layer 1)
**Objective:** プレイヤーとして、出力先が満杯の場合にアイテムが消失せず安全に停止してほしい。これによりアイテムの保存則が保証される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. While 出力先（隣接ベルトまたは機械入力ポート）が満杯である, the BeltTransportSystem shall ベルト末端のアイテムを停止させる
2. When ベルト末端のアイテムが停止した, the BeltTransportSystem shall 後続のアイテムも連鎖的に停止させる（圧力の逆伝播）
3. When 出力先に空きが生じた, the BeltTransportSystem shall 停止していたアイテムの進行を自動的に再開させる
4. While バックプレッシャーが発生している, the BeltTransportSystem shall すべてのアイテムを保存する（消失・重複なし）

### Requirement 4: 機械ポートとの入出力 (Layer 1)
**Objective:** プレイヤーとして、ベルトが機械の入出力ポートと自動的にアイテムをやり取りしてほしい。これにより採掘→加工→納品の自動化ラインが構築できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 機械の出力ポートにアイテムが準備された, the BeltTransportSystem shall 出力ポートに隣接する空きベルトへアイテムを転送する
2. When ベルト末端のアイテムが機械の入力ポートに隣接している, the BeltTransportSystem shall 入力ポートが受入可能な場合にアイテムを引き渡す
3. If 機械の入力ポートが満杯である, the BeltTransportSystem shall アイテムをベルト上に保持し、バックプレッシャーを適用する
4. If 出力ポートに隣接するベルトが満杯である, the BeltTransportSystem shall 機械出力ポートからの転送を行わない

### Requirement 5: ベルト接続関係の更新 (Layer 1)
**Objective:** プレイヤーとして、ベルトや機械の配置・撤去後に転送関係が自動的に更新されてほしい。これにより工場レイアウトの動的な変更が可能になる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 隣接するベルトまたは機械が配置された, the BeltTransportSystem shall 次回のシミュレーション更新までに新しい転送関係を反映する
2. When 隣接するベルトまたは機械が撤去された, the BeltTransportSystem shall 次回のシミュレーション更新までに転送関係を更新する
3. While 配置・撤去が発生していない, the BeltTransportSystem shall 転送関係を変化させない
4. When ベルトが撤去された, the BeltTransportSystem shall そのベルト上のアイテムを消失させる（MVPではドロップやインベントリ返却は行わない）

### Requirement 6: アイテム順序の保証（FIFO） (Layer 1)
**Objective:** プレイヤーとして、ベルトチェーンに投入した順序でアイテムが出力されてほしい。これにより予測可能な生産ラインの設計が可能になる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The BeltTransportSystem shall ベルトチェーンに投入された順序でアイテムを出力する（FIFO）
2. The BeltTransportSystem shall アイテムが占有中の中間ベルトを飛び越えないことを保証する
3. When 複数のアイテムが同一ベルトチェーン上にある, the BeltTransportSystem shall 先行アイテムが後続アイテムより先に出力されることを保証する

### Requirement 7: アイテム保存則 (Layer 1)
**Objective:** プレイヤーとして、ベルトシステム内でアイテムが消失・重複しないことを保証してほしい。これにより工場の物流が信頼できるものになる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The BeltTransportSystem shall ベルトシステム内のアイテム総数を常に保存する（入力アイテム数 = 出力アイテム数 + ベルト上残存数）
2. When アイテムが転送される, the BeltTransportSystem shall 転送元から正確に1個を除去し転送先に正確に1個を追加する
3. The BeltTransportSystem shall いかなる状態でもアイテムの重複生成を行わない

### Requirement 8: パフォーマンス要件 (Layer 2)
**Objective:** プレイヤーとして、大量のベルトとアイテムが存在する状態でもスムーズなゲームプレイを体験したい。これにより大規模工場の構築が実用的になる。
**Testability:** Layer 2 (Range-Testable)

#### Acceptance Criteria
1. While ベルト500本とアイテム2000個が存在する状態で, the BeltTransportSystem shall 1ティックあたりの処理時間を16ms以下に維持する
2. The BeltTransportSystem shall 64x64グリッド内で動作する

#### Non-Testable Aspects
- 実際のハードウェア環境によりパフォーマンス数値は変動する
- レビュー方法: CI環境（xvfb-run CLIモード）でのティック処理時間計測ベンチマークテスト
- 受け入れ閾値: 計測環境において1ティックあたり16ms以下を安定的に達成すること

### Requirement 9: ベルト上アイテムの視覚表現 (Layer 3)
**Objective:** プレイヤーとして、ベルト上のアイテム移動が視覚的に滑らかで分かりやすく表示されてほしい。これにより工場の稼働状況を直感的に把握できる。
**Testability:** Layer 3 (Human Review)

#### Acceptance Criteria
1. The BeltVisualSystem shall ベルト上のアイテムをベルトの向き方向に視覚的に移動表示する
2. While バックプレッシャーが発生している, the BeltVisualSystem shall アイテムの停止状態を視覚的に表現する

#### Non-Testable Aspects
- ベルト上のアイテム移動の視覚的な滑らかさ
- バックプレッシャー発生時の視覚的フィードバックの分かりやすさ
- 大量ベルト配置時（500本以上）の描画パフォーマンス
- レビュー方法: 開発者がゲーム実行中にベルトチェーン上のアイテム移動を目視確認
- 受け入れ閾値: アイテムの移動がカクつかず滑らかに見えること、停止と移動の状態が視覚的に区別できること
