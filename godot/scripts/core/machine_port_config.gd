class_name MachinePortConfig
extends Resource

## MachinePortConfig — 機械タイプごとのポート構成データ定義
##
## 機械タイプに紐づく入力/出力ポートの北基準定義を保持する。
## イミュータブル — 実行時に変更しない。
## 各ポートは local_offset（Vector2i）と local_direction（int）を持つ Dictionary で表現する。
## SceneTree/Node APIに依存しない純粋なデータクラス。

## EntityDefinition.entity_type_id と対応
var machine_type_id: int

## 入力ポート定義の配列（Array of {local_offset: Vector2i, local_direction: int}）
var input_ports: Array = []

## 出力ポート定義の配列（Array of {local_offset: Vector2i, local_direction: int}）
var output_ports: Array = []

## フットプリントサイズ（回転計算に必要）
var machine_size: Vector2i
