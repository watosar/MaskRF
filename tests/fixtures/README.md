# 完了済み応答のfixture

`completed-run/` は、図3(a)の採用設定（無損失RO相当・画素9分割）で正常終了・減衰を確認した応答のfixtureです。全401点・全S成分の順序、数値の保持、保存済み応答の読み込み、ターゲット採点を検査します。openEMS・CSXCADの導入や過去の `tmp/` は不要です。

`effective.json`、`status.json`、`metrics.json`、`sparameters.csv`、`mask.csv` の5ファイルを収録しています。ソルバ波形とTouchstoneファイルは含まないため、波形の再処理やTouchstoneの検査には使えません。APIが返すTouchstoneの参照先も、このfixtureには実体がありません。

`effective.json` と `status.json` 内の絶対パスは生成元の記録です。`load_response` は指定されたfixtureディレクトリを読みます。新規解析APIのテストでは、ソルバの実行部分だけを差し替え、入力・設定の保存と応答の読み込みを本体の処理で検査します。

生成元は `paper-refine-9-01`、検証範囲と物理的な限界は[検証レポート](../../docs/reproduction-report.md)に記載しています。fixtureとの一致は数値の保持を検査するもので、原論文との一致や任意マスクの精度を保証するものではありません。
