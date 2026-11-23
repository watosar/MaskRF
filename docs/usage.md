# Usage

[日本語](usage.ja.md)

See the [README](../README.md) for MaskRF setup and the openEMS and CSXCAD build. Run the commands below from the repository root and use `uv` to run Python and manage the environment.

## 1. Masks and settings

| Item | Specification |
|---|---|
| Input | 16×16 NumPy array, nested list, CSV, JSON array, or black-and-white PNG |
| Values | 1 for metal, 0 for empty space. Only these numeric values and their Boolean equivalents are accepted |
| PNG | Black for metal, white for empty space. Pixels must be pure black or white |
| Coordinates | Row 0 is on the +y side and column 0 is on the −x side. The mask center is the origin |
| Default dimensions | 0.125 mm pitch, yielding a 2 mm square interior |
| Added structures | Substrate, ground plane, feed lines, and shorts as specified in the configuration |

A CSV must have 16 rows and 16 columns with no header. A JSON input must be the two-dimensional array itself. For an 18×18 representation with terminals, supply only the inner 16×16 mask. MaskRF uses the geometry as supplied, including any isolated metal and corner contacts.

The defaults come from the [bundled YAML](../src/maskrf/configs/paper_corrected.yaml). To change the settings, copy the [editable example](../examples/configs/paper_corrected.yaml) and pass it as `config_path` in the API or `--config` in the CLI. Specify lengths in millimeters and frequencies as `frequency_GHz: [start, stop, count]`.

See the [YAML configuration reference](configuration.md) for each parameter's meaning, type, range, bundled value, and the grid and frequency spacings.

Pass a mask as the `mask` argument to `evaluate_mask`, or through `--mask` for `maskrf evaluate` and `maskrf inspect`. Mask evaluation requires `geometry.kind: mask` and `solver.excitations: [1, 2]`. To specify the mask in YAML for `run`, `convergence`, or `inspect --config`, set `geometry.file` to the path of a CSV or black-and-white PNG. Relative paths resolve from the YAML file's directory.

Changes to material, geometry, or grid settings require their own accuracy checks. The observed grid differences for Fig. 3(a) apply to the cases tested.

### Shorts and feed lines

The CSV defines the central 16×16 metal pattern. The configuration YAML specifies the positions and dimensions of the shorts and feed lines. The origin is the center of the mask, with +x to the right and +y up.

| Setting | Meaning |
|---|---|
| `geometry.shorts[].xy_mm`, `width_mm` | The center `[x, y]` of each short and the side length of its square conductor through the substrate |
| `geometry.shorts[].pad_width_mm` | Optional side length of a top metal pad with the same center as the short. For a short outside the mask, position and size the pad so it touches the metal at the edge of the mask |
| `ports.y_mm`, `ports.width_mm` | The centers of the feed lines `[left y, right y]` and their common width |
| `ports.neck.length_mm`, `width_mm` | Optional length and width of the section that meets the mask. The two feeds use the same dimensions, and the neck width must be at most `ports.width_mm`. The neck is included in `feed_length_mm`. Excitation and measurement take place in the outer section |

The [configuration for Fig. 3(a) with outer shorts and narrow feed connections](../examples/configs/paper_outer_terminals.yaml) specifies two peripheral pads and feed connections that are each 0.125 mm long and 0.125 mm wide. Use the same YAML to inspect and simulate the model.

```bash
uv run maskrf inspect --mask examples/data/fig3a-mask.csv --config examples/configs/paper_outer_terminals.yaml --out tmp/outer-terminals-inspect
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --config examples/configs/paper_outer_terminals.yaml --out tmp/outer-terminals-run
```

If a feed width change causes the grid check at the feed edges to fail, reduce `mesh.local_mm` and check the grid with `inspect`.

## 2. Python API

The public API includes `evaluate_mask`, `load_response`, their return type `CircuitResponse`, and `SimulationError` for failed simulations.

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

`evaluate_mask(mask, out_dir, *, config_path=None)` runs synchronously. Each call starts a new simulation with independent excitation at both ports and requires the openEMS and CSXCAD Python bindings and shared libraries. If they are missing, MaskRF prompts for installation with `(Y/n)`, installs them on confirmation, and continues the simulation. Declining or reaching the end of input raises `SimulationError` before the output directory is created. A default simulation takes tens of minutes or longer. Choose an unused directory for the output.

| Return value | Meaning |
|---|---|
| `frequency_Hz` | Frequency array in Hz. The default has 401 points from 10–30 GHz |
| `s` | Complex array of shape `(number of frequencies, 2, 2)`, with Sij at `s[:, i-1, j-1]` |
| `metrics` | S21 band metrics, the downward −3 dB crossing, and metrics for reciprocity, power ratios, and passivity |
| `settings`, `mask` | Simulation and measurement settings and the input mask |
| `run_dir` | Location of the simulation results |
| `to_dict()` | JSON-serializable dictionary with real and imaginary parts, magnitude in dB, phase in degrees, and metrics |

### Loading saved results

`load_response(run_dir)` reads the response from a completed run or from the output of `evaluate_mask`. It reads the stored data directly, so it can run without openEMS and CSXCAD or waveform reprocessing.

```python
from maskrf import load_response

saved = load_response("tmp/python-example")
s21 = saved.s[:, 1, 0]
```

Both functions check that the two excitations completed with sufficient decay, validate the frequency array, and require every S-parameter value to be finite. They reject runs that fail the decay criterion with `SimulationError`. Assess mesh convergence and strict passivity separately using the reported metrics and additional checks.

## 3. CLI and saved results

```bash
uv run maskrf evaluate --mask examples/data/fig3a-mask.csv --out tmp/circuit-01
```

### Evaluate options

| Option | Required | Meaning |
|---|---|---|
| `--mask PATH` | Yes | 16×16 mask to evaluate as a CSV, JSON array, or black-and-white PNG |
| `--out DIR` | Yes | Unused directory for the input, configuration, and response |
| `--config YAML` | No | Simulation settings. Defaults to the [bundled configuration](../src/maskrf/configs/paper_corrected.yaml) |

You can also invoke the CLI with `uv run python -m maskrf`.

### Output files

On success, `evaluate` writes the response JSON to standard output and `response.json`. On failure, it exits with a nonzero status and writes error JSON to standard error. Failures after the simulation starts also produce `error.json`. The output directory stores the input and solver logs.

The first-run installation prompt and progress messages go to standard error. If installation fails, MaskRF displays the path to the log in the XDG state directory. See the [README](../README.md#installation) for the installation locations and required tools.

| Main files | Contents |
|---|---|
| `mask.csv`, `request.yaml`, `request.json` | Input mask, settings passed to the solver, input hash, and geometry audit |
| `response.json` | Completed response, metrics, and a reference to the run directory |
| `execution.log` | Log from the simulation process |
| `run/effective.json`, `run/status.json` | Effective simulation settings and completion and decay status for each excitation |
| `run/sparameters.csv`, `run/network.s2p` | Full complex S-parameters in CSV and Touchstone formats |
| `run/solver-*.log`, `run/excite-*/` | Logs and waveforms for each excitation |

### Inspecting the circuit geometry

`inspect` builds the model and computational grid and exports the geometry before any excitation is run. This example uses a mask CSV and the bundled configuration. Building the model requires the openEMS and CSXCAD Python bindings and shared libraries. If they are missing, MaskRF prompts for installation with `(Y/n)`.

```bash
uv run maskrf inspect --mask examples/data/fig3a-mask.csv --out tmp/inspect-01
```

| Option | Required | Meaning |
|---|---|---|
| `--mask PATH` | If `--config` is omitted | 16×16 mask to draw as a CSV, JSON array, or black-and-white PNG |
| `--config YAML` | If `--mask` is omitted | Settings that define the geometry and grid. Defaults to the bundled configuration |
| `--out DIR` | No | Output directory. Defaults to `tmp/maskrf-inspect` |

If both options are given, MaskRF reads the metal pattern from `--mask` and the substrate, feed lines, and other settings from the `--config` YAML. If the YAML includes the mask path, `inspect --config YAML` is enough.

| Output file | Contents |
|---|---|
| `geometry.png` | Plan view showing the metal pattern, feeds, measurement planes, and short locations, and a schematic cross section of the substrate and ground plane |
| `geometry.xml` | Geometry XML for openEMS and CSXCAD |
| `mesh.json` | Grid coordinates for each axis, cell counts, and grid checks at the feed edges |
| `geometry-audit.json` | Mask dimensions, number of metal cells, number of connected components, and other geometry details |

Standard output contains the fields from `mesh.json` as JSON, with the grid coordinates omitted.

### Analysis and comparison commands

`run` starts a new simulation from the configuration YAML. `convergence` runs a new simulation for each grid listed under `convergence` and computes differences between stages. `compare` and `postprocess` reprocess saved waveforms and also require the openEMS and CSXCAD Python bindings and shared libraries.

`run` and `convergence` check that each excitation completes successfully and meets the decay criterion. Even when the solver returns exit code 0, a run that fails the decay criterion saves its status and logs and exits with a nonzero status before further excitations, grid runs, or routine postprocessing. When waveforms for all configured excitations are available, `postprocess` can reprocess them for diagnostics. Check completion and decay separately from postprocessing. If the run stopped after the first excitation, the full S-matrix requires the missing second excitation.

```bash
uv run maskrf run --config examples/configs/paper_corrected.yaml --out tmp/raw-run-01
uv run maskrf postprocess --run tmp/raw-run-01
uv run maskrf compare --runs tmp/raw-run-01 tmp/raw-run-02 --out tmp/comparison-01
uv run maskrf convergence --config examples/configs/paper_corrected.yaml --out tmp/convergence-01
```

Runs must share the same frequency array for comparison. Supply a separate run with the comparison settings as `raw-run-02`. If both excitations have saved waveforms in each run, `compare` can include incomplete or insufficiently decayed responses for diagnostics. To judge grid verification, check the comparison fields below in addition to the exit code.

In each row of `comparison.json`, `time_decay_confirmed` reports whether both excitations in the run completed and met the decay criterion. In comparison rows, `both_runs_completed_and_decayed` applies the check to both the current and previous runs. `full_s_delta_threshold_pass` checks the differences in magnitude, feature frequency, and the full complex S-matrix. `full_s_threshold_pass` also requires both runs to complete with sufficient decay. Use `full_s_threshold_pass` for grid verification. Strict passivity and agreement with the source paper require separate checks.

## 4. Scoring against a target S21 with RMSE

[score_mask.py](../examples/score_mask.py) is an example client of the public API. By default, it calculates RMSE from the difference between the response and target in linear magnitude and returns a single float.

```text
e[k] = |S21_response(f[k])| - target_magnitude[k]
RMSE = sqrt(sum(e[k]**2) / N)
```

The script linearly interpolates the response magnitude to the target frequencies and weights all N points equally. Target frequencies must be within the response range, and the score uses magnitude only. The score is dimensionless. Smaller values indicate closer agreement, and zero means that the magnitudes match at every target frequency. RMSE is the default for both the CLI and the Python function.

```bash
uv run python examples/score_mask.py --mask examples/data/fig3a-mask.csv --target examples/data/lowpass-target.csv --out tmp/score-01
```

This command runs a new simulation and scores its response. If openEMS and CSXCAD are missing, it prompts for installation with `(Y/n)`. On success, standard output is a single line containing a float. The script saves the response in `response.json`, the scoring settings, score, and compared magnitudes in `score.json`, and the input target in `target.csv`. On failure, it reports the error on standard error and exits with a nonzero status before printing a score.

### Scoring script options

| Option | Required | Meaning |
|---|---|---|
| `--mask PATH` | Yes | 16×16 mask to evaluate as a CSV, JSON array, or black-and-white PNG |
| `--target CSV` | Yes | Target for comparison. The columns and units are described below |
| `--out DIR` | Yes | Unused directory for the response and score |
| `--metric NAME` | No | `rmse`, `mse`, `mae`, or `max`. Defaults to `rmse` |
| `--config YAML` | No | Simulation settings. Defaults to the bundled configuration |

The target CSV must use one of two column pairs. Frequencies must be positive, strictly increasing, and within the simulated range. Both magnitude formats require finite values. Linear magnitudes must be nonnegative.

```csv
frequency_GHz,s21_magnitude
10,1
15,1
16,0
30,0
```

The other format is `frequency_GHz,s21_dB`. The script converts dB to linear magnitude with `10**(dB/20)` before scoring. Specify zero transmission as 0 in `s21_magnitude`.

[lowpass-target.csv](../examples/data/lowpass-target.csv) is an idealized low-pass example from 10–30 GHz in 1 GHz increments. It assigns a magnitude of 1 to the six points from 10–15 GHz and 0 to the 15 points from 16–30 GHz. It serves as a synthetic target. The feasibility of realizing it with a mask circuit remains untested.

In Python, call `examples.score_mask.score_mask(mask, target_path, out_dir, ...) -> float`. This function also runs a new simulation and scores its response.

| `--metric` or `metric` | Formula | Units |
|---|---|---|
| `rmse` (default) | `sqrt(mean(e**2))` | Linear magnitude |
| `mse` | `mean(e**2)` | Linear magnitude squared |
| `mae` | `mean(abs(e))` | Linear magnitude |
| `max` | `max(abs(e))` | Linear magnitude |

MSE and RMSE rank circuits in the same order for a given set of points and weights. They give larger errors more weight than MAE does. `s21_mae(...)` computes MAE. The maximum error covers the evaluation points only. Errors can be larger between those points.

Use RMSE to rank candidates. The contributions of the passband and stopband depend on the sample counts, and an average can conceal local specification violations. Check the insertion loss and stopband attenuation for each band when assessing compliance. The paper reproduction uses dB RMSE against the digitized HFSS magnitude curve, which has a different scale from the linear-magnitude score.

### Scoring a saved response

Load a saved result with `load_response()` and pass it to `s21_error()`. Scoring saved data requires neither a new simulation nor openEMS and CSXCAD. Pass the frequencies to the function in Hz.

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
