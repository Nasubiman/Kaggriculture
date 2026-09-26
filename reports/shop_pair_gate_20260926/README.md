# 6日目の店舗ペア別補正: 独立seed検証 (2026-09-26)

## 結論

現行 `main.py` のテープ選択は6日目の最初の2店舗で分岐する。追加の補正も同じ情報で分岐させる案を検証したが、今回の候補は独立seedで勝率が悪化したため、提出モデルへ採用しない。評価目的は勝率であり、平均得点差だけの改善では採用しない。

| 補正候補 | 事前スクリーン | 未使用seed・発動時 | 非発動時 | 判定 |
|---|---:|---:|---:|---|
| 需要店2店舗かつYARNなしで施肥開始をday10→14 | +6勝 / 432戦 | **-12勝 / 264戦**、平均得点差-64.7 | 216戦で結果完全一致 | 不採用 |
| 需要店0–1店舗かつYARNなしで人参切替比率2.0→1.6 | +4勝 / 1,056戦 | **-12勝 / 480戦**、平均得点差-2.6 | このseed群では該当なし | 不採用 |
| `FARMERS_MARKET|BAKERY` のテープをnative→route104 | +5勝 / 384戦 | **-4勝 / 128戦**、平均得点差+515 | 該当なし | 不採用 |

「需要店」は `BRUNCH_SPOT`、`ICE_CREAM_SHOP`、`SMOOTHIE_SHOP`、`FARMERS_MARKET`。施肥・人参ゲートは最初の2店舗の需要店数で分類し、店舗の順序は区別しない。テープ変更では順序を含む `FARMERS_MARKET|BAKERY` だけを対象にした。施肥・人参は、既存のテープ選択には手を加えず、後段の補正パラメータだけを変えた。

## 検証条件

- 事前スクリーン: `server-results/clsvar_screen/{base,fert14,carrot16}.json` と `server-results/route_search/validate6.json`。ここから店舗ペア条件を選んだので、この数値は採否判定には使わない。
- 未使用seed: `server-results/route_search/class_holdout_seeds.json` の H 60件、L 60件。前者のうち最初の2店舗による施肥ゲートが実際に発動したのは33 seed。各seedを両席で試した。
- 対戦相手: `results23_20260923`、`results25_20260923`、`results29_20260924`、`pub_2965_master_hybrid_20260925`。同じseed・席・相手で現行モデルと候補を比較。20ワーカー、エラー0。
- テープ変更の追加検証: seed map の各ペアに対する先頭40 seedを除き、次の16 seedを使用。上記4相手と両席、計128対の比較。エラー0。
- 生データ: `holdout_H/`、`holdout_L/`、`route_holdout.json`。`scripts/analyze_shop_pair_gate.py` でパラメータ補正の対応あり／なしを再集計できる。

事前スクリーンで人参補正の改善が集中した `FARMERS_MARKET|PIZZA_SHOP` は、独立seedの24戦では行動・得点が一度も変わらなかった。一方、別の `PET_CAFE|BAKERY` では40戦中12勝を失った。店舗ペア単位でも、少数seedの偶然と効果の不発を区別する必要がある。

## 実験用ファイル

- `scripts/build_shop_pair_gate.py`: 現行 `main.py` をコピーし、6日目の2店舗による後段補正を付加した提出形式の実験候補を作る。元の `main.py` は書き換えない。
- `candidates/shop_gate/fert14_high.py`、`carrot16_low.py`: 今回の不採用候補。提出しない。
- `scripts/screen_on_seeds.py`: JSON形式のseedクラスを `--seed-class` で指定可能にした。

次に同様の探索をする場合は、店舗ペア別の改善量だけで採用せず、(1) 事前seedで候補を固定、(2) 未使用seedで両席・複数の現行強豪相手を対戦、(3) 発動しない条件で結果完全一致、(4) 勝率と相手別内訳を確認する。現行モデルの勝率が既に高いため、平均得点差のみのプラスは重視しない。
