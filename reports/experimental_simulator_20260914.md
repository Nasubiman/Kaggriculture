# 仮置き高速シミュレーション v3（2026-09-14）

既存の `training/fast_kaggriculture.py` は変更せず、`experimental/faster-simulator`
ブランチ上だけで追加の高速化を試す。現在の実験版は
`training/experimental_fast_kaggriculture_v3.py`。v1/v2も比較・切り戻し用に残す。

## 導入した高速化

- 通常の2人対戦・現行デフォルト設定に専用化した hot loop / interpreter。
- 市場注文がないターンでは市場処理を丸ごとスキップ。
- 市場価格はinventoryが変化した商品のみ再計算。
- 2人用lockstep市場処理を専用実装し、queue/order-state/quoted等の一時コンテナ生成を削減。
- shed隣接判定をtuple生成+set lookupから算術判定へ変更。
- 植物腐敗は最初に起こり得るstepより前を即return、奇数stepも即return。
- finite-lifespan植物の座標をsidecarで追跡し、毎ターン全盤面を走査しない。
- PLANTのatomic seed validationはPLANTがない一般ケースでdict/set生成を避ける。
- HIRE時の中央4マスoccupancyをdict生成+sortせず4カウンタで選択。
- end-of-day shed dropはitemごとの`sum(shed.values())`再計算をやめ、使用量を増分管理。
- specialized interpreterでは毎stepの`Environment.done`/`env.state`往復を削減。
- 公開observationの共有参照は毎turn再代入せずepisode開始時に同期。
- 非対応設定・非2人・market cache無効時はstable fast runnerへfallback。

## GitHub Actions実測

GitHub hosted Ubuntu / Python 3.12、`kaggle-environments==1.32.7`。
public_v31 / v35 / v36 / v37、各両seat、1 seed。全8対戦でstableとの全action・observation・terminal parityを確認。
速度測定は同じ8対戦を2反復し、各variant 16試合。

| runner | games/s | median/game | 16 games total |
|---|---:|---:|---:|
| stable fast | 1.164 | 0.8457 s | 13.7495 s |
| experimental v3 | 1.217 | 0.8093 s | 13.1471 s |

**experimental v3 / stable = 1.0458x（+4.58% throughput）**。
この測定はagent import前後の条件を揃えたrunner A/Bであり、20 workerのserver探索全体の倍率ではない。

## profiler上の変化

public_v37との1試合cProfileでは、stableの`_process_market`が約0.058 s cumulative、
v3の専用market pathが約0.030 s。stableのplant decayが約0.062 s cumulative、
実験版のtracked decayが約0.016 sまで減った。

一方、1試合全体では`main.py`側の処理が支配的で、stdlib `copy.deepcopy`だけで
約0.49 s cumulative。したがってrunner単体の次の数%より、探索時に既存の
`training/agent_runtime.py::optimize_agent_module`を確実に使うこと、agent reuseを維持することの方が
全体throughputには重要。`scripts/evaluate_test_models.py`は既に両方をdefaultで有効にしている。

## 既存スクリプトで実験版を使う

stable sourceを変更せず、次のwrapperで任意のスクリプトの
`import fast_kaggriculture`だけをv3へ差し替えられる。

```bash
.venv/bin/python scripts/run_with_experimental_simulator.py \
  scripts/evaluate_test_models.py --candidate main.py --seeds 100 --workers 20
```

正しさの確認・単一processベンチは:

```bash
python scripts/benchmark_experimental_simulation.py --seeds 1 --repeats 2
python scripts/profile_experimental_simulation.py
```

stable runnerへの昇格は、ローカル/`kag-server`でより多いseed・相手・branch continuationを含むparity gateを通した後に行う。
