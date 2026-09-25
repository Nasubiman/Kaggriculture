# 4区画候補の無作為seed比較（2026-09-24）

前回の ICE_CREAM + SMOOTHIE 条件付きseedだけの対戦では候補が有利だったため、seedを事前に無作為抽出した評価を実施した。候補は `scripts/search_public_four_quadrant.py` の `early_ice_smoothie_high_prices`。現行 `main.py` は変更していない。

- seed: `random.Random(20260924).sample(range(2**31), 1000)`
- 相手: results14、results20、results23、results29。それぞれ両座席で対戦し、計8,000組。
- 実行: サーバーの高速シミュレータ、16 worker。ローカルとサーバーの `main.py` SHA-256 は一致。
- 比較: 全8,000組で現行を実行。候補のstep253/289ゲートが現行の観測で成立した組だけ候補も完走。非成立組は候補と現行の行動が同じなので結果を共用し、51組を別途再実行してすべて一致した。
- 生データ: `reports/four_quadrant_random1000_20260924.json`。再実行スクリプト: `scripts/evaluate_four_quadrant_random.py`。

| 指標 | 現行 | 4区画候補 |
| --- | ---: | ---: |
| 勝利数 / 8,000 | 7,122 | 7,095 |
| 勝率 | 89.025% | 88.688% |
| 平均得失点差 | +1,105 | +1,178 |
| 平均自分得点 | 97,932 | 98,048 |

候補の発動は184/8,000組（2.3%）、23 seed。発動した局では現行142勝、候補115勝で、30局を負けから勝ちへ、57局を勝ちから負けへ反転した。相手別の勝利数差は results14 `-17`、results20 `-16`、results23 `+3`、results29 `+3`。条件付きseedでの平均得失点差改善は無作為seedでも残るが、勝率目的では現行より27勝少ない。

seedごとの8対戦をひとまとまりとして計算した勝率差は `-0.34` パーセントポイント、正規近似95%区間はおよそ `[-0.89, +0.22]` ポイント。候補の優位性は示せず、差が小さい可能性も残る。4相手は固定した代表モデルで、相手分布全体への外挿はしない。この結果では候補を `main.py` に採用しない。

再実行例:

```bash
PYTHONPATH=training .venv/bin/python scripts/evaluate_four_quadrant_random.py \
  --seeds 1000 \
  --opponents results14_20260923 results20_20260923 results23_20260923 results29_20260924 \
  --workers 16 \
  --output reports/four_quadrant_random1000_20260924.json
```
