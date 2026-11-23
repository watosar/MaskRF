# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path
from typing import NotRequired, TypedDict

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .model import build


class PostprocessMetrics(TypedDict):
    max_outgoing_power_per_incident: dict[str, float]
    passivity_tolerance: float
    extraction: str
    max_incident_matrix_condition: float | None
    unexcited_port_incident_ratio: dict[str, float]
    max_singular_value: NotRequired[float]
    max_reciprocity_error: NotRequired[float]
    passband_s21_min_dB: NotRequired[float]
    passband_s21_max_dB: NotRequired[float]
    phase_delay_median_ps: NotRequired[float]
    first_downward_3dB_GHz: NotRequired[float | None]


def db(s):
    return 20 * np.log10(np.maximum(abs(s), 1e-15))


def process(out):
    out = Path(out)
    c = json.loads((out / "effective.json").read_text())
    if (out / "mask.csv").exists():
        c["geometry"]["file"] = str((out / "mask.csv").resolve())
    f = np.linspace(
        *[
            c["frequency_GHz"][0] * 1e9,
            c["frequency_GHz"][1] * 1e9,
            c["frequency_GHz"][2],
        ]
    )
    cols = {}
    energy = {}
    incident = []
    outgoing = []
    residual = {}
    for excitation in c["solver"]["excitations"]:
        _, _, ports, _ = build(c, excitation)
        for p in ports:
            p.CalcPort(
                str(out / f"excite-{excitation}"),
                f,
                ref_impedance=c["ports"]["reference_ohm"],
            )
        inc = ports[excitation - 1].uf_inc
        if not np.isfinite(inc).all() or np.min(abs(inc)) < 1e-20:
            raise ValueError("Invalid incident spectrum")
        incident.append(np.array([p.uf_inc for p in ports]))
        outgoing.append(np.array([p.uf_ref for p in ports]))
        residual[str(excitation)] = float(
            np.max(abs(ports[2 - excitation].uf_inc / inc))
        )
        for i, p in enumerate(ports):
            cols[f"s{i + 1}{excitation}"] = p.uf_ref / inc
    conditioning = None
    if len(incident) == 2:
        A = np.stack(incident, axis=2).transpose(1, 0, 2)
        B = np.stack(outgoing, axis=2).transpose(1, 0, 2)
        conditioning = float(np.linalg.cond(A).max())
        if not np.isfinite(conditioning) or conditioning > 1e8:
            raise ValueError("Ill-conditioned incident wave matrix")
        S = B @ np.linalg.inv(A)
        cols = {f"s{i + 1}{j + 1}": S[:, i, j] for j in range(2) for i in range(2)}
    for excitation in c["solver"]["excitations"]:
        energy[str(excitation)] = float(
            np.max(sum(abs(cols[f"s{i + 1}{excitation}"]) ** 2 for i in range(2)))
        )
    if any(not np.isfinite(s).all() for s in cols.values()):
        raise ValueError("Nonfinite S data")
    header = ["frequency_Hz"]
    data = [f]
    for key, s in cols.items():
        header.extend([key + "_real", key + "_imag"])
        data.extend([s.real, s.imag])
    np.savetxt(
        out / "sparameters.csv",
        np.column_stack(data),
        delimiter=",",
        header=",".join(header),
        comments="",
    )
    fig, ax = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for key, s in cols.items():
        ax[0].plot(f / 1e9, db(s), label=key)
        ax[1].plot(f / 1e9, np.unwrap(np.angle(s)) * 180 / np.pi, label=key)
    ax[0].set_ylabel("Magnitude (dB)")
    ax[1].set_ylabel("Unwrapped phase (deg)")
    ax[1].set_xlabel("Frequency (GHz)")
    for a in ax:
        a.grid()
        a.legend()
    fig.tight_layout()
    fig.savefig(out / "sparameters.png")
    plt.close(fig)
    summary: PostprocessMetrics = {
        "max_outgoing_power_per_incident": energy,
        "passivity_tolerance": 0.02,
        "extraction": "S=B inv(A), both incident waves retained"
        if len(incident) == 2
        else "Single excitation wave ratios; residual incident wave limits S interpretation",
        "max_incident_matrix_condition": conditioning,
        "unexcited_port_incident_ratio": residual,
    }
    if len(cols) == 4:
        S = np.array(
            [[cols["s11"], cols["s12"]], [cols["s21"], cols["s22"]]]
        ).transpose(2, 0, 1)
        summary["max_singular_value"] = float(np.linalg.svd(S, compute_uv=False).max())
        summary["max_reciprocity_error"] = float(np.max(abs(cols["s12"] - cols["s21"])))
        with (out / "network.s2p").open("w") as fp:
            fp.write(
                f"! Both ports independently excited\n# Hz S RI R {c['ports']['reference_ohm']}\n"
            )
            for k, freq in enumerate(f):
                values = [freq]
                for key in ["s11", "s21", "s12", "s22"]:
                    values.extend([cols[key][k].real, cols[key][k].imag])
                fp.write(" ".join(f"{x:.12g}" for x in values) + "\n")
    if "s21" in cols:
        s = cols["s21"]
        band = c["validation"]["passband_GHz"]
        use = (f >= band[0] * 1e9) & (f <= band[1] * 1e9)
        summary.update(
            passband_s21_min_dB=float(db(s)[use].min()),
            passband_s21_max_dB=float(db(s)[use].max()),
            phase_delay_median_ps=float(
                np.median(-np.gradient(np.unwrap(np.angle(s)), 2 * np.pi * f)) * 1e12
            ),
        )
        crossing = np.flatnonzero((db(s)[:-1] >= -3) & (db(s)[1:] < -3))
        summary["first_downward_3dB_GHz"] = (
            None
            if not len(crossing)
            else float(
                np.interp(
                    -3,
                    db(s)[crossing[0] : crossing[0] + 2][::-1],
                    f[crossing[0] : crossing[0] + 2][::-1],
                )
                / 1e9
            )
        )
    (out / "metrics.json").write_text(json.dumps(summary, indent=2))
    return f, cols, summary
