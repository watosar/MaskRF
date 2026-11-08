# MaskRF：金属マスクのRF応答解析

16×16の二値金属マスクから、openEMSで2ポート回路の複素Sパラメータを計算するPythonライブラリです。配布名・import名・CLIはいずれも `maskrf` です。

NumPy配列・CSV・JSON・白黒PNGを受け取り、基板・給電・短絡を含むモデルを解析します。S11・S12・S21・S22をCSV・Touchstone・JSONで保存でき、ターゲットS21とのRMSEを返す採点スクリプトも用意しています。

Guoらの論文 *Dall-EM*（IMS 2025）図3(a)を基準に検証していますが、原論文の定量再現は未達で、任意マスクの精度も未確認です。採用条件と検証結果は[検証レポート](docs/reproduction-report.md)を参照してください。

## 導入

Python 3.12と `uv` を使い、以下のコマンドはリポジトリのルートで実行します。

新規FDTD解析、形状・メッシュの生成、保存波形の再処理には、openEMS・CSXCADのPythonバインディング（PythonからC/C++の実装を呼び出す拡張モジュール）と、`libopenEMS.so`・`libCSXCAD.so` などの共有ライブラリが必要です。MaskRFはPythonバインディング経由で解析処理を呼び出し、`openEMS` 実行ファイルをコマンドとして起動することはありません。

構築スクリプトの対象環境はUbuntu 24.04／x86_64です。`uv`、`git`、`cmake`、C/C++コンパイラ、Python 3.12開発ヘッダと、約5 GBの空き領域を用意してください。

```bash
uv sync --locked --inexact
mkdir -p tmp/setup
bash scripts/bootstrap.sh > tmp/setup/bootstrap.log 2>&1
source env.sh
```

[bootstrap.sh](scripts/bootstrap.sh)はopenEMS-Project v0.0.36の固定コミットとサブモジュールから、共有ライブラリとPythonバインディングをビルドします。共有ライブラリと依存するUbuntuパッケージは `.native/` へ展開し、システムへはインストールしません。Pythonバインディングは `.native/wheels/` にwheelを作成し、`.venv/` へインストールします。構築用ファイルは `tmp/native-build/` に保存します。他のOS・CPU向けの構築手順は検証していません。

`env.sh` は共有ライブラリを読み込めるように `LD_LIBRARY_PATH` を設定し、Matplotlibの作業先も指定します。openEMS・CSXCADの共有ライブラリを `.native/` 以外へ導入した場合は、sourceする前に `MASKRF_NATIVE` をその導入先のルートへ設定してください。

openEMS・CSXCADのPythonバインディングを削除しないよう、環境の同期には `uv sync --locked --inexact` を使います。`.venv` を作り直した場合は、保存済みwheelを再導入してください。

```bash
uv sync --locked --inexact
uv pip install --python .venv/bin/python .native/wheels/*.whl
source env.sh
```

この手順がビルドするソースのバージョンはopenEMS 0.0.36／CSXCAD 0.6.3です。Pythonバインディングのwheelメタデータは0.0.33／0.6.2なので、導入版の確認にはビルドしたソースの版も使います。

## 新規解析

```bash
source env.sh
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --out tmp/example-response
```

両ポートを独立に励振し、応答JSONを標準出力と `tmp/example-response/response.json` に保存します。標準設定では数十分以上かかります。出力先は未使用のディレクトリにしてください。

新規解析とターゲット採点をまとめて行う場合は、次のスクリプトを使います。

```bash
uv run python examples/score_mask.py --mask examples/data/fig3a-mask.csv --target examples/data/lowpass-target.csv --out tmp/example-score
```

このスクリプトも新規解析を実行し、同梱の理想ローパスターゲットに対する線形振幅のRMSEを1行で出力します。引数は[evaluateのオプション](docs/usage.md#evaluate-のオプション)と[採点スクリプトのオプション](docs/usage.md#採点スクリプトのオプション)、Python APIや入力形式は[利用方法](docs/usage.md)に記載しています。

## 保存済み結果の読み込み

解析済みの結果は `load_response()` で読み込みます。

```python
from maskrf import load_response

response = load_response("tmp/example-response")
s21 = response.s[:, 1, 0]
```

読み込みだけならopenEMS・CSXCADは不要です。保存済み応答を採点する方法は[利用方法](docs/usage.md#保存済み応答の採点)に記載しています。

## 詳細な使い方と検証結果

| 文書 | 内容 |
|---|---|
| [利用方法](docs/usage.md) | マスクと設定、Python API、CLIと保存結果、RMSE採点 |
| [検証レポート](docs/reproduction-report.md) | 背景と目的、採用モデル、検証結果と未達事項、参考資料 |
| [検証データ](docs/data/README.md) | レポートの掲載数値と図を確認する入力データ・出典 |

## 開発時の確認

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

テストには[同梱の保存済み応答](tests/fixtures/README.md)を使うため、openEMS・CSXCADの導入や過去の解析結果は不要です。

## ディレクトリ構成

| 場所 | 内容 |
|---|---|
| [src/maskrf](src/maskrf/) | ライブラリ、API、CLI、同梱標準設定とマスク |
| [examples](examples/) | 利用側のスクリプト、編集用設定、マスクとターゲット例 |
| [tests](tests/) | 保守するテストと保存済み応答のfixture |
| [scripts](scripts/) | openEMS・CSXCADのビルドと導入 |
| [docs](docs/) | 現在の利用仕様と検証結果、掲載図 |
| `tmp/`（Git管理外） | 作業用ファイル、実行結果、検証の証拠 |
