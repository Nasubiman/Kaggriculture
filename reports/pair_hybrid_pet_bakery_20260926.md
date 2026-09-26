# PET_CAFE→BAKERY 限定の Harvest Ledger 切替（2026-09-26）

## 変更

`main.py` は、6日目（step 144）の最初の2店が PET_CAFE→BAKERY の試合だけ、公開エージェント「Kaggriculture | Harvest Ledger」（`test/pub_harvest_ledger_20260925`）の行動に切り替える。

- 0〜143ステップは現行モデルの行動を提出する。Harvest Ledger も同じ観測（コピー）を受けて裏で動かし、その行動は捨てる。
- step 144 で最初の2店が PET_CAFE→BAKERY なら、以降は Harvest Ledger の行動を使う。例外が出た場合は現行モデルに戻す。
- それ以外の63組み合わせでは、現行モデル（results28 ＋ `_MP_H`=40・`_DP_H`=12・肥料10日目）のまま動く。
- Harvest Ledger のソースは、帰属表示とライセンス表記を含めて圧縮して埋め込んだ。生成は `scripts/build_pair_hybrid.py`。検証済みの `candidates/pair_hybrid_pet_bakery/main.py` と `main.py` は同一ファイル（SHA-256 先頭 bb91926cc4e2bbd6）。

## 理由

店舗ペア別の評価で、PET_CAFE→BAKERY は現行モデルの最弱ペアだった（強敵3モデルに対して勝率28%、未使用seedでも27%）。この組み合わせでは Harvest Ledger 単体の方が大幅に強かった。テープ107への切替や、DP の見通し時間の変更は改善が小さいか、相手によって悪化した。

## 評価（PET_CAFE→BAKERY のseed、6モデル×両座席）

| seed群 | 現行モデル | 切替版 |
| --- | ---: | ---: |
| 探索 24 seed | 167/288 | 223/288 |
| 未使用 24 seed | 171/288 | 225/288 |
| 最終 40 seed | 281/480 | 386/480 |

最終40 seedでは、6モデルすべてに対して勝数が同等以上だった。

## 対象外ペアの確認

- 対象外の12種類の店舗ペア×3モデル×両座席の72局で、元のモデルと両者の得点が完全に一致した（51/72勝で同一）。
- 公式シミュレータでの動作確認（2026-09-26）：Kaggle の読み込み器が選ぶ入口は `kaggle_agent`。PET_CAFE→BAKERY と BAKERY→BAKERY の各seed・両座席でエラーなく完走した。切替は対象ペアだけで発生し（575ステップ）、1ステップの処理時間は平均1〜2ms、最大62ms。

## 残課題

- 他の弱いペア（SMOOTHIE→SMOOTHIE、FARMERS→BRUNCH、ICE_CREAM→ICE_CREAM）にも、同じ切替方式が効くか。
- 肥料の開始日を14日目に戻す案は、実戦で当たった相手の記録で+1勝だったが、今回の `main.py` には入っていない。
- 未提出、未コミット。
