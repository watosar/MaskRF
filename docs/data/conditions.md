# Conditions and assumptions for Fig. 3(a)

[日本語](conditions.ja.md)

The table records the model with internal shorts and uniform-width feeds used by the bundled YAML. The reproduction report gives the settings and response for the model with external shorts and narrow feed ends from Fig. 3(a). [Model for Fig. 3(a)](../reproduction-report.md#2-model-for-fig-3a)

The source is Guo et al., *Dall-EM*, IMS 2025, DOI 10.1109/IMS40360.2025.11103838. Fig. 3(a) provides feed dimensions and an HFSS curve, so it supports comparison without manufacturing variation. The simulated response in Fig. 3(a) serves as the comparison reference. Fig. 4 reports prototype measurements. [Original paper](https://doi.org/10.1109/IMS40360.2025.11103838)

| Condition | Value or treatment | Basis | Status |
|---|---|---|---|
| Width and height of the metal pattern | 2 mm × 2 mm | Fig. 2 on p. 2 and Fig. 3(a) on p. 3 of the PDF | Confirmed |
| Training matrix | 18×18 | Section II-B and Fig. 2 on p. 2 | Confirmed |
| Interior grid in Fig. 3(a) | 16×16, pitch 0.125 mm | Checked the 15 internal boundaries in each direction and the 2 mm dimension in Fig. 3(a) against the 16 candidate terminals per side in Fig. 2. [Grid measurements](grid-measurements.json) | Interior divisions confirmed from the figure. The correspondence with the input perimeter is inferred |
| Minimum line width and gap | Generally one pixel, with corner contacts present | Fig. 3(a) | Estimated |
| Conductor layers | Substrate top metal and backside ground | Fig. 2 | Confirmed |
| Substrate | RO4350B, 6.6 mil = 0.16764 mm, εr ≈ 3.66 | Annotation in Fig. 2 | Confirmed |
| Dielectric loss and dispersion | The model uses zero conductivity and constant εr | The four-page paper leaves these values unspecified | Unknown, model assumption |
| Metal thickness | 35 µm | Fig. 2 | Confirmed |
| Conductivity and roughness | PEC | The paper leaves these values unspecified | Unknown, model assumption |
| Ground extent and thickness | PEC boundary across the entire bottom of the domain at z = 0 | Fig. 2 shows a ground plane with unspecified extent | Assumed |
| AC ground | Leftmost pixel on the top edge and sixth pixel from the left on the bottom edge | Blue markers in Fig. 3(a) and the shorting-via legend in Fig. 1 | Positions inferred |
| Short geometry | PEC pillar with a 0.125 mm square cross section through the substrate | Via diameter, plating, and pads are unspecified | Assumed |
| Feed width | 0.35 mm | Annotation to the right of Fig. 3(a) | Confirmed |
| Feed length | 12 mm on both sides | Fig. 3(a) labels the right feed 12 mm. The model uses the same length on the left | Right confirmed, left inferred |
| Feed position | Left y = −0.5625 mm, right y = −0.6875 mm | Centerlines in Fig. 3(a) | Estimated |
| Ports | openEMS MSL ports with the electric field along z and reference ground at z = 0 | Section III-B on p. 3 describes edge feed excitations | Assumed |
| Reference impedance | 50 Ω | The paper leaves it unspecified | Assumed |
| Reference plane | 3 mm inward from the outer end and 9 mm from the mask edge | The paper leaves the reference planes and de-embedding unspecified | Assumed |
| Substrate width and air height | y from −3 to 3 mm, upper boundary at z = 3 mm | The paper leaves these dimensions unspecified | Assumed |
| Boundaries | PML8 on both x faces, MUR on both y faces and the top, PEC on the bottom | Initial settings follow the official notch example. A separate run checked sensitivity to distance | Assumed |
| Frequency range | 10–30 GHz | Section II-B and Fig. 2 on p. 2 | Confirmed |
| Original sampling interval | 1 GHz, 21 points | Section II-B on p. 2 | Confirmed |
| Comparison curve | Purple curve in Fig. 3(a), HFSS S21 magnitude | Section III-B and Fig. 3 on p. 3 | Confirmed |
| Simulation used for comparison | HFSS | Section III-B and Fig. 3 on p. 3 identify separate target, CNN prediction, and measurement results | Confirmed |

Row 0 lies on the +y side, column 0 on the −x side, and the origin at the center of the mask. MaskRF reads 0/1 CSV data directly with 1 for metal. In black-and-white PNGs, black denotes metal and gray pixels are rejected. The model preserves gaps, isolated metal, and corner contacts as extracted. Corner contacts are sensitive to FDTD discretization and contribute shape uncertainty alongside mesh differences. [Extraction settings, thresholds, and ambiguous cells](paper-extraction.json)

The purple curve in the image embedded in the PDF provides the HFSS data. The comparison covers its visible range, including only values above the clipping near −20 dB. The available reference is transmission magnitude. [Axes and digitization uncertainty](paper-extraction.json)

The 18×18 input representation includes perimeter terminal information. The figures indicate that the metal pattern occupies the inner 16×16 cells. The original numerical encoding remains unavailable. [Terminal counts, 16- and 18-cell grid fits, and agreement across all mask cells](grid-measurements.json)
