# MaskRF · RF response analysis for metal masks

[日本語](README.ja.md)

MaskRF is a Python library that uses openEMS to compute the complex S-parameters of a two-port circuit from a 16×16 binary metal mask. The distribution, import, and CLI names are all `maskrf`.

MaskRF accepts NumPy arrays, CSV, JSON, and black-and-white PNG files. It models the substrate, feed lines, and shorts, and saves S11, S12, S21, and S22 in CSV, Touchstone, and JSON. A scoring script computes the RMSE against a target S21 response.

We simulated the circuit in Fig. 3(a) of Guo et al., *Dall-EM* (IMS 2025), in openEMS using the reproduction configuration with peripheral shorts and narrow feed connections. The RMSE of S21 magnitude in dB against the digitized HFSS curve was 0.58 dB across 16 points from 10.5 to 18 GHz at 0.5 GHz intervals. At 10.5 GHz, the openEMS result was 0.88 dB below the digitized HFSS value. [Reproduction command](#reproducing-fig-3a) · [Comparison results](docs/reproduction-report.md)

## Installation

Use Python 3.12 and `uv`. Run the commands below from the repository root.

New FDTD runs, geometry and mesh generation, and reprocessing saved waveforms require the openEMS and CSXCAD Python bindings and shared libraries such as `libopenEMS.so` and `libCSXCAD.so`. The bindings let MaskRF call the C/C++ solver directly. The standalone `openEMS` executable is optional at runtime.

The automatic build targets Ubuntu 24.04 on x86_64. It requires `uv`, `git`, `cmake`, a C/C++ compiler, the Python 3.12 development headers, and about 5 GB of free space.

```bash
uv sync --locked --inexact
```

If MaskRF cannot load openEMS or CSXCAD when you first run an analysis, it asks whether to install them using a `(Y/n)` prompt. Press Enter or type `y` to install and continue. Typing `n` or reaching the end of input cancels the operation. Displaying help and loading saved responses work even when the bindings are absent.

When you accept the installation, MaskRF builds the shared libraries and Python bindings from a pinned openEMS-Project v0.0.36 commit. It extracts the required Ubuntu packages into user directories and installs the bindings into the Python environment running the command. The installation prompt displays the locations of the installation and the log.

MaskRF follows the XDG Base Directory specification. [XDG Base Directory specification](https://specifications.freedesktop.org/basedir/latest/)

| Contents | Directory | Default when the variable is unset |
|---|---|---|
| Shared libraries and wheels | `$XDG_DATA_HOME/maskrf/openems-0.0.36/` | `~/.local/share/maskrf/openems-0.0.36/` |
| Downloads and build files | `$XDG_CACHE_HOME/maskrf/openems-0.0.36/` | `~/.cache/maskrf/openems-0.0.36/` |
| Installation logs | `$XDG_STATE_HOME/maskrf/` | `~/.local/state/maskrf/` |

An empty XDG variable or a relative path also selects the default location. MaskRF configures shared library loading.

Use `uv sync --locked --inexact` to sync the environment and keep the installed bindings. If you recreate the Python environment, the next analysis prompts for installation again. MaskRF reuses the saved wheels when the shared libraries and wheels are already available.

This procedure builds openEMS 0.0.36 and CSXCAD 0.6.3. The binding wheels report versions 0.0.33 and 0.6.2 respectively, so check the source versions when identifying the installation.

## Running a new analysis

```bash
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --out tmp/example-response
```

This command uses the bundled settings with interior shorts and constant-width feeds. MaskRF excites the two ports independently, writes the response JSON to standard output, and saves it as `tmp/example-response/response.json`. The run usually takes tens of minutes or more. Choose an output directory that does not yet exist.

To run a new analysis and score the result against a target, use the scoring script.

```bash
uv run python examples/score_mask.py --mask examples/data/fig3a-mask.csv --target examples/data/lowpass-target.csv --out tmp/example-score
```

The script runs a new analysis and prints the linear-magnitude RMSE against the bundled ideal low-pass target on one line. The usage guide lists the arguments, Python API, and input formats. [Evaluate options](docs/usage.md#evaluate-options) · [Scoring script options](docs/usage.md#scoring-script-options) · [Usage guide](docs/usage.md)

## Reproducing Fig. 3(a)

Pass the Fig. 3(a) mask and the reproduction YAML to use the peripheral shorts, narrow feed connections, and four subdivisions per pixel from the 0.58 dB comparison. [Mask CSV](examples/data/fig3a-mask.csv) · [Reproduction YAML](examples/configs/paper_outer_terminals.yaml)

```bash
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --config examples/configs/paper_outer_terminals.yaml --out tmp/fig3a-reproduction
```

## Loading saved results

Use `load_response()` to load a completed analysis.

```python
from maskrf import load_response

response = load_response("tmp/example-response")
s21 = response.s[:, 1, 0]
```

Loading and scoring saved responses works without openEMS or CSXCAD. [Scoring a saved response](docs/usage.md#scoring-a-saved-response)

## Documentation and verification results

| Document | Contents |
|---|---|
| [Usage guide](docs/usage.md) | Masks and settings, the Python API, the CLI, saved results, and RMSE scoring |
| [YAML configuration reference](docs/configuration.md) | Setting definitions, value ranges, bundled values, and grid and frequency spacing |
| [Reproduction report](docs/reproduction-report.md) | Background, reproduction setup, comparison with HFSS, and the effects of geometry and materials |
| [Verification data](docs/data/README.md) | The inputs and sources behind the report's figures and numerical results |

## Development checks

```bash
uv sync --locked --inexact
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m unittest discover -s tests -v
uv run python tests/check_geometry.py
uv run python tests/check_network_extraction.py
uv build --out-dir tmp/dist
```

The tests use bundled response data and run without openEMS, CSXCAD, or previous run outputs. [Saved response fixture](tests/fixtures/README.md)

## Repository layout

| Directory | Contents |
|---|---|
| [src/maskrf](src/maskrf/) | Library, API, CLI, and bundled settings and mask |
| [examples](examples/) | Example scripts, editable configurations, masks, and targets |
| [tests](tests/) | Maintained tests and a saved response fixture |
| [scripts](scripts/) | openEMS and CSXCAD build and installation scripts |
| [docs](docs/) | Usage specifications, verification results, and figures |
| `tmp/` (ignored by Git) | Working files, run outputs, and verification records |

## License

The original MaskRF software is available under the GNU General Public License, version 3 or any later version. The openEMS and CSXCAD Python bindings built during setup carry GPLv3-or-later and LGPLv3-or-later terms, respectively. The data index records the sources and redistribution status of the third-party material used for comparisons. [MaskRF license](LICENSE) · [openEMS license metadata](https://github.com/thliebig/openEMS/blob/5f36e7f3a2367123f00999491a069aed50c6f244/python/setup.py) · [CSXCAD license metadata](https://github.com/thliebig/CSXCAD/blob/3861f2102aa9d13fbb0edb115fe446aeca6a0c13/python/setup.py) · [Data sources and redistribution](docs/data/README.md#data-sources-and-redistribution)
