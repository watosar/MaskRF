# Dall-EM マスク回路シミュレータ

16×16の金属マスクを入力し、openEMSで2ポート回路の周波数特性を計算するPythonライブラリです。S11・S12・S21・S22の複素値、振幅・位相、通過帯域の指標を返します。配布名は `dall-em`、import名は `rf_repro` です。

Guoらの論文 *Dall-EM*（IMS 2025）の図3(a)をモデル化したシミュレータで、拡散モデルの学習・マスク生成は含みません。

## インストール

Python 3.12と `uv` を使います。リポジトリのルートで実行してください。

```bash
uv sync --locked --inexact
uv run rf-repro --help
```

これで入力処理、保存済み結果の読み込み・再利用、CLIが使えます。`src/rf_repro/` をインストールする構成で、`PYTHONPATH` の設定は不要です。標準設定とマスク例はwheelに同梱します。

新規シミュレーションと波形の再処理には、openEMS・CSXCADのネイティブライブラリとPythonバインディングが必要です。Ubuntu 24.04／x86_64で、`git`、`cmake`、C/C++コンパイラ、Python 3.12開発ヘッダを用意して実行します。

```bash
mkdir -p tmp/setup
bash scripts/bootstrap.sh > tmp/setup/bootstrap.log 2>&1
source env.sh
```

固定版openEMS-Project v0.0.36とサブモジュールをビルドします。ダウンロード・ビルド用ファイルは `tmp/native-build/`、導入済みライブラリとwheelは `.native/`、Python環境は `.venv/` に保存します。約5 GBの空き領域が必要です。Ubuntuの依存パッケージはダウンロード・展開のみ行い、システムにはインストールしません。

ネイティブバインディングはローカルビルドしたwheelから追加導入するため、環境の再同期には `uv sync --locked --inexact` を使ってください。`.venv` を作り直した場合は `uv pip install --python .venv/bin/python .native/wheels/*.whl` で再導入できます。実際のネイティブ版はopenEMS 0.0.36／CSXCAD 0.6.3ですが、上流wheelのメタデータは0.0.33／0.6.2です。

`env.sh` は共有ライブラリの参照先を設定します。既存の外部導入先を使う場合は、sourceする前に `RF_REPRO_NATIVE` をそのパスへ設定してください。

## CLI

```bash
source env.sh
uv run rf-repro evaluate --mask examples/data/fig3a-mask.csv --out tmp/my-circuit
# python -m からも同じCLIを呼べます。
uv run python -m rf_repro --help
# 形状・メッシュの確認のみ。
uv run rf-repro inspect --config examples/configs/paper_corrected.yaml --out tmp/inspect-paper
```

`--out` には未使用のディレクトリを指定します。新規解析は同期処理で、標準の細密格子では数十分以上かかります。成功時は標準出力と出力先の `response.json` に結果を返します。失敗時は非ゼロ終了とエラーJSONになり、不完全な結果を成功として返しません。

既存の解析を再利用する場合は `--reuse-run /path/to/completed-run` を指定します。入力マスクと解析・計測設定の一致を検査します。ソルバを使わずに試す例です。

```bash
uv run rf-repro evaluate --mask examples/data/fig3a-mask.csv --out tmp/reuse-example --reuse-run tests/fixtures/completed-run
```

`run`、`postprocess`、`compare`、`convergence` も `rf-repro` から利用できます。条件変更には `--config` でYAMLを指定します。YAMLの `geometry.file` はそのYAMLを基準とする相対パスです。

## Python API

```python
import numpy as np
from rf_repro import evaluate_mask, load_response

mask = np.loadtxt("examples/data/fig3a-mask.csv", delimiter=",", dtype=int)
result = evaluate_mask(mask, "tmp/python-example")
frequency_GHz = result.frequency_Hz / 1e9
s21 = result.s[:, 1, 0]  # 周波数、出力ポート、入力ポートの順
print(result.metrics["first_downward_3dB_GHz"])
saved = load_response("tmp/python-example")
```

`evaluate_mask(mask, out_dir, *, config_path=None, reuse_run=None)` は標準で10–30 GHzの401点を計算します。`result.s` は複素配列 `(周波数点数, 2, 2)`、`result.to_dict()` はJSON化可能な辞書です。両方向の正常終了と減衰条件を満たさない結果は `SimulationError` になります。

| 項目 | 仕様 |
|---|---|
| 入力 | 16×16のNumPy配列、二次元リスト、CSV、JSON配列、白黒PNG |
| マスク値 | 1＝金属、0＝空白。PNGは黒＝金属。灰色や非二値入力は拒否 |
| 向き | 行0が+y、列0が−x、中心原点 |
| 標準条件 | 1セル0.125 mm、2 mm角。基板・給電・短絡は設定から付加 |
| JSON | 実部・虚部・dB振幅・度単位の位相、回路指標、マスク、実効設定、保存先 |

18×18の端子込み学習表現から16×16への自動変換は行いません。APIによる単一評価はメッシュ収束を自動検査しません。再利用応答は元の解析ディレクトリを参照するため、そのディレクトリも保持してください。

## 開発・検証

```bash
uv run python -m unittest discover -s tests -v
uv run python tests/check_geometry.py
uv run python tests/check_network_extraction.py
uv build --out-dir tmp/dist
```

テスト用の保存済み応答は `tests/fixtures/completed-run/` に含めています。契約テストにネイティブソルバや過去の `tmp/` は不要です。新たな検証出力は `tmp/` に保存します。

| 場所 | 内容 |
|---|---|
| [src/rf_repro](src/rf_repro/) | シミュレータ、Python API、CLI、同梱標準設定 |
| [pyproject.toml](pyproject.toml)・[uv.lock](uv.lock) | ビルド設定・Python依存管理 |
| [examples](examples/) | 編集して使える設定・マスク例 |
| [scripts](scripts/) | ネイティブ環境の構築手順 |
| [tests](tests/) | API契約テスト・検証用fixture |
| tmp/ | 作業用ファイル、実行結果、確認記録 |

従来の解析結果・レポートは [tmp/rf-repro/REPORT.md](tmp/rf-repro/REPORT.md) に残しています。過去の文書・スクリプト内のパスは実行当時の記録です。図3(a)の採用形状では最後の2段階の最大複素S差0.011985を確認しましたが、厳密な受動性と論文条件の完全一致は未達です。これらの記録はライブラリの実行には不要です。
