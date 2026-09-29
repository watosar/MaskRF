# 完了済み応答のfixture

`completed-run/` は移行前の `tmp/rf-repro/results/paper-refine-9-01/` から、API契約テストに必要な5ファイルを保存したものです。全401点・全S成分の順序、再利用条件、数値の保持を検査します。ソルバ波形は含まず、再解析には使いません。

`effective.json` と `status.json` 内の絶対パスは実行当時の記録です。`load_response` は指定されたfixtureディレクトリのデータを読み、マスク一致判定から元のパスを除外します。
