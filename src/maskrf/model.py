# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

import numpy as np

from .geometry import boxes, load_mask, terminal_boxes


def build(c, excitation=1):
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    s = c["substrate"]
    m = c["mesh"]
    g = c["geometry"]
    p = c["ports"]
    domain = c["domain"]
    h = s["thickness_mm"]
    t = c["metal"]["thickness_mm"]
    w = p["width_mm"]
    fdtd = openEMS(
        NrTS=c["solver"]["max_steps"], EndCriteria=c["solver"]["end_criteria"]
    )
    lo, hi, _ = c["frequency_GHz"]
    fdtd.SetGaussExcite((lo + hi) * 0.5e9, (hi - lo) * 0.5e9)
    fdtd.SetBoundaryCond(c["boundary"])
    cs = ContinuousStructure()
    fdtd.SetCSX(cs)
    mesh = cs.GetGrid()
    mesh.SetDeltaUnit(1e-3)
    dx = m["max_mm"]
    fine = m["local_mm"]
    # Missing key reproduces historical runs exactly. New configurations must
    # request 'thirds': one third of the edge cell inside, two thirds outside.
    rule = m.get("edge_rule", "legacy")
    if rule not in ("legacy", "thirds"):
        raise ValueError("Unknown edge_rule")
    inside = fine / 3 if rule == "thirds" else 2 * fine / 3
    outside = 2 * fine / 3 if rule == "thirds" else fine / 3
    half = (
        0 if g["kind"] != "mask" else load_mask(g["file"]).shape[1] * g["pitch_mm"] / 2
    )
    length = p["feed_length_mm"] + half
    port_end = half + p.get("neck", {}).get("length_mm", 0)
    for axis, limits in [("x", [-length, length]), ("y", domain["y_mm"])]:
        mesh.AddLine(axis, limits)
    if g["kind"] == "mask":
        a = load_mask(g["file"])
        pitch = g["pitch_mm"]
        # Cell boundaries are mandatory; independent subdivisions define FDTD refinement.
        for axis, n in [("x", a.shape[1]), ("y", a.shape[0])]:
            mesh.AddLine(
                axis,
                np.linspace(
                    -n * pitch / 2, n * pitch / 2, n * m["pixel_subdivisions"] + 1
                ),
            )
    else:
        mesh.AddLine(
            "x", [-w / 2 - outside, -w / 2 + inside, w / 2 - inside, w / 2 + outside]
        )
    terminals = terminal_boxes(c, half)
    subdivisions = m.get("pixel_subdivisions", 1)
    wide_edges = {y + sign * w / 2 for y in p["y_mm"] for sign in (-1, 1)}
    for start, stop in terminals:
        for index, axis, limits in (
            (0, "x", (-length, length)),
            (1, "y", domain["y_mm"]),
        ):
            lower, upper = start[index], stop[index]
            if not limits[0] <= lower < upper <= limits[1]:
                raise ValueError("Terminal metal must fit inside the substrate")
            positions = np.linspace(lower, upper, subdivisions + 1).tolist()
            if axis == "y":
                # An exact line at a wide feed edge would override its thirds-rule cell.
                positions = [pos for pos in positions if pos not in wide_edges]
            if positions:
                mesh.AddLine(axis, positions)
    for y in p["y_mm"]:
        mesh.AddLine(
            "y",
            [
                y - w / 2 - outside,
                y - w / 2 + inside,
                y + w / 2 - inside,
                y + w / 2 + outside,
            ],
        )
    if g["kind"] == "notch":
        edge = w / 2 + g["stub_mm"]
        mesh.AddLine("y", [edge - inside, edge + outside])
    mesh.AddLine(
        "x",
        [
            -length + p["measurement_shift_mm"],
            length - p["measurement_shift_mm"],
            -length + p["feed_shift_mm"],
            length - p["feed_shift_mm"],
        ],
    )
    if "probe_step_mm" in m:
        # MSLPort averages the two current samples around its voltage plane.
        # Equal spacing makes this average colocated with the voltage sample.
        step = m["probe_step_mm"]
        if step <= 0:
            raise ValueError("probe_step_mm must be positive")
        for sign in (-1, 1):
            plane = sign * (length - p["measurement_shift_mm"])
            mesh.AddLine("x", [plane - step, plane + step])
    mesh.SmoothMeshLines("x", dx, 1.4)
    mesh.SmoothMeshLines("y", dx, 1.4)
    if "neck" in p:
        xs = np.asarray(mesh.GetLines("x"))
        for sign in (-1, 1):
            plane = sign * (length - p["measurement_shift_mm"])
            plane_index = int(np.argmin(abs(xs - plane)))
            if sign * xs[plane_index - sign] <= port_end:
                raise ValueError("Measurement probes must remain on the wide feed")
    # Other mandatory grid lines can intrude into the requested edge cell.
    # Inspect the finished grid, not just the requested hint coordinates.
    edge_audit = []
    ys = np.asarray(mesh.GetLines("y"))
    for centre in p["y_mm"]:
        for edge, side in [(centre - w / 2, 1), (centre + w / 2, -1)]:
            index = np.searchsorted(ys, edge)
            lower, upper = ys[index - 1 : index + 1]
            inner = upper - edge if side == 1 else edge - lower
            fraction = inner / (upper - lower)
            edge_audit.append(
                {
                    "edge_mm": edge,
                    "neighbors_mm": [float(lower), float(upper)],
                    "inside_fraction": float(fraction),
                    "thirds_rule_satisfied": bool(abs(fraction - 1 / 3) < 1e-10),
                }
            )
    if m.get("verify_feed_edges", False) and not all(
        e["thirds_rule_satisfied"] for e in edge_audit
    ):
        raise ValueError(
            "Actual feed-edge grid violates thirds rule; refine local_mm to avoid intervening mask lines"
        )
    mesh.AddLine("z", np.linspace(0, h, m["substrate_cells"] + 1))
    if t > 0:
        mesh.AddLine("z", [h + t])
    mesh.AddLine("z", domain["air_top_mm"])
    mesh.SmoothMeshLines("z", dx, 1.4)
    sub = cs.AddMaterial(
        "substrate", epsilon=s["epsilon_r"], kappa=s["conductivity_S_m"]
    )
    sub.AddBox(
        [-length, domain["y_mm"][0], 0], [length, domain["y_mm"][1], h], priority=0
    )
    metal = cs.AddMetal("PEC")
    if c["metal"]["model"] != "PEC":
        raise ValueError("Only explicit PEC preliminary model is supported")
    for start, stop in [*boxes(c), *terminals]:
        metal.AddBox(start, stop, priority=10)
    for via in g.get("shorts", []):
        x, y = via["xy_mm"]
        b = via["width_mm"] / 2
        metal.AddBox([x - b, y - b, 0], [x + b, y + b, h + t], priority=20)
    ports = []
    for i, sign in enumerate([-1, 1]):
        y = p["y_mm"][i]
        start = [sign * length, y - w / 2, h]
        stop = [sign * port_end, y + w / 2, 0]
        ports.append(
            fdtd.AddMSLPort(
                i + 1,
                metal,
                start,
                stop,
                "x",
                "z",
                excite=-1 if excitation == i + 1 else 0,
                FeedShift=p["feed_shift_mm"],
                MeasPlaneShift=p["measurement_shift_mm"],
                priority=10,
            )
        )
        # The stock current probe encloses a zero-thickness sheet. Extend its
        # contour to enclose the whole conductor volume when thickness > 0.
        if t > 0:
            for name in ports[-1].I_filenames:
                prop = cs.GetPropertiesByName(name)[0]
                primitive = prop.GetPrimitive(0)
                stop_i = primitive.GetStop()
                stop_i[2] = h + t
                primitive.SetStop(stop_i)
        # MSLPort defines a sheet; add the explicitly configured top metal thickness.
        if t > 0:
            metal.AddBox(
                [min(start[0], stop[0]), y - w / 2, h],
                [max(start[0], stop[0]), y + w / 2, h + t],
                priority=10,
            )
    lines = {axis: np.asarray(mesh.GetLines(axis)).tolist() for axis in "xyz"}
    counts = [len(lines[a]) - 1 for a in "xyz"]
    cells = int(np.prod(counts))
    if cells > c["solver"]["max_cells"]:
        raise ValueError(f"Cell budget exceeded: {cells}")
    return (
        fdtd,
        cs,
        ports,
        {
            "lines_mm": lines,
            "feed_edge_audit": edge_audit,
            "cell_counts": counts,
            "cells": cells,
            "rough_memory_MiB": cells * 200 / 2**20,
            "note": "200 bytes/geometric cell field-only estimate, excludes Python/native overhead; solver counts grid nodes, actual RSS recorded separately",
        },
    )
