# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Recover known complex S matrices through the production postprocessor."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from maskrf import postprocess


class PostprocessTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="maskrf-postprocess-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def test_production_extraction_and_saved_component_order(self):
        out = self.directory / "known-two-port"
        out.mkdir()
        config = {
            "geometry": {"kind": "mask", "file": "unused-by-synthetic-build.csv"},
            "frequency_GHz": [10, 30, 5],
            "solver": {"excitations": [1, 2]},
            "ports": {"reference_ohm": 50},
            "validation": {"passband_GHz": [10, 15]},
        }
        (out / "effective.json").write_text(json.dumps(config))
        frequency = np.linspace(10e9, 30e9, 5)
        s = np.array(
            [
                [
                    [0.1 + 0.03j * k, 0.2 - 0.02j * k],
                    [0.7 * np.exp(-0.2j * k), -0.08 + 0.04j * k],
                ]
                for k in range(5)
            ]
        )
        a = np.array(
            [
                [[1 + 0.05j * k, 0.12 + 0.02j * k], [0.18 - 0.03j * k, 1.1 - 0.04j * k]]
                for k in range(5)
            ]
        )
        b = s @ a
        calls = []

        class Port:
            def __init__(self, port, excitation):
                self.uf_inc = a[:, port, excitation - 1]
                self.uf_ref = b[:, port, excitation - 1]

            def CalcPort(self, directory, frequencies, ref_impedance):
                calls.append((directory, frequencies.copy(), ref_impedance))

        def build(settings, excitation):
            return None, None, [Port(i, excitation) for i in range(2)], None

        with patch.object(postprocess, "build", side_effect=build) as native:
            actual_frequency, columns, metrics = postprocess.process(out)
        self.assertEqual([call.args[1] for call in native.call_args_list], [1, 2])
        self.assertEqual(len(calls), 4)
        for directory, frequencies, impedance in calls:
            self.assertIn(Path(directory).name, ["excite-1", "excite-2"])
            np.testing.assert_array_equal(frequencies, frequency)
            self.assertEqual(impedance, 50)
        np.testing.assert_array_equal(actual_frequency, frequency)

        csv = np.genfromtxt(out / "sparameters.csv", delimiter=",", names=True)
        np.testing.assert_array_equal(csv["frequency_Hz"], frequency)
        for i in range(2):
            for j in range(2):
                key = f"s{i + 1}{j + 1}"
                np.testing.assert_allclose(columns[key], s[:, i, j], rtol=0, atol=1e-14)
                np.testing.assert_allclose(
                    csv[key + "_real"] + 1j * csv[key + "_imag"],
                    s[:, i, j],
                    rtol=0,
                    atol=1e-14,
                )

        touchstone = np.loadtxt(out / "network.s2p", comments=["!", "#"])
        np.testing.assert_array_equal(touchstone[:, 0], frequency)
        for position, (i, j) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
            values = (
                touchstone[:, 1 + 2 * position] + 1j * touchstone[:, 2 + 2 * position]
            )
            np.testing.assert_allclose(values, s[:, i, j], rtol=0, atol=1e-12)

        self.assertEqual(
            metrics["extraction"], "S=B inv(A), both incident waves retained"
        )
        self.assertGreater(metrics["unexcited_port_incident_ratio"]["1"], 0)
        self.assertGreater(metrics["unexcited_port_incident_ratio"]["2"], 0)
        assert "max_singular_value" in metrics
        np.testing.assert_allclose(
            metrics["max_singular_value"],
            np.linalg.svd(s, compute_uv=False).max(),
            atol=1e-14,
        )
        self.assertEqual(json.loads((out / "metrics.json").read_text()), metrics)
        self.assertTrue((out / "sparameters.png").exists())


if __name__ == "__main__":
    unittest.main()
