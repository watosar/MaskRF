"""Plot the report's saved responses through the public library API."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from rf_repro import load_response


PROJECT = Path(__file__).resolve().parents[1]


def plot_report(out: Path) -> None:
    data = PROJECT / "docs/data"
    response = load_response(PROJECT / "tests/fixtures/completed-run")
    frequency = response.frequency_Hz / 1e9
    s21_db = 20 * np.log10(np.maximum(abs(response.s[:, 1, 0]), 1e-15))
    paper = np.genfromtxt(data / "paper-hfss.csv", delimiter=",", names=True)
    material = np.genfromtxt(data / "material-s21-curves.csv", delimiter=",", names=True)
    selection = json.loads((data / "material-paper-selection.json").read_text())
    out.mkdir(parents=True, exist_ok=True)

    def axes_for(title, limits):
        fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.7), constrained_layout=True)
        for axis in axes:
            axis.plot(paper["frequency_GHz"], paper["s21_dB"], color="#7b3294", lw=1.8,
                      label="Original paper HFSS (readable trace)")
            axis.axhline(-3, color="#888888", lw=0.8, ls=":")
            axis.set(xlabel="Frequency (GHz)", ylabel="S21 amplitude (dB)")
            axis.grid(alpha=0.25)
        axes[0].set(xlim=limits, ylim=(-45, 0.5), title=title)
        axes[1].set(xlim=(10, 14), ylim=(-6, 0.2), title="10-14 GHz: zoom of the same S21 amplitude")
        return fig, axes

    def save(fig, axes, name):
        axes[0].legend(fontsize=8, loc="upper right")
        for extension in ("png", "svg"):
            path = out / f"{name}.{extension}"
            fig.savefig(path, dpi=170)
            if extension == "svg":
                path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
        plt.close(fig)

    fig, axes = axes_for("10-30 GHz; paper trace available only to 18.08 GHz", (10, 30))
    for axis in axes:
        axis.plot(frequency, s21_db, color="#222222", lw=1.8,
                  label="Adopted lossless RO approximation (N=9)")
    save(fig, axes, "adopted-ro-paper")

    labels = {
        "baseline_r4": ("#222222", "Lossless RO approximation (N=4)"),
        "epsilon_4p4_r4": ("#1f77b4", "epsilon_r=4.4, lossless (N=4)"),
        "fr4_like_r4": ("#ff7f0e", "epsilon_r=4.4, FR4-like loss (N=4)"),
        "thickness_0p125_r4": ("#e377c2", "Thickness 0.125 mm (N=4)"),
    }
    fig, axes = axes_for("Material comparison against original paper HFSS", (10, 18.5))
    for axis in axes:
        for name in selection["same_mesh_cases"]:
            color, label = labels[name]
            axis.plot(material["frequency_Hz"] / 1e9, material[name], color=color, label=label)
        axis.plot(frequency, s21_db, color="#888888", ls="--", label="Adopted lossless RO (N=9)")
    save(fig, axes, "material-paper-comparison")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Directory for regenerated PNG and SVG figures")
    args = parser.parse_args()
    plot_report(args.out)


if __name__ == "__main__":
    main()
