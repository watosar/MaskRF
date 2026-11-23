# 利用方法

導入とopenEMS・CSXCADの構築は[README](../README.md)を参照する。以下のコマンドはリポジトリのルートで実行し、Pythonの実行・環境管理には `uv` を使う。

## 1. マスクと設定

| 項目 | 仕様 |
|---|---|
| 入力 | 16×16のNumPy配列、二次元リスト、CSV、JSON配列、白黒PNG |
| 数値 | 1＝金属、0＝空白。boolも使用可。非二値・非数値入力は拒否 |
| PNG | 黒＝金属、白＝空白。灰色は拒否 |
| 座標 | 行0が+y、列0が−x。マスク中心が原点 |
| 標準寸法 | ピッチ0.125 mm、内側2 mm角 |
| 付加する構造 | 設定に従う基板、裏面GND、給電線、短絡 |

CSVはヘッダなしの16行×16列、JSONは二次元配列そのものを入力する。18×18の端子込み表現の自動変換や、孤立金属の除去、角接触の接続・切断などの形状修正は行わない。

標準設定は[同梱YAML](../src/maskrf/configs/paper_corrected.yaml)にある。条件を変更する場合は[編集用設定例](../examples/configs/paper_corrected.yaml)をコピーし、APIの `config_path` またはCLIの `--config` に渡す。設定の長さはmm、周波数は `frequency_GHz: [開始, 終了, 点数]` で指定する。

`evaluate_mask` では引数 `mask`、`maskrf evaluate` と `maskrf inspect` では `--mask` でマスクを指定できる。マスクの評価には `geometry.kind: mask` と `solver.excitations: [1, 2]` が必要である。`run`・`convergence` または `inspect --config` でYAMLからマスクを指定する場合は、`geometry.file` にCSVまたは白黒PNGのパスを書く。相対パスの起点はYAMLを置いたディレクトリである。

材料・形状・格子の変更には個別の精度確認が必要である。図3(a)について確認した格子差を、変更後の設定や任意マスクの誤差上限として使わない。

### 短絡と給電線の設定

CSVは中央16×16の金属パターンを指定する。短絡と給電線の位置・寸法は設定YAMLで指定する。マスク中心を原点とし、右が+x、上が+yである。

| 設定 | 内容 |
|---|---|
| `geometry.shorts[].xy_mm`、`width_mm` | 短絡ごとの中心 `[x, y]` と、基板を貫通する正方形の導体の一辺 |
| `geometry.shorts[].pad_width_mm` | 任意。短絡と同じ中心に置く上面金属パッドの一辺。マスク外に短絡を置く場合は、パッドがマスク端の金属に接するように位置と幅を指定する |
| `ports.y_mm`、`ports.width_mm` | 左右の給電線の中心 `[左のy, 右のy]` と、左右共通の線幅 |
| `ports.neck.length_mm`、`width_mm` | 任意。マスクに接する側の区間の長さと幅。左右に共通で、幅は `ports.width_mm` 以下とする。区間の長さは `feed_length_mm` に含まれ、励振と測定は外側の区間に置く |

[図3(a)の外周短絡と細い給電接続の設定例](../examples/configs/paper_outer_terminals.yaml)では、2か所の外周パッドと、長さ・幅とも0.125 mmの給電先端を指定している。形状確認と解析には同じYAMLを渡す。

```bash
uv run maskrf inspect --mask examples/data/fig3a-mask.csv --config examples/configs/paper_outer_terminals.yaml --out tmp/outer-terminals-inspect
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --config examples/configs/paper_outer_terminals.yaml --out tmp/outer-terminals-run
```

給電幅を変更して給電線の縁の格子検査に失敗した場合は、`mesh.local_mm` を小さくして `inspect` で確認する。

## 2. Python API

公開APIは `evaluate_mask`、`load_response`、戻り値の `CircuitResponse`、解析失敗を表す `SimulationError` である。

```python
from maskrf import evaluate_mask

response = evaluate_mask(
    "examples/data/fig3a-mask.csv",
    "tmp/python-example",
)
frequency_GHz = response.frequency_Hz / 1e9
s21 = response.s[:, 1, 0]
print(response.metrics["first_downward_3dB_GHz"])
```

`evaluate_mask(mask, out_dir, *, config_path=None)` は同期処理である。毎回、両ポートを独立に励振して新規解析するため、openEMS・CSXCADのPythonバインディングと共有ライブラリが必要になる。未導入なら `(Y/n)` で導入を確認し、承諾後にインストールして解析を続ける。拒否または入力なしの終了では `SimulationError` となり、出力先は作成しない。標準設定の解析は数十分以上かかる。出力先は未使用のディレクトリにする。

| 戻り値 | 内容 |
|---|---|
| `frequency_Hz` | Hz単位の周波数配列。標準は10–30 GHzの401点 |
| `s` | 複素配列 `(周波数点数, 2, 2)`。`s[:, i-1, j-1]` がSij |
| `metrics` | S21の帯域指標、下降側−3 dB交差、相反性・電力比・受動性の指標など |
| `settings`・`mask` | 解析・計測条件と入力マスク |
| `run_dir` | 解析結果の所在 |
| `to_dict()` | 実部・虚部、dB振幅、度単位の位相、指標を含むJSON化可能な辞書 |

### 保存結果の読み込み

`load_response(run_dir)` は完了済み解析または `evaluate_mask` の出力から応答を読み込む。解析や波形の再処理は行わないため、openEMS・CSXCADは不要である。

```python
from maskrf import load_response

saved = load_response("tmp/python-example")
s21 = saved.s[:, 1, 0]
```

両励振の正常終了・減衰、周波数配列、全S成分の有限値を検査する。減衰を満たさない解析は `SimulationError` として拒否する。`evaluate_mask` と `load_response` の呼び出しではメッシュ収束を調べず、厳密な受動性違反を理由とする自動排除も行わない。これらは指標と追加検証で判断する。

## 3. CLIと保存結果

```bash
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --out tmp/circuit-01
```

### evaluate のオプション

| オプション | 必須 | 意味 |
|---|---|---|
| `--mask PATH` | 必須 | 評価する16×16マスク。CSV・JSON・白黒PNGのいずれか |
| `--out DIR` | 必須 | 入力・設定と応答を保存する未使用のディレクトリ |
| `--config YAML` | 任意 | 解析設定。省略時は[同梱の標準設定](../src/maskrf/configs/paper_corrected.yaml)を使う |

CLIは `uv run python -m maskrf` からも呼び出せる。

### 保存される結果

`evaluate` は成功時に応答JSONを標準出力と `response.json` に返す。失敗時は非ゼロ終了となり、エラーJSONを標準エラーに出す。解析開始後の失敗は `error.json` にも残す。入力やソルバのログは出力先へ保存する。

初回の導入確認と進捗案内は標準エラーに表示する。導入に失敗した場合はXDGの状態ディレクトリに保存したログの場所を示す。保存先と必要なツールは[README](../README.md#導入)を参照する。

| 主なファイル | 内容 |
|---|---|
| `mask.csv`・`request.yaml`・`request.json` | 入力マスク、実際に渡した設定、入力のハッシュと形状監査 |
| `response.json` | 完了した応答と指標、解析ディレクトリへの参照 |
| `execution.log` | 新規解析プロセスのログ |
| `run/effective.json`・`run/status.json` | 新規解析の実効設定と各励振の終了・減衰判定 |
| `run/sparameters.csv`・`run/network.s2p` | 全複素SのCSVとTouchstone |
| `run/solver-*.log`・`run/excite-*/` | 励振ごとのログと波形 |

### inspect で回路形状を確認する

`inspect` は解析モデルと計算格子を組み立て、励振を実行せずに形状図を出力する。次の例はマスクCSVと同梱の標準設定を使う。モデルの組み立てにはopenEMS・CSXCADのPythonバインディングと共有ライブラリが必要で、未導入の場合は `(Y/n)` で導入を確認する。

```bash
uv run maskrf inspect --mask examples/data/fig3a-mask.csv --out tmp/inspect-01
```

| オプション | 必須 | 意味 |
|---|---|---|
| `--mask PATH` | `--config` 省略時に必須 | 描画する16×16マスク。CSV・JSON・白黒PNGのいずれか |
| `--config YAML` | `--mask` 省略時に必須 | 形状と計算格子を定義する解析設定。省略時は同梱の標準設定 |
| `--out DIR` | 任意 | 出力先。省略時は `tmp/maskrf-inspect` |

両方を指定すると、金属パターンは `--mask` のファイルから、基板・給電線などの条件は `--config` のYAMLから読み込む。設定YAMLにマスクのパスが含まれていれば、`inspect --config YAML` でも描画できる。

| 出力ファイル | 内容 |
|---|---|
| `geometry.png` | 金属パターン、給電線、測定面、短絡位置を示す平面図と、基板・GNDの概略断面図 |
| `geometry.xml` | openEMS・CSXCADで使用する形状のXML |
| `mesh.json` | 各軸の格子座標、セル数、給電線の縁における格子の確認結果 |
| `geometry-audit.json` | マスクの寸法、金属セル数、接続成分数など |

標準出力には格子座標を除いた `mesh.json` の内容をJSONで表示する。

### 解析・比較コマンド

`run` は設定YAMLを使って新規解析を実行する。`convergence` は設定の `convergence` に列挙した各格子で新規解析し、段階間の差を計算する。`compare` と `postprocess` は保存波形を再処理するため、openEMS・CSXCADのPythonバインディングと共有ライブラリも必要になる。

`run` と `convergence` は、各励振の正常終了と減衰を確認する。終了コード0でも減衰条件未達なら状態とログを保存して非ゼロ終了し、後続の励振・格子解析と通常の後処理へは進まない。`postprocess` は設定した全励振の波形が保存されている場合に診断用の再処理として使えるが、その処理の成功は解析の正常終了・減衰を意味しない。第1励振で停止して第2励振の波形がないrunは、そのまま全Sを再処理できない。

```bash
uv run maskrf run --config examples/configs/paper_corrected.yaml --out tmp/raw-run-01
uv run maskrf postprocess --run tmp/raw-run-01
uv run maskrf compare --runs tmp/raw-run-01 tmp/raw-run-02 --out tmp/comparison-01
uv run maskrf convergence --config examples/configs/paper_corrected.yaml --out tmp/convergence-01
```

比較する解析は同じ周波数配列を必要とする。`raw-run-02` は比較対象の設定で別途実行した解析を指定する。各runに両励振の波形が保存されている場合、`compare` は未完了・未減衰の応答も診断用に比較できるが、比較処理の終了コードだけで格子検証を合格とは判断しない。

`comparison.json` の各行の `time_decay_confirmed` は、両励振の正常終了と減衰を確認した結果である。比較行の `both_runs_completed_and_decayed` は現在の解析と前の解析の両方を検査する。`full_s_delta_threshold_pass` は振幅・特徴周波数・全複素Sの差だけの判定、`full_s_threshold_pass` はその数値差と両解析の完了・減衰を満たす判定である。格子検証には後者を確認し、厳密な受動性や原論文との一致とは区別する。

## 4. ターゲットS21のRMSE採点

[score_mask.py](../examples/score_mask.py)は公開APIを使う利用側のスクリプトである。標準では、応答の線形振幅とターゲットの差からRMSEを計算し、単一のfloatを返す。

```text
e[k] = |S21_response(f[k])| - target_magnitude[k]
RMSE = sqrt(sum(e[k]**2) / N)
```

ターゲット周波数へ応答の振幅を直線補間し、N点を等重みで評価する。外挿は拒否し、位相は採点しない。値は無次元で、小さいほど近く、0なら評価点で一致する。CLI・Python関数とも、指標を省略するとRMSEになる。

```bash
uv run python examples/score_mask.py --mask examples/data/fig3a-mask.csv --target examples/data/lowpass-target.csv --out tmp/score-01
```

このコマンドは新規解析と採点を実行し、openEMS・CSXCADが未導入なら `(Y/n)` で導入を確認する。成功時の標準出力はfloatの1行だけで、応答は `response.json`、採点条件・値・比較振幅は `score.json`、入力ターゲットは `target.csv` に保存する。失敗時は標準エラーと非ゼロ終了になり、floatを返さない。

### 採点スクリプトのオプション

| オプション | 必須 | 意味 |
|---|---|---|
| `--mask PATH` | 必須 | 評価する16×16マスク。CSV・JSON・白黒PNGのいずれか |
| `--target CSV` | 必須 | 比較するターゲット。列と単位は後述 |
| `--out DIR` | 必須 | 応答と採点結果を保存する未使用のディレクトリ |
| `--metric NAME` | 任意 | `rmse`・`mse`・`mae`・`max`。省略時は `rmse` |
| `--config YAML` | 任意 | 解析設定。省略時は同梱の標準設定を使う |

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

Pythonでは `examples.score_mask.score_mask(mask, target_path, out_dir, ...) -> float` を呼び出せる。この関数も新規解析と採点を実行する。

| `--metric`／`metric` | 計算式 | 単位 |
|---|---|---|
| `rmse`（標準） | `sqrt(mean(e**2))` | 線形振幅と同じ |
| `mse` | `mean(e**2)` | 線形振幅の二乗 |
| `mae` | `mean(abs(e))` | 線形振幅と同じ |
| `max` | `max(abs(e))` | 線形振幅と同じ |

MSEとRMSEは同じ評価点・重みなら回路の順位が同じで、MAEより大きな誤差の寄与を強める。`s21_mae(...)` はMAEを計算する。最大誤差も入力した評価点だけを調べるため、点間を含めた全帯域の最大誤差は保証しない。

RMSEは候補比較の指標であり、帯域仕様の合否判定は実装していない。通過域と阻止域の寄与は点数によって変わり、局所的な仕様違反も平均で小さく見える場合がある。用途に応じて帯域ごとの挿入損失・阻止域減衰量を確認する。原論文との再現性評価では、画像から読んだHFSS振幅へのdB RMSEを用いるため、この採点値と直接比較しない。

### 保存済み応答の採点

保存済み結果は `load_response()` で読み込み、`s21_error()` に渡して採点する。この処理では解析を実行せず、openEMS・CSXCADも使わない。関数に渡す周波数の単位はHzである。

```python
from pathlib import Path

from maskrf import load_response
from examples.score_mask import parse_target_csv, s21_error

response = load_response("tmp/circuit-01")
target_frequency_Hz, target_magnitude = parse_target_csv(
    Path("examples/data/lowpass-target.csv").read_text()
)
value = s21_error(
    response.frequency_Hz,
    response.s[:, 1, 0],
    target_frequency_Hz,
    target_magnitude,
)
print(value)
```
