# Implementation Plan

- [x] 1. TickClock コアロジック — 固定レートティック発火と蓄積時間管理
- [x] 1.1 TickClock 固定レート発火のテストを作成する
  - ティック間隔（16667μs）ちょうどの入力で1ティック発火することを検証するテスト
  - ティック間隔の2倍（33334μs）の入力で2ティック発火することを検証するテスト
  - ティック間隔未満（10000μs）の入力でティックが発火しないことを検証するテスト
  - 端数繰り越しの検証: 20000μs入力で1ティック発火し、残りの蓄積時間が3333μsであること
  - 連続フレームでの蓄積と発火: 10000μs × 2回で1ティック発火し、残り3333μs
  - 初期ティックカウントが0であることの検証
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.4, 6.1_

- [x] 1.2 TickClock の基本構造と固定レート発火ロジックを実装する
  - RefCountedを継承した純粋ロジッククラスとして作成
  - 定数: TICK_INTERVAL_USEC = 16667、MAX_TICKS_PER_FRAME = 5
  - 内部状態: _accumulator_usec（int）、current_tick（int、初期値0）、is_paused（bool、初期値false）
  - advance(delta_usec: int) -> int メソッド: 蓄積時間にdelta_usecを加算し、ティック間隔ごとに発火回数をカウントして返す
  - 蓄積時間からティック間隔分を減算し、端数を次フレームに繰り越す
  - delta_usec < 0の場合のassertガード
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 6.1_

- [x] 1.3 TickClock ティックカウント管理のテストを作成する
  - advance()呼び出しごとにcurrent_tickが発火数分だけ正確に増加することの検証
  - 単調増加の検証: 複数回のadvance()で減少しないこと
  - current_tickが外部から読み取り可能であることの検証
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 1.4 TickClock キャッチアップ制限のテストを作成する
  - 100000μs（100ms、6ティック相当）入力で5ティックのみ発火することの検証
  - キャッチアップ上限到達後に蓄積時間が0にリセットされることの検証
  - 200000μs（200ms、12ティック相当）でも5ティック上限が適用されることの検証
  - 上限到達直後の次フレームで正常にティック発火が再開することの検証
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 1.5 TickClock にキャッチアップ制限ロジックを実装する
  - advance()内のループに発火回数カウンタを追加し、MAX_TICKS_PER_FRAME到達でループを終了
  - 上限到達時に蓄積時間を0にリセットして超過分を完全破棄
  - _Requirements: 3.1, 3.2, 3.3, 8.1, 8.2_

- [x] 2. TickClock 一時停止・再開と決定性
- [x] 2.1 TickClock 一時停止・再開のテストを作成する
  - pause()後のadvance()で0ティック発火し、ティックカウントが変更されないことの検証
  - 一時停止中に大量のdelta_usec（例: 1000000μs）を与えてもティックが発火しないことの検証
  - resume()後に蓄積時間が0にリセットされることの検証
  - resume()後の最初のadvance()で正常にティック発火が再開することの検証
  - resume()後に大量のキャッチアップが発生しないことの検証（蓄積時間リセットにより保証）
  - pause()の冪等性: 既にpause中のpause()呼び出しが安全に処理されること
  - resume()の冪等性: 既にrunning中のresume()呼び出しが安全に処理されること（accumulatorリセットのみ再実行）
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 2.2 TickClock に一時停止・再開ロジックを実装する
  - pause()メソッド: is_pausedをtrueに設定
  - resume()メソッド: is_pausedをfalse、_accumulator_usecを0にリセット
  - advance()内でis_paused判定を追加: trueの場合は蓄積もせず即座に0を返す
  - reset()メソッド: current_tick, _accumulator_usec, is_pausedを全て初期値にリセット
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 2.3 TickClock 決定性のテストを作成する
  - 同一のdelta_usecシーケンス（例: [16667, 8000, 25000, 16667, 100000]）を2回実行し、ティック発火パターンとcurrent_tickが完全一致することの検証
  - 整数演算による累積誤差なしの検証: 16667μs × 60回で正確に60ティック発火すること
  - pause/resume を含むシーケンスでの再現性検証
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 2.4 TickClock フレームレート非依存性のテストを作成する
  - 120fps相当のdeltaシーケンス（8333μs × 120回）で60ティック発火することの検証
  - 60fps相当のdeltaシーケンス（16667μs × 60回）で60ティック発火することの検証
  - 30fps相当のdeltaシーケンス（33333μs × 30回）で60ティック発火することの検証
  - 異なるフレームレートで同一の実時間に対して同一のティック数が発火することの比較検証
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 3. TickEngineNode — Godotブリッジの実装とインテグレーション
- [x] 3.1 TickEngineNode のシグナル発行テストを作成する（L2）
  - ティック発火時にtick_firedシグナルが正しいtick値で発行されることの検証
  - ティック非発火フレーム（蓄積時間がティック間隔未満）でシグナルが発行されないことの検証
  - 1フレーム内で複数ティック発火時にシグナルがtick昇順で発行されることの検証
  - delta（float秒）→μs（int）変換の精度検証
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.2, 6.3_

- [x] 3.2 TickEngineNode を実装する
  - Nodeを継承したブリッジクラスとして作成
  - _ready()でTickClockインスタンスを生成・初期化
  - tick_fired(tick: int)シグナルを定義
  - _physics_process(delta)でdelta→μs変換（int(delta * 1_000_000)）を行い、clock.advance()を呼び出す
  - advance()の戻り値（発火数）に応じてtick_firedシグナルを発火数分発行（tick昇順）
  - 発火数が0の場合はシグナルを発行しない
  - clockプロパティを公開して外部からTickClockへの参照を提供
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.2, 6.3_

- [x] 3.3 (P) TickEngineNode シグナル発行のスクリーンショット検証
  - [x] 3.3 Screenshot checkpoint: TickEngineNodeをシーンに追加し、tick_firedシグナルの接続先でprint出力してコンソールログを確認する
  - _Requirements: 6.2, 6.3_

- [ ] 4. 高負荷時の安定性 — E2E自動検証
- [ ] 4.1 高負荷環境でのティック動作のE2E検証
  - [ ] 4.1 E2E checkpoint: ベルト500本+アイテム2000個の状態でFPSメトリクスを計測する。ゲーム実行中にFPS値をprint出力し、AIが30FPS以上であることを確認する
  - _Requirements: 8.1, 8.2_

- [ ] 4.2 一時停止・再開の応答時間のE2E検証
  - [ ] 4.2 E2E checkpoint: pause/resumeの呼び出し前後でタイムスタンプを計測し応答時間をprint出力する。AIが100ms以下であることを確認する
  - _Requirements: 4.1, 4.4, 8.2_
