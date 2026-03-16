# Requirements Document

## Introduction

Entity Placement（配置・撤去システム）は、プレイヤーがグリッド上に機械やベルトなどのエンティティを配置・撤去できるようにする機能である。配置前にゴーストプレビューで配置可否を視覚的にフィードバックし、フットプリント検証と回転対応により正確な工場レイアウト構築を実現する。

対象エンティティ（MVP）: Miner(2x2), Smelter(2x2), Belt(1x1), DeliveryBox(1x1)。配置対象領域は64x64セルのグリッドとする。

## Requirements

### Requirement 1: エンティティ配置
**Objective:** プレイヤーとして、グリッド上の指定座標にエンティティを配置できるようにしたい。それにより工場レイアウトを自由に構築できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When プレイヤーがエンティティ種別と基準セル座標を指定して配置操作を行う, the PlacementSystem shall フットプリント全体が空きかつグリッド範囲内であることを検証し、検証成功時にエンティティを配置する
2. When エンティティが配置される, the PlacementSystem shall フットプリントが占有する全セルの占有状態を一括で更新する
3. When 2x2フットプリントのエンティティ（Miner, Smelter）が基準セル(x, y)に配置される, the PlacementSystem shall (x,y), (x+1,y), (x,y+1), (x+1,y+1)の4セルすべてを占有状態に設定する
4. When 1x1フットプリントのエンティティ（Belt, DeliveryBox）が基準セル(x, y)に配置される, the PlacementSystem shall (x,y)の1セルを占有状態に設定する
5. The PlacementSystem shall 配置操作を即座に完了する（建設時間やアニメーション待ちを発生させない）

### Requirement 2: 配置検証
**Objective:** プレイヤーとして、無効な配置（重複・範囲外）が拒否されるようにしたい。それにより不整合のない工場レイアウトが保証される。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. If フットプリント内のいずれかのセルが既に占有されている, the PlacementSystem shall 配置を拒否し、グリッド状態を変更しない
2. If フットプリント内のいずれかのセルがグリッド範囲（64x64）外にある, the PlacementSystem shall 配置を拒否し、グリッド状態を変更しない
3. If 配置が拒否される, the PlacementSystem shall 部分的な配置を発生させない（一部セルのみ占有された状態にならない）
4. When 基準セル(63, 63)に2x2エンティティの配置が試みられる, the PlacementSystem shall フットプリントがグリッド範囲を超えるため配置を拒否する
5. When 基準セル(0, 0)に1x1エンティティの配置が試みられ、そのセルが空きの場合, the PlacementSystem shall 配置を許可する

### Requirement 3: エンティティ回転
**Objective:** プレイヤーとして、配置確定前にエンティティの向きを変更できるようにしたい。それにより後続機能（ポート方向等）に必要な方向制御ができる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When プレイヤーが回転操作を行う, the PlacementSystem shall 選択中エンティティの向きを北→東→南→西→北の順で切り替える
2. The PlacementSystem shall 回転方向として北・東・南・西の4方向のみをサポートする
3. When エンティティが特定の回転方向で配置される, the PlacementSystem shall 配置済みエンティティにその回転方向を保持する
4. While MVPのエンティティはすべて正方形フットプリントである, the PlacementSystem shall 回転によって占有領域を変化させない

### Requirement 4: エンティティ撤去
**Objective:** プレイヤーとして、配置済みエンティティを撤去できるようにしたい。それにより工場レイアウトを自由に変更できる。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When プレイヤーがセルを指定して撤去操作を行う, the PlacementSystem shall そのセルを占有しているエンティティを特定し撤去する
2. When 複数セルを占有するエンティティ（2x2）のいずれか1セルが指定される, the PlacementSystem shall 当該エンティティ全体を撤去する
3. When エンティティが撤去される, the PlacementSystem shall そのエンティティが占有していた全セルを一括で未占有に戻す
4. If 指定されたセルにエンティティが存在しない, the PlacementSystem shall 撤去操作を無視し、グリッド状態を変更しない
5. The PlacementSystem shall 配置済みエンティティをいつでも撤去可能にする（撤去不可の状態を持たない）
6. When 撤去が完了する, the PlacementSystem shall 撤去操作を即座に完了する（アニメーション待ちを発生させない）

### Requirement 5: ゴーストプレビュー表示
**Objective:** プレイヤーとして、配置確定前にエンティティの配置予定位置と配置可否を視覚的に確認できるようにしたい。それにより配置ミスを事前に防止できる。
**Testability:** Layer 2 (Range-Testable)

#### Acceptance Criteria
1. While プレイヤーがエンティティ種別を選択中である, the PlacementSystem shall 配置予定位置にゴースト（半透明）プレビューを表示する
2. When 配置予定位置が有効（フットプリント全体が空きかつ範囲内）である, the PlacementSystem shall ゴーストを緑色で表示する
3. When 配置予定位置が無効（占有済みセルまたは範囲外を含む）である, the PlacementSystem shall ゴーストを赤色で表示する
4. When プレイヤーが対象セルを変更する, the PlacementSystem shall ゴースト表示を新しい対象セルへ更新する

#### Non-Testable Aspects
- ゴーストの半透明度が視覚的に適切か（見やすさと背景の視認性のバランス）
  - レビュー方法: 配置操作中のスクリーンショットを取得し、ゴーストが背景グリッドと区別可能かを目視確認
  - 受け入れ閾値: ゴーストと背景が明確に区別でき、配置予定位置が一目で分かること
- ゴースト表示の更新が体感遅延なく追従するか
  - レビュー方法: マウス移動中にゴーストの追従をリアルタイムで確認
  - 受け入れ閾値: 体感的な遅延がなく、入力に対して即座にゴーストが移動すること

### Requirement 6: 配置・撤去の原子性
**Objective:** システムとして、配置・撤去操作が常に一貫した状態遷移を保証するようにしたい。それによりグリッドの占有状態が不整合にならない。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The PlacementSystem shall 配置操作において、フットプリント全セルの占有更新を一括で実行する（一部セルのみ更新された中間状態を生じさせない）
2. The PlacementSystem shall 撤去操作において、対象エンティティの全占有セルの解放を一括で実行する
3. If 配置検証が失敗した場合, the PlacementSystem shall グリッド状態を一切変更しない

### Requirement 7: エンティティ定義の参照
**Objective:** システムとして、MVPで配置可能なエンティティの種別とフットプリントを正しく参照できるようにしたい。それにより配置検証が正確に動作する。
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The PlacementSystem shall Minerのフットプリントを2x2として扱う
2. The PlacementSystem shall Smelterのフットプリントを2x2として扱う
3. The PlacementSystem shall Beltのフットプリントを1x1として扱う
4. The PlacementSystem shall DeliveryBoxのフットプリントを1x1として扱う
5. The PlacementSystem shall 矩形フットプリントのみをサポートする（L字型等の不規則形状は対象外）
