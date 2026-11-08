"""Focused checks of coordinate convention and rejection of invalid mask data."""

import tempfile
from pathlib import Path

import numpy as np

from maskrf.geometry import boxes, load_mask

Path("tmp/geometry-checks").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir="tmp/geometry-checks") as tmp:
    p = Path(tmp) / "mask.csv"
    np.savetxt(p, [[1, 0, 0], [0, 0, 1]], fmt="%d", delimiter=",")
    c = {
        "geometry": {"kind": "mask", "file": str(p), "pitch_mm": 0.2},
        "substrate": {"thickness_mm": 0.1},
        "metal": {"thickness_mm": 0.035},
    }
    b = boxes(c)
    assert np.allclose(b[0][0], [-0.3, 0, 0.1]) and np.allclose(
        b[0][1], [-0.1, 0.2, 0.135]
    )
    assert np.allclose(b[1][0], [0.1, -0.2, 0.1])
    assert load_mask(p).sum() == 2
    p.write_text("0,0.5\n1,0\n")
    try:
        load_mask(p)
    except ValueError:
        pass
    else:
        raise AssertionError("nonbinary CSV accepted")
print(
    "PASS: asymmetric mask coordinates, dimensions, preservation, nonbinary rejection"
)
