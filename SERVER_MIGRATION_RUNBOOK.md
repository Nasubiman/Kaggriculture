# CPU/GPUサーバー移行ランブック

- 作成日: 2026-07-31
- 想定環境: Linux、NVIDIA GPU、十分なCPUコアとNVMeストレージ
- 対象リポジトリ: `https://github.com/Nasubiman/Kaggriculture.git`
- 現在のブランチ: `main`

この文書は、現在のMac上の開発環境から計算サーバーへ移行し、既存エージェントの再現確認から模倣学習・自己対戦強化学習へ進むための引き継ぎメモである。

## 1. 現在のプロジェクト状態

### 実行環境

移行前に確認したローカル環境は次の通り。

| 項目 | 現在値 |
|---|---|
| Python | 3.12.13（`.venv`内） |
| `kaggle` | 2.2.4 |
| `kaggle-environments` | 1.32.2 |
| ゲーム長 | 720ターン |
| プレイヤー数 | 2 |
| 現在の提出ファイル | `main.py` |

システムの`python3`は3.9.6だが、プロジェクトはPython 3.11以上を必要とするため、必ずPython 3.12の仮想環境を使う。

### 現在のエージェント

`main.py`はCow Crown v1で、次の構成になっている。

- 序盤は羊2頭と既存作物で資金を作る
- day 11から牛中心へ移行
- 北東の土地を購入
- 牛20頭、羊2頭、hand 12人を目標にする
- 牛を中央のshed付近に配置する
- day 30にhandを再雇用し、最終回収・売却を行う

詳細は次を参照。

- `reports/cow_strategy_implementation.md`
- `reports/cow_strategy_analysis.md`
- `reports/public_history_summary.md`
- `reports/orbit_wars_learning_methods.md`

### 再現済みのローカル評価

| 対戦相手 | Games | Win rate | Mean reward | Mean margin |
|---|---:|---:|---:|---:|
| Archived Pulse Breaker v2 | 10 | 100% | 105,481 | +69,649 |
| ユーザー提供score 800 agent | 10 | 100% | 107,046 | +72,462 |

両方のseatとheld-out seedで評価済み。ただし、ローカルrewardはKaggle leaderboard ratingを直接予測するものではない。

## 2. Gitに含まれるもの・含まれないもの

### Gitに含まれる

- `main.py`
- `agents/`
- `scripts/`
- `reports/`にある既存の集計結果
- `requirements.txt`
- `Makefile`
- ゲーム仕様書

### Gitに含まれない

| 対象 | 現在の状態 | 移行方法 |
|---|---|---|
| `.venv/` | 約1.2 GB | コピーせずサーバーで再作成 |
| `replays/` | 約520 MB、27ファイル | 必要なら別途転送、またはKaggleから再取得 |
| `kaggle-data/` | Git対象外 | サーバーで再ダウンロード |
| `.env` | Git対象外 | サーバーで再作成 |
| Kaggle token | Git対象外 | Secret Managerまたは`~/.kaggle/`へ配置 |
| logs / zip / tar.gz | Git対象外 | 必要なものだけ別途転送 |
| score 800参照エージェント | Codexのローカル添付 | 必ず別途保全する |

特にscore 800参照エージェントは、現在次のMac固有パスにある。

```text
/Users/nakamuray/.codex/attachments/40f45862-6d72-4d5f-9fbd-bab35f6354ff/pasted-text.txt
```

`scripts/head_to_head.py`のデフォルトもこのパスを参照するため、サーバーではそのまま動かない。元の`pasted-text.txt`を安全な場所へコピーして実行時に`--reference`で明示するか、Notebookのマーカーを除いた純粋なPythonファイルへ変換する。

## 3. ローカル環境を離れる前のチェックリスト

- [ ] `git status`を確認し、必要な変更をcommitする
- [ ] `git push origin main`を実行する
- [ ] score 800参照エージェントを安全な転送先へコピーする
- [ ] 過去replayを保持するか、サーバーで再取得するか決める
- [ ] Kaggle tokenをGitに入れていないことを確認する
- [ ] 必要なら現在の`replays/`を圧縮し、リポジトリ外で保管する

replayを保持する場合の例:

```bash
tar -czf kaggriculture-replays-20260731.tar.gz replays
scp kaggriculture-replays-20260731.tar.gz USER@SERVER:/SECURE/DATA/PATH/
```

`.venv/`はOS依存なので転送しない。

## 4. 推奨サーバー構成

学習の有効性を検証する初期段階では、GPUを大量に用意する必要はない。

| リソース | 推奨 |
|---|---|
| CPU | 16～32物理コア以上 |
| RAM | 64 GB以上 |
| GPU | RTX 4090/5090、A100、H100などをまず1枚 |
| GPU VRAM | 24 GB以上が扱いやすい |
| Storage | NVMe SSD、空き200 GB以上 |
| OS | Ubuntu 22.04または24.04 LTS |

Kaggricultureでは、当面はGPU性能よりもCPU側のepisode生成速度が重要になる。自己対戦ワーカーをCPUで並列化し、複数ワーカーの推論をGPUでまとめてbatch処理する構成を目指す。

複数GPUは、1 GPUで学習曲線が明確に伸び、episode生成もGPU更新も飽和してから追加する。

## 5. サーバー初期セットアップ

### OSとGPUの確認

```bash
nvidia-smi
lscpu
free -h
df -h
```

NVIDIA driverが正常に見えてから、Python側のCUDA対応ライブラリを入れる。PyTorchとJAXを最初から両方入れず、学習実装を決めてから片方を選ぶ。

### リポジトリ取得

```bash
git clone https://github.com/Nasubiman/Kaggriculture.git
cd Kaggriculture
git checkout main
git pull --ff-only
```

### Python環境

UbuntuでPython 3.12が利用可能であることを前提とする。

```bash
python3.12 -m venv .venv
make setup PYTHON=python3.12
.venv/bin/python --version
.venv/bin/python -m pip show kaggle kaggle-environments
```

期待値:

```text
Python 3.12.x
kaggle 2.2.4付近
kaggle-environments 1.32.2
```

現在の`requirements.txt`はバージョン範囲指定なので、将来は検証済み環境からlockファイルを作る。移行直後は、まず上記の現在バージョンと合わせる。

## 6. Kaggle認証

tokenをリポジトリへ置かない。推奨は`~/.kaggle/access_token`またはサーバーのSecret Manager。

```bash
mkdir -p ~/.kaggle
nano ~/.kaggle/access_token
chmod 600 ~/.kaggle/access_token
```

確認:

```bash
make kaggle-check
.venv/bin/kaggle competitions leaderboard kaggriculture -s
```

環境変数を使う場合は`KAGGLE_API_TOKEN`をshellまたはジョブスケジューラのsecretとして設定し、ログに表示しない。

## 7. 移行直後の再現確認

最初にGPU学習を始めず、既存エージェントがMacと同じ挙動をすることを確認する。

### 基本評価

```bash
make evaluate
```

期待する最低条件:

- 全gameが`DONE`
- starter/randomに対して勝率100%
- エージェント例外がない

### score 800参照との比較

```bash
.venv/bin/python scripts/head_to_head.py \
  --reference /SECURE/PATH/score800_reference.txt \
  --seeds 7101 7102 7103 7104 7105 \
  --output reports/server_cow_vs_score800.json
```

期待する目安:

- 10 games
- 10 wins
- mean rewardがおよそ107,000
- mean marginがおよそ+72,000

値が大きくずれた場合は、学習へ進む前にPython・`kaggle-environments`のバージョン、seat、seed、参照エージェントの内容を確認する。

## 8. Public Game Historyの再取得

現在の分析結果は2026-07-31時点のsnapshotである。leaderboardや上位戦略が変わった場合は再取得する。

```bash
make history-collect
make history-analyze
make cow-analyze
```

保存先:

- 生replay: `replays/`（Git対象外）
- 集計: `reports/public_history_summary.md`
- 牛戦略分析: `reports/cow_strategy_analysis.md`

再取得データと古いデータを混同しないよう、学習datasetには取得日時、team、submission ID、episode IDを残す。

## 9. GPU学習の導入順

### Phase 0: 正確性と速度計測

最初に現在の`kaggle_environments`版を基準実装として扱う。

- 固定seed・両seatで決定論的に再現する
- 1 episodeと1,000 episodeの所要時間を記録する
- CPUコア数を増やしたときのepisodes/secを測る
- `debug=True`と`debug=False`の差を測る

高速シミュレータを新しく作る場合も、同じaction列に対して全stepの主要stateと最終rewardが基準実装に一致することを先に確認する。

### Phase 1: 模倣学習

上位Game Historyから高レベル判断を学習する。

最初の学習対象候補:

- 牛を購入するか
- 牛を何頭まで増やすか
- 土地をいつ購入するか
- handを何人雇うか
- 市場で何を売買するか
- 農場作業の優先順位

生の全unit actionを直接予測するより、現在のルールベースプランナーが作った合法候補をモデルに選ばせる方が、データ効率と提出時の安定性が高い。

### Phase 2: 自己対戦PPO

模倣モデルまたはルールベース方策を初期値にする。

Opponent Pool:

- `agents/baseline_v1.py`
- `agents/pulse_breaker_v2.py`
- 現在の`main.py`
- score 800参照エージェント
- 上位Game Historyの模倣モデル
- 過去のPPO checkpoint

報酬:

- 最終勝敗または順位を主報酬にする
- 初期学習だけ資産増加などの補助報酬を利用する
- 補助報酬は徐々に弱める

### Phase 3: リーグと短時間探索

- PFSPなどで現在モデルが苦手な過去モデルを多く選ぶ
- 最新モデル同士だけの自己対戦を避ける
- 中央の牛配置、市場売却、day 30の回収など重要局面だけ短い探索を行う

## 10. 推奨ディレクトリ構成

学習コードを追加するときは、提出用の`main.py`と分離する。

```text
Kaggriculture/
├── agents/                 # ルールベース・export済みagent
├── configs/                # 学習・評価設定
├── datasets/               # 生成データ。原則Git対象外
├── models/                 # 提出用の小さい重みだけを選別
├── checkpoints/            # 学習checkpoint。Git対象外
├── training/               # BC/PPO/league実装
├── scripts/                # 収集・評価・変換コマンド
├── reports/                # 小さい集計結果
└── main.py                 # Kaggle提出エントリ
```

上記ディレクトリは現時点では未作成。作成時には`datasets/`、`checkpoints/`、大きなmodel weightsを`.gitignore`へ追加する。

## 11. 実験記録

各runで最低限、次を保存する。

- Git commit SHA
- config全体
- Pythonとpackage versions
- GPU名、CUDA version、CPUコア数
- random seed
- training stepsとenvironment steps
- wall-clock time
- opponent poolの構成
- train/validation/held-out seeds
- 両seatのwin rate、mean reward、mean margin
- checkpointの由来

実験名の例:

```text
bc_top3_20260731_v001
ppo_cow_macro_pool_v003
ppo_cow_macro_pfsp_v006
```

単一の自己対戦相手に対する勝率だけで採用せず、固定された複数の過去agentとheld-out seedsによるローカル総当たりで判断する。

## 12. 長時間ジョブ

SSH切断で学習を止めない。

- 小規模サーバー: `tmux`または`systemd`
- クラスタ: Slurmなどのジョブスケジューラ
- ログ: stdoutだけでなくrun directoryへ保存
- checkpoint: 一定間隔とbest評価時に保存
- resume: optimizer、scheduler、RNG、opponent poolを含める

学習が止まった場合に最初からやり直さないため、resumeテストを短いrunで先に行う。

## 13. 既知の注意点

1. `scripts/head_to_head.py`にはMac固有の参照ファイルパスがある。
2. `requirements.txt`は完全固定ではないため、依存更新で結果が変わる可能性がある。
3. `replays/`はGitに含まれず、現在約520 MBある。
4. 公開Game Historyは時間とともに更新される。
5. 大量GPUより先に、CPU episode生成とbatch inferenceを最適化する。
6. Kaggle実行環境でGPUが利用できるとは限らない。提出モデルはCPUでも時間制限内に動く大きさにする。
7. 学習用コード・依存関係を`main.py`へ直接混ぜない。
8. 大きいcheckpointやdatasetを通常のGitへcommitしない。
9. seedだけでなく両seatを必ず評価する。
10. 新しい高速シミュレータは、基準環境とのstep単位一致を確認してから学習に使う。

## 14. 最初の作業順

サーバー移行後は次の順で進める。

1. cloneとPython 3.12環境作成
2. Kaggle認証
3. `make evaluate`で基本再現
4. score 800参照を転送し、held-out評価を再現
5. public replayを再取得または転送
6. 現在のシミュレータ速度を計測
7. replayから学習datasetを生成
8. 小さい模倣モデルをGPU 1枚で学習
9. ルールベース候補選択とのハイブリッドを評価
10. CPU並列自己対戦とPPOを導入
11. 過去checkpoint league/PFSPを導入
12. CPU推論可能な提出形式へexport

最初の成功条件は「GPUを使うこと」ではなく、**既存結果を再現したうえで、同一のheld-out評価において学習モデルがCow Crown v1を安定して上回ること**とする。
