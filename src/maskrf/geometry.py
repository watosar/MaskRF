from math import isfinite
from pathlib import Path
from typing import cast

import numpy as np
from scipy.ndimage import label


def load_mask(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        a = np.loadtxt(path, delimiter=",", ndmin=2)
    else:
        from PIL import Image

        a = np.asarray(Image.open(path).convert("L"))
        if not np.isin(a, [0, 255]).all():
            raise ValueError(
                "PNG must be strictly black/white; no implicit thresholding"
            )
        a = (a == 0).astype(int)  # black = metal
    if not np.isin(a, [0, 1]).all():
        raise ValueError("Mask must contain only 0 and 1")
    return a.astype(int)


def boxes(c):
    g = c["geometry"]
    h = c["substrate"]["thickness_mm"]
    t = c["metal"]["thickness_mm"]
    result = []
    if g["kind"] == "mask":
        a = load_mask(g["file"])
        p = g["pitch_mm"]
        ny, nx = a.shape
        for r, col in np.argwhere(a):
            x = (col - nx / 2) * p
            y = (ny / 2 - r - 1) * p
            result.append(([x, y, h], [x + p, y + p, h + t]))
    elif g["kind"] == "notch":
        w = c["ports"]["width_mm"]
        result.append(([-w / 2, w / 2, h], [w / 2, w / 2 + g["stub_mm"], h + t]))
    elif g["kind"] != "straight":
        raise ValueError("Unknown geometry kind")
    return result


def terminal_boxes(c, half):
    """Return top-metal pads and narrow feed ends in addition to the mask."""
    h = c["substrate"]["thickness_mm"]
    top = h + c["metal"]["thickness_mm"]
    result = []
    for via in c["geometry"].get("shorts", []):
        if "pad_width_mm" in via:
            width = via["pad_width_mm"]
            if not isfinite(width) or width <= 0:
                raise ValueError("pad_width_mm must be positive and finite")
            x, y = via["xy_mm"]
            b = width / 2
            result.append(([x - b, y - b, h], [x + b, y + b, top]))

    p = c["ports"]
    if "neck" in p:
        length = p["neck"]["length_mm"]
        width = p["neck"]["width_mm"]
        if not 0 < width <= p["width_mm"]:
            raise ValueError(
                "ports.neck.width_mm must be positive and at most ports.width_mm"
            )
        probe_step = c["mesh"].get("probe_step_mm", 0)
        probe_reach = max(p["feed_shift_mm"], p["measurement_shift_mm"] + probe_step)
        if not 0 < length < p["feed_length_mm"] - probe_reach:
            raise ValueError(
                "ports.neck.length_mm must leave excitation and probes on the wide feed"
            )
        for sign, y in zip((-1, 1), p["y_mm"]):
            x0, x1 = sorted((sign * half, sign * (half + length)))
            result.append(([x0, y - width / 2, h], [x1, y + width / 2, top]))
    return result


def mask_audit(c):
    if c["geometry"]["kind"] != "mask":
        return {}
    a = load_mask(c["geometry"]["file"])
    p = c["geometry"]["pitch_mm"]
    # Without an output argument, label returns the labeled array and its count.
    _, n4 = cast(tuple[np.ndarray, int], label(a))
    _, n8 = cast(tuple[np.ndarray, int], label(a, np.ones((3, 3))))
    d = (a[:-1, :-1] + a[1:, 1:] == 2) & (a[:-1, 1:] + a[1:, :-1] == 0)
    e = (a[:-1, 1:] + a[1:, :-1] == 2) & (a[:-1, :-1] + a[1:, 1:] == 0)
    return {
        "shape": list(a.shape),
        "size_mm": [a.shape[1] * p, a.shape[0] * p],
        "metal_cells": int(a.sum()),
        "connected_components_edge": n4,
        "connected_components_corner": n8,
        "corner_only_contacts": int(d.sum() + e.sum()),
        "convention": "row 0 is +y; column 0 is -x; centre origin; mm; 1=metal; no repairs",
    }
