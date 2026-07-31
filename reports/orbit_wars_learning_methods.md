# Orbit Wars上位解と類似シミュレーションコンペの学習手法

- 調査日: 2026-07-31
- 対象: Orbit Warsで公開されている1～11位の解法10件（4位を除く）
- 目的: 上位解で多く使われた学習方法を整理し、Kaggricultureへの適用方針を決める

## 結論

Orbit Warsでは、**PPOによる自己対戦強化学習**が圧倒的多数だった。ただし、生の行動をすべてニューラルネットに任せるのではなく、次の要素を組み合わせたハイブリッド型が実態である。

- 高速に書き直したシミュレータ
- 手作業で圧縮した意味的な行動空間
- 合法手マスクや幾何計算などのルール
- 過去チェックポイントを含む対戦相手リーグ
- 必要な局面だけの短い探索

公開Game Historyを使った模倣学習は初期モデルの作成には有効だったが、模倣学習だけで終えず、自己対戦強化学習に接続した解法の方が強かった。

## Orbit Wars上位解の集計

| 方法 | 採用数 | 内容 |
|---|---:|---|
| PPO系自己対戦 | 9/10 | 現在または過去の自分と大量に対戦 |
| IMPALA/V-trace | 1/10 | 5位が非同期強化学習として採用 |
| 外部Game Historyの模倣を最終系に利用 | 2/10 | 5位と11位 |
| 学習なしの完全ルールベース | 0/10 | 公開された上位解では確認できず |
| Transformer/Attention | 10/10 | 惑星や航路をEntityとして処理 |
| 過去モデルのリーグ/PFSP | 多数 | 最新モデル同士だけの過学習を防止 |
| 終局勝敗・順位中心の報酬 | ほぼ全員 | 細かい報酬整形は最終的に減らす傾向 |

### 各順位の概要

- [1位](https://www.kaggle.com/competitions/orbit-wars/writeups/1st-place-solution-scaling-reinforcement-learnin)
  - 模倣なしのPPO自己対戦
  - 約150億ステップ、2人戦と4人戦を同時学習
  - 200MパラメータのTransformer
- [2位](https://www.kaggle.com/competitions/orbit-wars/writeups/2nd-place-solution-for-orbit-wars)
  - 上位棋譜の模倣学習で一度Top 10に到達
  - 最終的にはゼロからの自己対戦PPOが模倣モデルを上回った
- [3位](https://www.kaggle.com/competitions/orbit-wars/writeups/3rd-place-ab-in-den-orbit)
  - PPOとPFSPを使用
  - 現在のモデルが苦手な過去モデルを重点的に対戦相手として選択
- [5位](https://www.kaggle.com/competitions/orbit-wars/writeups/orbit-wars-5th-place-solution)
  - 上位棋譜でBehavior Cloning
  - その後、IMPALA/V-traceで自己対戦
- [6位](https://www.kaggle.com/competitions/orbit-wars/writeups/6th-rl-league-search-with-a-custom-edge-atte)
  - PPO、リーグ、推論時の2手探索
  - 小さいRLモデルから大きいモデルへの教師転移も利用
- [7位](https://www.kaggle.com/competitions/orbit-wars/writeups/7th-place-solution-how-structured-experiments-sa)
  - PPOに手作業の射撃プランナーと行動マスクを統合
  - ローカル総当たり戦で変更を評価
- [8位](https://www.kaggle.com/competitions/orbit-wars/writeups/8th-place-how-i-made-ender)
  - PPO、過去チェックポイントのリーグ、推論時探索
  - 比較的低い計算予算でも上位に到達
- [9位](https://www.kaggle.com/competitions/orbit-wars/writeups/9th-place-solution-end-to-end-jax-ppo)
  - JAXでシミュレータからPPOまで一体化
  - Population Based Trainingとリーグを利用
- [10位](https://www.kaggle.com/competitions/orbit-wars/writeups/10th-place-solution)
  - PPOと過去の基準モデルを含むローカルArena
  - 2人戦と4人戦を分けて学習
- [11位](https://www.kaggle.com/competitions/orbit-wars/writeups/11th-place-solution-standing-on-the-shoulders-of)
  - 上位プレイヤー約3,500試合の模倣学習後にPPOとPFSP
  - 模倣学習だけでは約25位で、RLを加えて11位

## 山登り法との違い

過去の行動列を部分的に入れ替えて評価する、山登り法に近い方法はOrbit Wars上位解の中心ではなかった。

対戦ゲームでは、途中の行動を変えると相手の反応と後続状態も変わるため、固定された行動列を最適化しても別の試合に一般化しにくい。そのため、上位解は行動列ではなく、**現在の状態から行動を選択する方策と、局面を評価する価値関数**を学習している。

ただし、ルールベースエージェントのパラメータ調整や、意味的な行動候補の探索には山登り法や進化的最適化を利用できる。

## 類似シミュレーションコンペ

| コンペ | 上位方式 | 示唆 |
|---|---|---|
| [Lux AI 2021・1位](https://www.kaggle.com/c/lux-ai-2021/discussion/294993) | Deep RL自己対戦 | ルールベースも開発したが、RLが上回ったため途中で中止 |
| [Lux AI Season 2・10位](https://www.kaggle.com/competitions/lux-ai-season-2/writeups/deimos-10th-place-deimos-s-rl-approach) | PPO自己対戦とカリキュラム | 公開リプレイの途中状態から試合を開始して探索範囲を拡大 |
| [Hungry Geese・2位](https://www.kaggle.com/competitions/hungry-geese/writeups/goosebumps-goosebumps-solution-2nd-place) | 上位棋譜の模倣とPUCT/MCTS | 模倣モデルのミスを探索で補正 |
| [Hungry Geese・5位](https://www.kaggle.com/competitions/hungry-geese/writeups/takedarts-5th-place-solution-geesezero) | AlphaZero型自己対戦とDUCT | 外部棋譜なしで自己対戦データから学習 |
| [Kore 2022・1位](https://www.kaggle.com/competitions/kore-2022/writeups/harm-buisman-1st-place-solution) | 完全ルールベースと経路探索 | 正確な先読みとルート評価ができれば学習なしでも優勝可能 |

以上から、シミュレーションコンペでは単一の学習手法が常に優位なのではなく、概ね次の使い分けになる。

- 高速に数億～数十億ステップを生成できる場合: PPO自己対戦
- 上位Game Historyが豊富で探索しやすい場合: 模倣学習とMCTS
- 規則が明確で局面を正確に先読みできる場合: ルールと探索
- 実際の上位解: 上記を組み合わせたハイブリッド

## Kaggricultureへの推奨構成

Kaggricultureでは、生の全行動を最初からPPOに学ばせるより、現在のルールベースエージェントを利用した次の構成が現実的である。

1. 現在の牛中心エージェントを、合法な行動候補を作るプランナーとして残す。
2. 上位Game Historyから高レベル判断を模倣学習する。
   - 牛を買うか
   - 中央に何頭送るか
   - 作物、設備、労働者のどれを優先するか
   - 売買や繁殖のタイミング
3. 模倣モデルを初期値としてPPO自己対戦を行う。
4. 対戦相手を固定せず、次のOpponent Poolを使用する。
   - 現在の`baseline_v1`
   - score 800の参照エージェント
   - 牛中心ルールエージェント
   - 上位棋譜の模倣モデル
   - 過去のPPOチェックポイント
5. 報酬は最終順位と勝敗を中心にする。
6. 学習初期だけ資産増加などの補助報酬を使い、後半は弱める。
7. 中央の牛争いや市場など重要な局面だけ、短い先読み探索を追加する。

Kaggricultureで最も参考になるのは、Orbit Warsの5位・11位の「Game History模倣から自己対戦RLへ移行する構成」と、6～8位の「学習と手作業プランナーを組み合わせる構成」である。
