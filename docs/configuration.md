# YAML configuration reference

[日本語](configuration.ja.md)

Pass simulation settings through `--config` in the CLI or `evaluate_mask(..., config_path=...)` in the Python API. The YAML file must include all the settings used by the command. The "Bundled value" column shows the values used by `evaluate` and by `inspect` with a mask if `--config` is omitted. Use the reproduction YAML for the Fig. 3(a) circuit with shorts outside the mask. [Bundled YAML](../src/maskrf/configs/paper_corrected.yaml) · [Reproduction YAML](../examples/configs/paper_outer_terminals.yaml)

"Type and range" lists the conditions for building a model and identifies the checks that MaskRF performs explicitly. Integer settings have a step of 1. Real-valued dimensions, coordinates, and material constants can be entered without a fixed increment. Whether a geometry change appears in the simulation depends on the generated grid and how materials and conductors are represented on it. See [Checking grid spacing](#checking-grid-spacing) for an example with a small change in dimension. Positions and lengths are in millimeters.

| Key | Meaning | Type and range |
|---|---|---|
| `name` | Name displayed in the geometry drawing | String |
| `assumptions` | Notes on modeling assumptions or sources | Optional list of strings for recordkeeping |

## Mask geometry and materials

The origin is the center of the mask, with +x to the right and +y up. CSV row 0 corresponds to the +y side and column 0 to the −x side. The API's `mask` argument and the CLI's `--mask` accept a 16×16 binary mask. A CSV uses 1 for metal and 0 for empty space. The ground plane is on the underside of the substrate at z = 0, and the top metal lies on the substrate.

| Key | Meaning | Type and range | Bundled value |
|---|---|---|---|
| `geometry.kind` | Circuit geometry to generate. `mask` places the input metal pattern at the center and adds the left and right feeds and any configured shorts. See the [appendix on straight and notch models](#appendix-on-straight-and-notch-models) for other values | `mask` for a mask circuit. Required by `evaluate` and `inspect --mask` | `mask` |
| `geometry.file` | Metal mask file | Path to a CSV or black-and-white PNG for `mask`. Relative paths resolve from the directory containing the YAML. The input passed through `--mask` to `evaluate` or `inspect`, or through the API's `mask` argument, takes precedence | `../data/example-mask.csv` |
| `geometry.pitch_mm` | Side length of one mask pixel. A side of the 16×16 mask is 16 times the pitch | Positive real number for `mask`. The CLI checks that it is positive | 0.125 |
| `geometry.shorts` | List of shorts through the substrate, connecting the top surface to the back ground plane | Optional list of mappings with the fields below. An empty list creates no shorts | 2 entries |
| `geometry.shorts[].xy_mm` | Center of the short and its top pad | Pair of real numbers `[x, y]`. The entire short must fit in the domain. If a pad is specified, MaskRF checks its bounds when building the model | `[-0.9375, 0.9375]`, `[-0.3125, -0.9375]` |
| `geometry.shorts[].width_mm` | Side length of the short's square cross section | Positive real number | 0.125 each |
| `geometry.shorts[].pad_width_mm` | Side length of a square top metal pad centered on the short | Optional positive finite real number. MaskRF validates it when building the model. Omit to create the short without a pad | Omitted |
| `substrate.thickness_mm` | Substrate thickness | Positive real number | 0.16764 |
| `substrate.epsilon_r` | Relative permittivity of the substrate | Positive real number, dimensionless | 3.66 |
| `substrate.conductivity_S_m` | Substrate conductivity in S/m | Nonnegative real number. Use 0 to omit dielectric absorption loss | 0 |
| `metal.model` | Conductor model | `PEC` only. Validated when building the model | `PEC` |
| `metal.thickness_mm` | Top metal thickness | Nonnegative real number. Use 0 for a zero-thickness PEC surface | 0.035 |

For an external short, set the center and width of its top pad so the pad touches the metal at the mask edge.

## Feeds and measurement

Port 1 is on the −x side and port 2 is on the +x side. Distances to the excitation and measurement planes are measured from the outer end of each feed line toward the circuit.

| Key | Meaning | Type and range | Bundled value |
|---|---|---|---|
| `ports.type` | Note on the port type. The model uses microstrip line (MSL) ports | For recordkeeping. The examples use `MSL` | `MSL` |
| `ports.y_mm` | Center of each feed line | Pair of real numbers `[port 1 y, port 2 y]`. Each line must fit in `domain.y_mm`, including half of `ports.width_mm` on either side of its center | `[-0.5625, -0.6875]` |
| `ports.width_mm` | Common width of the two feed lines | Positive real number | 0.35 |
| `ports.feed_length_mm` | Common length of a feed line from its outer end to the mask edge, including any neck | Positive real number | 12 |
| `ports.feed_shift_mm` | Distance from the outer end to the excitation plane | Real number at least 0 and smaller than the feed length. With a neck, the plane must be in the wider section | 2 |
| `ports.measurement_shift_mm` | Distance from the outer end to the S-parameter measurement plane | Real number greater than 0 and smaller than the feed length. The adjacent probes must also fit within the feed line | 3 |
| `ports.reference_ohm` | Common reference impedance in Ω used to normalize the S-parameters | Positive real number | 50 |
| `ports.neck` | Setting that changes the width of each feed where it connects to the circuit | Optional mapping. Specify both the length and width below when used. Omit for constant-width feeds | Omitted |
| `ports.neck.length_mm` | Length of the neck from the mask edge toward the outer end | Positive real number. MaskRF checks the upper bound below when building the model | Omitted |
| `ports.neck.width_mm` | Neck width | Positive real number at most `ports.width_mm`. Validated when building the model | Omitted |

With a neck, the excitation plane and the measurement probes must lie in the wider section. MaskRF checks that the neck length is less than `feed_length_mm − max(feed_shift_mm, measurement_shift_mm + probe_step_mm)`. The formula uses `mesh.probe_step_mm` for `probe_step_mm`, or 0 if the setting is omitted. After grid smoothing, MaskRF also checks that the grid line next to the measurement plane on the circuit side is still in the wider section.

## Domain and frequencies

The domain extends in both x directions from the origin by half the mask width plus `ports.feed_length_mm`.

| Key | Meaning | Type and range | Bundled value |
|---|---|---|---|
| `domain.y_mm` | Bounds of the domain along y | Pair of real numbers `[lower, upper]` with lower < upper. The structures on the substrate must fit within the bounds | `[-3, 3]` |
| `domain.air_top_mm` | Top z coordinate of the domain measured from the ground plane | Real number greater than the sum of the substrate and metal thicknesses | 3 |
| `boundary` | Boundary conditions for the six faces of the domain | Ordered as `[-x, +x, -y, +y, -z, +z]`. String options are `PEC` (electric wall), `PMC` (magnetic wall), `MUR` (absorbing boundary), and `PML_n` (absorbing layer of n cells, with n a positive integer). The CLI checks that all six faces are specified and that −z is `PEC` | `[PML_8, PML_8, MUR, MUR, PEC, MUR]` |
| `frequency_GHz` | Excitation band and frequencies at which to calculate S-parameters | `[start, stop, count]`. Start and stop are real numbers with 0 ≤ start < stop. Count is an integer of at least 2. The CLI checks the lower bound on count | `[10, 30, 401]` |

The other five boundary conditions also accept integers. Values `0`, `1`, `2`, and `3` correspond to `PEC`, `PMC`, `MUR`, and `PML_8`, respectively.

The output frequencies are evenly spaced and include both endpoints. The spacing is `(stop − start) / (count − 1)` GHz, 0.05 GHz (50 MHz) with the bundled values. The solver determines the FDTD time step from the grid and materials.

## Computational grid

| Key | Meaning | Type and range | Bundled value |
|---|---|---|---|
| `mesh.max_mm` | Maximum spacing along each axis when smoothing the grid | Positive real number | 0.075 |
| `mesh.local_mm` | Spacing between grid lines placed mainly on either side of the edges of the wider feed sections | Positive real number | About 0.004167 |
| `mesh.pixel_subdivisions` | Number of subdivisions in x and y per mask pixel. Also used to add grid lines at pads and necks | Positive integer. Required for `mask` | 9 |
| `mesh.substrate_cells` | Number of equal subdivisions through the substrate thickness before smoothing | Positive integer | 16 |
| `mesh.edge_rule` | Rule for dividing `mesh.local_mm` between the inside and outside of the conductor | `thirds` assigns 1/3 inside and 2/3 outside. `legacy` assigns 2/3 inside and 1/3 outside. Validated when building the model. Defaults to `legacy` if omitted | `thirds` |
| `mesh.probe_step_mm` | Distance from the measurement plane to the added x grid lines on either side | Optional positive real number. Validated when building the model | 0.025 |
| `mesh.verify_feed_edges` | Whether to check that the conductor occupies the required 1/3 of the cell straddling each edge of the wider feed section | Optional `true` or `false`. Defaults to `false`. With `true`, a failed ratio check stops model construction | `true` |

### Checking grid spacing

The grid includes the pixel boundaries and lines spaced by `geometry.pitch_mm / mesh.pixel_subdivisions` in the mask. A pitch of 0.125 mm divided into 4 subdivisions gives a spacing of 0.03125 mm. MaskRF also places grid lines at feed edges, measurement planes, and domain boundaries, so the final spacing varies by location.

Two geometries with different dimensions produce the same FDTD model if they share the grid, material and conductor representation, excitation, and measurement conditions. MaskRF builds the grid from the settings, so changing a feed width or a measurement plane can move grid lines. For example, changing `ports.width_mm` from 0.35 mm to 0.3501 mm in the reproduction YAML moves each grid line bordering a feed edge by 0.00005 mm. When evaluating a response change due to such a small dimension change, check whether the difference persists on a finer grid.

To see the grid that represents a dimension change, check `lines_mm` in the `mesh.json` produced by `inspect`. The difference between adjacent coordinates along each axis is the local grid spacing. For the reproduction YAML, the minimum spacings are 0.025 mm in x, about 0.004167 mm in y, and 0.020955 mm in z. Cells that straddle feed edges are recorded in `feed_edge_audit`. [Inspecting the circuit geometry](usage.md#inspecting-the-circuit-geometry)

## Solver and comparison metrics

| Key | Meaning | Type and range | Bundled value |
|---|---|---|---|
| `solver.excitations` | Port numbers in the order in which they are independently excited | List with entries from `1` and `2`. Both excitations are required for the full S-matrix. `evaluate` requires `[1, 2]` | `[1, 2]` |
| `solver.max_steps` | Maximum number of FDTD time steps per excitation | Positive integer | 400000 |
| `solver.end_criteria` | Upper bound on the ratio of the current estimated energy to its maximum so far, used to determine when the simulation can stop | Real number greater than 0 and less than 1, dimensionless. `1.0e-06` corresponds to −60 dB | `1.0e-07` |
| `solver.max_cells` | Maximum allowed number of computational cells, compared against the product of the number of intervals along each axis (grid points minus one) | Positive integer. Validated when building the model | 10000000 |
| `solver.threads` | Number of solver threads per excitation | Nonnegative integer. Use 0 to let openEMS choose automatically | 4 |
| `solver.timeout_s` | Time limit per excitation in seconds | Positive real number | 7200 |
| `validation.passband_GHz` | Frequency interval for reporting the minimum and maximum S21 magnitudes and the maximum difference in a comparison | Pair of real numbers `[lower, upper]` with lower ≤ upper. The interval must include at least one output frequency | `[10, 14]` |
| `validation.complex_delta_tolerance` | Maximum absolute difference allowed for complex S-parameters in `compare` and `convergence` | Nonnegative real number, dimensionless. Defaults to 0.02 if omitted | 0.02 |
| `convergence` | Grid settings for successive runs of `maskrf convergence` | Required by the `convergence` command. List of mappings with keys from `mesh`. Each stage overrides the specified entries in the base `mesh`. Provide at least two stages to compare them | Two stages with 8 and 9 subdivisions per pixel |

A successful new simulation must meet `solver.end_criteria`. Grid comparisons check differences in the full complex S-matrix, the passband S21 magnitude, and the frequency of the downward −3 dB crossing. See the usage guide for the fields in the comparison results. [Analysis and comparison commands](usage.md#analysis-and-comparison-commands)

## Appendix on straight and notch models

Use `geometry.kind: straight` to check transmission, reflection, and the effects of grid refinement on a straight line. Use `geometry.kind: notch` to check the drop in transmission caused by a stub. In both geometries, the left and right feed lines meet directly at x = 0. The x boundaries of the domain are at ±`ports.feed_length_mm`. To inspect or simulate a model, pass its YAML to `inspect --config` or `run --config`, respectively.

### Straight transmission line (`straight`)

Set the same `ports.y_mm` for both feeds to form a single constant-width line of width `ports.width_mm`. The example uses y = 0, a width of 0.35 mm, and a length of 13 mm on each side, giving a 26 mm line. [Straight-line configuration](../examples/configs/straight_fine.yaml)

### Open-stub transmission line (`notch`)

One open-ended stub extends from the central line toward +y. The example uses `ports.y_mm: [0, 0]`, with the base of the stub connected to the +y edge of the line. Set the length in `geometry.stub_mm` to study the S21 notch. [Open-stub configuration](../examples/configs/notch.yaml)

| Key | Meaning | Type and range | Example value |
|---|---|---|---|
| `geometry.stub_mm` | Length from the base to the open end | Positive real number. The open end must lie within the upper bound of `domain.y_mm` | 12 |

The stub is centered at x = 0. With `w = ports.width_mm`, it spans `−w/2` to `+w/2` in x and `w/2` to `w/2 + geometry.stub_mm` in y. `ports.y_mm` sets the center of each feed line only. In the stub example the width is 0.6 mm, the base is at y = 0.3 mm, and the open end is at y = 12.3 mm.
