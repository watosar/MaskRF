# Completed response fixture

[日本語](README.ja.md)

`completed-run/` contains a response generated for Fig. 3(a) using the selected lossless RO4350B-equivalent model with nine subdivisions per pixel. Both excitations completed and met the decay criterion. The fixture checks all 401 frequency points, the order and preservation of the S-parameter values, saved-response loading, and target scoring. The tests run without openEMS, CSXCAD, or prior outputs in `tmp/`.

The fixture contains five files: `effective.json`, `status.json`, `metrics.json`, `sparameters.csv`, and `mask.csv`. It supports checks on the saved response. Waveform reprocessing and Touchstone checks require the files from a full run. The Touchstone path exposed by the API refers to a file outside the fixture's contents.

Absolute paths in `effective.json` and `status.json` document the original run. `load_response` reads from the fixture directory supplied to it. The API tests for new runs stub only the solver invocation. Production code still saves the input and configuration and loads the response.

The fixture comes from `paper-refine-9-01`. Matching it verifies numerical preservation. The report describes the comparison with the paper, the validation scope, and the physical limits of the model. [Reproduction report](../../docs/reproduction-report.md)
