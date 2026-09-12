# シミュレーション高速化（2026-09-13）

## 現在のプロジェクト

KaggleのKaggriculture農業対戦AIを開発するワークスペース。公開リプレイの
収集・分析、候補戦略の探索、複数の対戦相手との両席評価、提出物の作成を扱う。

- `main.py`: 現在の提出用AI。保存された行動列を再生するChassisに、観測に応じた
  市場注文・雇用・作業者行動の補正と、終盤の物理シミュレーションを重ねている。
- `training/fast_kaggriculture.py`: 公式インタプリタを直接呼び出す対戦ランナー。
  スキーマ検証や全リプレイ保存などを省き、初期環境と市場価格をキャッシュする。
- `training/search_*.py`: 戦略パラメータ、行動スケジュール、序盤の市場注文などを探索。
- `scripts/evaluate_test_models.py`: `test/<model>/main.py` の相手と固定seed・両席で対戦。
  相手のモジュール状態が試合をまたがないよう、各試合でAIを読み込み直す。
- `scripts/collect_*.py` / `analyze_*.py`: 公開・ローカル対戦の収集と分析。
- `Makefile`: ローカル実行と `kag-server` 上の探索・評価をつなぐ。

READMEのJuly baselineやPPOに関する記述は過去の構成も含む。今回の計測対象は
現在の `main.py` と public_v31 / public_v35 / public_v36 / public_v37。
公式環境はインストール済みの `kaggle-environments==1.32.7`。

## 計測から選んだ変更

変更前の1対戦のcProfileでは約495万回の関数呼び出し。`deepcopy` は累積約0.25秒、
公式インタプリタは約0.15秒だった（プロファイラ込みの約1.24秒なので、実測の
対戦時間とは別）。現在はルール処理だけでなく、AI内部のコピーが目立つ。

1. **行動だけを構造に沿ってコピーする。** Farmer命令、各hand命令、各market命令を
   それぞれ複製する `_copy_action` を追加。命令の引数は不変のスカラーなので、
   全要素を汎用 `deepcopy` でたどる必要がない。その他のメタデータ、観測、
   プランナーの状態には必要な深いコピーを残した。
2. **フォールバック用コピーを例外時に行う。** Chassisが正常に動く毎ターンの
   予備コピーを省略。補正レイヤーが失敗したときは元の行動列から再取得する。
3. **盤面走査と隣接判定の小さな繰り返しを削減する。** 作物の腐敗処理では行を
   一度取り出して走査する。倉庫に隣接する4マスは盤面サイズ別の不変集合を
   キャッシュする。腐敗条件・更新順序は公式と同じ。

高速ランナーの置き換えは専用globals内に閉じ、同じプロセスで使う公式ランナーを
変更しない。対戦相手のファイル、戦略パラメータ、提出アーカイブは変更していない。
既存の未コミット変更を含む作業開始時点を基準にした今回分だけの差分を
[simulation_speedup_20260913.patch](simulation_speedup_20260913.patch) に保存した。

## 性能

ローカルMac / ARM64 / Python 3.12.13、単一プロセス。
4相手 × 2 seeds × 両席 = 16対戦を3回、各版48対戦。
同じ対戦を旧版・新版で交互に実行し、反復ごとに測定順も反転した。
AIは毎試合新しく読み込む。1試合のウォームアップを除外した。

| 対戦処理の測定 | 変更前 | 変更後 |
|---|---:|---:|
| 48対戦の合計時間 | 17.611秒 | 15.957秒 |
| 対戦数/秒 | 2.726 | 3.008 |
| 1対戦の中央値 | 0.358秒 | 0.325秒 |

**スループット1.104倍（+10.36%）、処理時間−9.39%。**
3反復それぞれの倍率は1.084 / 1.112 / 1.115。

この表はAIのimport、対戦前のGC、ウォームアップを除外した対戦処理の計測。
プレイ中のGCは有効。最初の測定では以前のAIモジュールの循環参照回収が次の版の
計測区間に入り、平均値が不安定だったため、各対戦の直前にGCを実行して切り分けた。
初期測定の平均倍率は1.004であり、これを探索全体の確実な高速化とは扱わない。

生の各対戦時間、実行環境、seed、入力ファイルのSHA-256は
[simulation_speedup_20260913.json](simulation_speedup_20260913.json) に保存。
サーバー並列実行や探索全体の速度は、この数値からは断定できない。

### AI読み込み・GCを含む連続対戦

対戦処理だけの差が実際の連続評価でも残るか、別の測定で確認した。
4相手 × 両席の8対戦を1バッチとして各版3バッチ（24対戦）実行。
バッチの前に前回分を回収し、**バッチ内のAI読み込み・対戦・最後のGCまで**を計時。
毎対戦の強制GCは行わず、通常の自動GCを有効にした。全対戦の報酬が一致した。

| 連続対戦全体 | 変更前 | 変更後 |
|---|---:|---:|
| 24対戦の合計時間 | 12.752秒 | 11.932秒 |
| 対戦数/秒 | 1.882 | 2.011 |

**読み込み・回収込みでも1.069倍（+6.88%）**。
これはローカル単一プロセスの結果で、ワーカー起動、通信、戦略生成は含まない。
[生の測定値](simulation_speedup_lifecycle_20260913.json) と
[測定スクリプト](../scripts/benchmark_simulation_lifecycle.py) を保存した。

```bash
.venv/bin/python scripts/benchmark_simulation_lifecycle.py \
  /tmp/kaggriculture_main_before_speedup.py \
  /tmp/kaggriculture_runner_before_speedup.py
```

## 正しさの検証

- 16対戦で、変更前と変更後の**全ターンの両者の行動・観測と最終状態**を照合し一致。
- そのうち各相手・両席の8対戦は公式ランナーとも全軌跡が一致。
- 比較はゲームデータの正規化JSONのSHA-256で実施。フレームワークの実行時間用
  メタデータを除き、盤面、手持ち・倉庫、市場、町、日時、player、stepを含む。
- `scripts/check_simulator.py` が成功。ルール定数、ロックされたマスからの移動、
  短期対戦と720-step設定の完全対戦の公式・高速ランナー一致を確認。
- `scripts/test_simulation_speed.py` の6テストが成功。全行動列のコピー形式、
  可変要素の独立性、途中で例外が出た場合の行動復元、作物の腐敗境界、複数サイズの
  倉庫隣接判定、公式関数が変更されていないことを確認。

## 再実行

```bash
.venv/bin/python scripts/test_simulation_speed.py
PYTHONPATH=training .venv/bin/python scripts/check_simulator.py
.venv/bin/python scripts/benchmark_simulation.py --verify
```

A/B比較には、変更前の2ファイルを別の場所に保存して指定する。
今回の一時バックアップが残っていれば次で同じ比較を実行できる。

```bash
.venv/bin/python scripts/benchmark_simulation.py \
  --baseline-agent /tmp/kaggriculture_main_before_speedup.py \
  --baseline-runner /tmp/kaggriculture_runner_before_speedup.py \
  --verify --output reports/simulation_speedup_20260913.json
```

今回の差分patchと変更後の対応するソースがあれば、別のコピー上で逆適用して
変更前のファイルを復元できる。作業中のソースへ直接逆適用しないこと。
