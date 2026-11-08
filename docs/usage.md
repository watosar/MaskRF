# 導入と利用方法

MaskRFは、設定で定めた基板・給電・短絡に16×16の金属マスクを配置し、2ポート回路を評価する。目的と検証結果は[検証レポート](reproduction-report.md)を参照する。以下のコマンドはリポジトリのルートで実行し、Pythonの実行・環境管理には `uv` を使う。

## 1. Python環境

Python 3.12を使用する。パッケージは `src/` レイアウトで、標準設定とマスク例をwheelに同梱する。`PYTHONPATH` の設定は不要である。

```bash
uv sync --locked --inexact
source env.sh
uv run maskrf --help
```

この環境だけで、入力検査、保存済み応答の読み込み・再利用、ターゲット採点を実行できる。新規FDTD解析、形状・メッシュの生成、保存波形の再処理には次のネイティブ環境が必要になる。

## 2. openEMS・CSXCADの構築

構築スクリプトの対象環境はUbuntu 24.04／x86_64である。`uv`、`git`、`cmake`、C/C++コンパイラ、Python 3.12開発ヘッダと、約5 GBの空き領域を用意する。

```bash
mkdir -p tmp/setup
bash scripts/bootstrap.sh > tmp/setup/bootstrap.log 2>&1
source env.sh
```

[bootstrap.sh](../scripts/bootstrap.sh)はopenEMS-Project v0.0.36の固定コミットとサブモジュールをビルドする。依存するUbuntuパッケージはダウンロード・展開し、システムへはインストールしない。構築用ファイルは `tmp/native-build/`、導入先とwheelは `.native/`、Python環境は `.venv/` に保存する。他のOS・CPU向けの構築手順は検証していない。

`env.sh` は共有ライブラリの参照先と、Matplotlibの作業先を設定する。外部のネイティブ導入先を使う場合は、sourceする前に `MASKRF_NATIVE` をそのパスへ設定する。

環境の同期には `uv sync --locked --inexact` を使う。ネイティブバインディングはローカルwheelから追加するため、通常の同期で削除しないようにする。`.venv` を作り直した場合は、保存済みwheelを再導入する。

```bash
uv sync --locked --inexact
uv pip install --python .venv/bin/python .native/wheels/*.whl
source env.sh
```

ビルドしたネイティブ版はopenEMS 0.0.36／CSXCAD 0.6.3である。上流のwheelメタデータは0.0.33／0.6.2なので、導入版の確認にはビルドしたソースの版も使う。

## 3. マスクと設定

| 項目 | 仕様 |
|---|---|
| 入力 | 16×16のNumPy配列、二次元リスト、CSV、JSON配列、白黒PNG |
| 数値 | 1＝金属、0＝空白。boolも使用可。非二値・非数値入力は拒否 |
| PNG | 黒＝金属、白＝空白。灰色は拒否 |
| 座標 | 行0が+y、列0が−x。マスク中心が原点 |
| 標準寸法 | ピッチ0.125 mm、内側2 mm角 |
| 付加する構造 | 設定に従う基板、裏面GND、給電線、短絡 |

CSVはヘッダなしの16行×16列、JSONは二次元配列そのものを入力する。18×18の端子込み表現の自動変換や、孤立金属の除去、角接触の接続・切断などの形状修正は行わない。

標準設定は[同梱YAML](../src/maskrf/configs/paper_corrected.yaml)にある。条件を変更する場合は[編集用設定例](../examples/configs/paper_corrected.yaml)をコピーし、APIの `config_path` またはCLIの `--config` に渡す。マスク評価には `geometry.kind: mask` と `solver.excitations: [1, 2]` が必要である。設定の長さはmm、周波数は `frequency_GHz: [開始, 終了, 点数]` で指定する。低位の `run`・`inspect` コマンドでは、`geometry.file` をYAMLの所在からの相対パスとして解決する。`evaluate_mask` はその値を入力マスクの保存先へ置き換える。

材料・形状・格子の変更には個別の精度確認が必要である。図3(a)について確認した格子差を、変更後の設定や任意マスクの誤差上限として使わない。

## 4. Python API

公開APIは `evaluate_mask`、`load_response`、戻り値の `CircuitResponse`、解析失敗を表す `SimulationError` である。

```python
from maskrf import evaluate_mask, load_response

response = evaluate_mask(
    "examples/data/fig3a-mask.csv",
    "tmp/python-example",
    reuse_run="tests/fixtures/completed-run",
)
frequency_GHz = response.frequency_Hz / 1e9
s21 = response.s[:, 1, 0]
print(response.metrics["first_downward_3dB_GHz"])
saved = load_response("tmp/python-example")
```

`evaluate_mask(mask, out_dir, *, config_path=None, reuse_run=None)` は同期処理である。`reuse_run` を省略すると両ポートを独立に励振して新規解析し、標準設定では数十分以上かかる。出力先は未使用のディレクトリにする。

| 戻り値 | 内容 |
|---|---|
| `frequency_Hz` | Hz単位の周波数配列。標準は10–30 GHzの401点 |
| `s` | 複素配列 `(周波数点数, 2, 2)`。`s[:, i-1, j-1]` がSij |
| `metrics` | S21の帯域指標、下降側−3 dB交差、相反性・電力比・受動性の指標など |
| `settings`・`mask` | 解析・計測条件と入力マスク |
| `run_dir` | 解析結果の所在 |
| `to_dict()` | 実部・虚部、dB振幅、度単位の位相、指標を含むJSON化可能な辞書 |

`load_response(run_dir)` は完了済み解析または `evaluate_mask` の出力から応答を読み込む。両励振の正常終了・減衰、周波数配列、全S成分の有限値を検査する。減衰を満たさない解析は `SimulationError` として拒否する。単一のAPI呼び出しではメッシュ収束を調べず、厳密な受動性違反を理由とする自動排除も行わない。これらは指標と追加検証で判断する。

再利用には、入力マスクと材料・形状・ポート・格子・境界・ソルバ・検証設定の一致が必要である。結果の複製ではなく元の解析ディレクトリを参照するため、元のディレクトリも保持する。テスト用fixtureの収録範囲は[fixtureの説明](../tests/fixtures/README.md)を参照する。

## 5. CLIと保存結果

```bash
source env.sh
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --out tmp/circuit-01
uv run maskrf inspect --config examples/configs/paper_corrected.yaml --out tmp/inspect-01
```

`evaluate` は成功時に応答JSONを標準出力と `response.json` に返す。失敗時は非ゼロ終了となり、エラーJSONを標準エラーに出す。解析開始後の失敗は `error.json` にも残す。入力やソルバのログは出力先へ保存する。

| 主なファイル | 内容 |
|---|---|
| `mask.csv`・`request.yaml`・`request.json` | 入力マスク、実際に渡した設定、入力のハッシュと形状監査 |
| `response.json` | 完了した応答と指標、解析ディレクトリへの参照 |
| `execution.log` | 新規解析プロセスのログ |
| `run/effective.json`・`run/status.json` | 新規解析の実効設定と各励振の終了・減衰判定 |
| `run/sparameters.csv`・`run/network.s2p` | 全複素SのCSVとTouchstone |
| `run/solver-*.log`・`run/excite-*/` | 励振ごとのログと波形 |

`--reuse-run` を指定した場合は `run/` を新規作成せず、応答は既存解析を参照する。CLIは `uv run python -m maskrf` からも呼び出せる。

低位の解析操作は次のとおりである。`compare` と `postprocess` は保存波形を再処理するため、ネイティブ環境も必要になる。`convergence` は設定の `convergence` に列挙した各格子で新規解析し、設定した段階間の差を計算する。

`run` と `convergence` は、各励振の正常終了と減衰を確認する。終了コード0でも減衰条件未達なら状態とログを保存して非ゼロ終了し、後続の励振・格子解析と通常の後処理へは進まない。`postprocess` は設定した全励振の波形が保存されている場合に診断用の再処理として使えるが、その処理の成功は解析の正常終了・減衰を意味しない。第1励振で停止して第2励振の波形がないrunは、そのまま全Sを再処理できない。

```bash
uv run maskrf run --config examples/configs/paper_corrected.yaml --out tmp/raw-run-01
uv run maskrf postprocess --run tmp/raw-run-01
uv run maskrf compare --runs tmp/raw-run-01 tmp/raw-run-02 --out tmp/comparison-01
uv run maskrf convergence --config examples/configs/paper_corrected.yaml --out tmp/convergence-01
```

比較する解析は同じ周波数配列を必要とする。`raw-run-02` は比較対象の設定で別途実行した解析を指定する。各runに両励振の波形が保存されている場合、`compare` は未完了・未減衰の応答も診断用に比較できるが、比較処理の終了コードだけで格子検証を合格とは判断しない。

`comparison.json` の各行の `time_decay_confirmed` は、両励振の正常終了と減衰を確認した結果である。比較行の `both_runs_completed_and_decayed` は現在の解析と前の解析の両方を検査する。`full_s_delta_threshold_pass` は振幅・特徴周波数・全複素Sの差だけの判定、`full_s_threshold_pass` はその数値差と両解析の完了・減衰を満たす判定である。格子検証には後者を確認し、厳密な受動性や原論文との一致とは区別する。

## 6. ターゲットS21のRMSE採点

[score_mask.py](../examples/score_mask.py)は公開APIを使う利用側のスクリプトである。標準では、応答の線形振幅とターゲットの差からRMSEを計算し、単一のfloatを返す。

```text
e[k] = |S21_response(f[k])| - target_magnitude[k]
RMSE = sqrt(sum(e[k]**2) / N)
```

ターゲット周波数へ応答の振幅を直線補間し、N点を等重みで評価する。外挿は拒否し、位相は採点しない。値は無次元で、小さいほど近く、0なら評価点で一致する。CLI・Python関数とも、指標を省略するとRMSEになる。

```bash
uv run python examples/score_mask.py --mask examples/data/fig3a-mask.csv --target examples/data/lowpass-target.csv --out tmp/score-01 --reuse-run tests/fixtures/completed-run
```

このコマンドは `0.20037665494010062` を出力する。新規解析には `--reuse-run` を省略し、ネイティブ環境を設定して実行する。成功時の標準出力はfloatの1行だけで、応答は `response.json`、採点条件・値・比較振幅は `score.json`、入力ターゲットは `target.csv` に保存する。失敗時は標準エラーと非ゼロ終了になり、floatを返さない。

ターゲットCSVには次のいずれかの2列を指定する。周波数は正の昇順・重複なしとし、解析範囲内に置く。振幅とdBは有限値を必要とし、線形振幅は0以上とする。

```csv
frequency_GHz,s21_magnitude
10,1
15,1
16,0
30,0
```

もう一つの形式は `frequency_GHz,s21_dB` で、入力を `10**(dB/20)` により線形振幅へ変換する。0透過は `s21_magnitude` の0で指定する。dB形式を入力しても採点は線形振幅で行う。

[lowpass-target.csv](../examples/data/lowpass-target.csv)は10–30 GHzを1 GHz間隔で指定し、10–15 GHzの6点を1、16–30 GHzの15点を0とした理想ローパスの例である。原論文から取得したターゲット配列やHFSS応答ではなく、マスク回路による実現可能性も確認していない。

Pythonでは `examples.score_mask.score_mask(mask, target_path, out_dir, ...) -> float` を呼び出せる。取得済み応答の採点には `s21_error(response.frequency_Hz, response.s[:, 1, 0], target_frequency_Hz, target_magnitude)` を使う。関数に渡す周波数の単位はHzである。

| `--metric`／`metric` | 計算式 | 単位 |
|---|---|---|
| `rmse`（標準） | `sqrt(mean(e**2))` | 線形振幅と同じ |
| `mse` | `mean(e**2)` | 線形振幅の二乗 |
| `mae` | `mean(abs(e))` | 線形振幅と同じ |
| `max` | `max(abs(e))` | 線形振幅と同じ |

MSEとRMSEは同じ評価点・重みなら回路の順位が同じで、MAEより大きな誤差の寄与を強める。`s21_mae(...)` はMAEを計算する。最大誤差も入力した評価点だけを調べるため、点間を含めた全帯域の最大誤差は保証しない。

RMSEは候補比較の指標であり、帯域仕様の合否判定は実装していない。通過域と阻止域の寄与は点数によって変わり、局所的な仕様違反も平均で小さく見える場合がある。用途に応じて帯域ごとの挿入損失・阻止域減衰量を確認する。原論文との再現性評価では、画像から読んだHFSS振幅へのdB RMSEを用いるため、この採点値と直接比較しない。

## 7. 開発時の確認

```bash
uv sync --locked --inexact
source env.sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m unittest discover -s tests -v
uv run python tests/check_geometry.py
uv run python tests/check_network_extraction.py
uv build --out-dir tmp/dist
```

APIと採点の契約テストには `tests/fixtures/completed-run/` を使う。ネイティブソルバや過去の解析結果は不要である。形状検査、合成波形による抽出式の検査、契約テストは電磁界モデルの外部検証と区別する。新しい解析結果・確認記録は `tmp/` に実行ごとのディレクトリを作って保存する。
