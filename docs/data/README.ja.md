# 検証レポートの保存データ

[English](README.md)

このディレクトリは、[検証レポート](../reproduction-report.ja.md)の掲載数値と図を確認するためのデータを収録する。同梱の標準YAMLに対応する内側短絡・一定幅給電の9分割結果は、[完了済み応答のfixture](../../tests/fixtures/README.ja.md)と[Touchstone](adopted-network.s2p)に保存している。

| 対象 | 保存データ |
|---|---|
| 原論文の条件と画像読取 | [条件・仮定](conditions.ja.md)、[HFSS曲線](paper-hfss.csv)、[抽出条件](paper-extraction.json)、[分割の計測値](grid-measurements.json) |
| 外周短絡と給電接続の比較 | [6ケースの集計CSV](terminal-study-summary.csv)、[給電幅2条件のS21曲線](terminal-feed-width-s21.csv)、[外周短絡・細い給電接続の4分割Touchstone](fig3a-outer-terminals.s2p) |
| 先行実装との照合 | [マスク・抽出式の検査](prior-art-verification.json)、[COMSOL曲線](comsol-digitized.csv)、[COMSOL読取と比較指標](comsol-metrics.json) |
| 格子と終了状態の検査 | [格子比較](mesh-comparison.json)、[監査](convergence-audit.json) |
| 材料の感度試験 | [実験条件](material-experiment.json)、[材料・格子の監査](material-audit.json)、[全ケース一覧](material-summary.csv)、[原論文に対する採点](material-paper-selection.json)、[細分化比較](material-refinement.json)、[再抽出の検査](material-extraction-verification.json) |
| 掲載数値と図 | [採用モデルの比較・電力指標](report-metrics.json)、[材料4条件のS21曲線](material-s21-curves.csv) |
| ターゲット採点 | [標準RMSEの確認結果](target-score-verification.json) |

原論文のHFSS曲線と先行COMSOL曲線は画像からの読取値で、ソルバの数値出力原本ではない。読取範囲と座標由来の誤差は各JSONに記載する。原論文と先行実装の出典URLはレポートの参考資料にまとめている。

## 給電・短絡

内側短絡で給電端の幅を変えた粗格子試験は、[比較指標](feed-comparison.json)、[固定条件](feed-controlled-variables.json)、[検査結果](feed-final-checks.json)を保存する。短絡除去の試験は[終了状態](no-shorts-status.json)に示すとおり減衰未達で、有効な全Sを得ていない。

## 出典と再生成

[provenance.json](provenance.json)には、整理前の保存場所、保存データのSHA-256、材料曲線への変換式、採用時のコア実装のSHA-256を記録する。JSON内の `tmp/` や絶対パスは生成当時の記録であり、現在の読込先ではない。ソルバの原波形・ログ、画像原本、作業記録はこのディレクトリに含めないため、それらを使った再抽出・再読取の検査は収録データだけでは反復できない。

内側短絡・一定幅給電のHFSS比較図と材料比較図は、[描画コード](../../examples/plot_report.py)で保存データから生成できる。リポジトリのルートで次を実行すると、図を指定先へ保存する。

```bash
source env.sh
uv run python examples/plot_report.py --out tmp/report-figures
```
