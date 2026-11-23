# Saved data for the reproduction report

[日本語](README.ja.md)

This directory contains the data behind the numerical results and figures in the reproduction report. The run with internal shorts, uniform-width feeds, and nine subdivisions per mask pixel corresponds to the bundled YAML. Its results are available as a test fixture and as a Touchstone file. [Reproduction report](../reproduction-report.md) · [Completed response fixture](../../tests/fixtures/README.md) · [Touchstone file](adopted-network.s2p)

| Topic | Saved data |
|---|---|
| Conditions and digitization of the paper | [Conditions and assumptions](conditions.md), [HFSS curve](paper-hfss.csv), [Extraction settings](paper-extraction.json), [Measured grid](grid-measurements.json) |
| External shorts and feed transitions | [Summary of six cases](terminal-study-summary.csv), [S21 curves for two feed widths](terminal-feed-width-s21.csv), [Touchstone for external shorts and narrow feed ends, four subdivisions per pixel](fig3a-outer-terminals.s2p) |
| Comparison with prior work | [Mask and extraction checks](prior-art-verification.json), [COMSOL curves](comsol-digitized.csv), [COMSOL digitization and comparison metrics](comsol-metrics.json) |
| Mesh and completion checks | [Grid comparison](mesh-comparison.json), [Convergence audit](convergence-audit.json) |
| Material sensitivity | [Experiment settings](material-experiment.json), [Material and grid audit](material-audit.json), [Summary of all cases](material-summary.csv), [Comparison with the paper](material-paper-selection.json), [Refinement comparison](material-refinement.json), [Re-extraction checks](material-extraction-verification.json) |
| Published figures and numerical results | [Comparison and power metrics for the selected model](report-metrics.json), [S21 curves for four material cases](material-s21-curves.csv) |
| Target scoring | [Default RMSE verification](target-score-verification.json) |

The published HFSS curve and the prior COMSOL curves were digitized from images. The corresponding JSON files record the digitization range and the uncertainty due to image coordinates. The report's references identify the original paper and prior implementations.

## Data sources and redistribution

The MaskRF license covers the original software. Redistribution terms for the material extracted from the following third-party figures are unverified. This also applies to figures that redraw the digitized traces or show the recovered mask, including copies in earlier Git commits. [MaskRF license](../../LICENSE) · [IEEE guidance on reuse](https://journals.ieeeauthorcenter.ieee.org/choose-a-publishing-agreement/avoid-infringement-upon-ieee-copyright/)

| Material | Source | Location |
|---|---|---|
| 16×16 mask | Metal pattern read from Guo et al., Fig. 3(a). [Paper](https://doi.org/10.1109/IMS40360.2025.11103838) | [Reproduction input](../../examples/data/fig3a-mask.csv) and [test fixture](../../tests/fixtures/completed-run/mask.csv) |
| HFSS S21 reference | Magnitudes digitized from the purple trace in Guo et al., Fig. 3(a). [Paper](https://doi.org/10.1109/IMS40360.2025.11103838) | [Readings](paper-hfss.csv) and [extraction settings](paper-extraction.json) |
| Earlier COMSOL comparison | S11 and S21 magnitudes digitized from the plot in `jwt625/Obsidian-Journals`. [Source image](https://github.com/jwt625/Obsidian-Journals/blob/67227f7579e27259e75e9fadcefe345f856e5137/10-30GHz.png) | [Readings](comsol-digitized.csv) and [comparison metrics](comsol-metrics.json) |

The Python package ships an original example mask with a straight metal strip. The Touchstone files contain the project's own openEMS simulation results. The reproduction report identifies which figures display the digitized HFSS trace alongside those results. [Bundled example mask](../../src/maskrf/data/example-mask.csv) · [Reproduction report](../reproduction-report.md)

## Feeds and shorts

The coarse-grid study with internal shorts varied the width at the feed ends. The results include the comparison metrics, the fixed settings, and the verification checks. A separate test removed the shorts. It failed to reach the decay criterion, so it yielded no valid full S-matrix. [Comparison metrics](feed-comparison.json) · [Fixed settings](feed-controlled-variables.json) · [Verification checks](feed-final-checks.json) · [Completion status](no-shorts-status.json)

## Provenance and figure generation

The provenance file records the original locations of the data, the SHA-256 hashes of saved files, the conversion used for the material curves, and the SHA-256 of the core implementation used for the selected model. Entries under `tmp/` and absolute paths refer to the original runs. Repeating extraction from waveforms or digitization from images requires the original waveforms, logs, images, and work records. [Data provenance](provenance.json)

The plotting script generates the HFSS comparison for internal shorts with uniform-width feeds and the material comparison from the saved data. Run it from the repository root to save the figures to the specified directory. [Plotting script](../../examples/plot_report.py)

```bash
source env.sh
uv run python examples/plot_report.py --out tmp/report-figures
```
