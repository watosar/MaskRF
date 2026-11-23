# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check the configured metal added at the feed and shorting terminals."""

import unittest
from pathlib import Path

import numpy as np

from maskrf.geometry import terminal_boxes


class TerminalGeometryTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "geometry": {
                "kind": "mask",
                "file": str(Path(__file__).parent / "fixtures/completed-run/mask.csv"),
                "pitch_mm": 0.125,
                "shorts": [
                    {"xy_mm": [-0.9375, 1.0625], "width_mm": 0.1, "pad_width_mm": 0.125}
                ],
            },
            "substrate": {"thickness_mm": 0.16764},
            "metal": {"thickness_mm": 0.035},
            "ports": {
                "feed_length_mm": 12,
                "feed_shift_mm": 2,
                "measurement_shift_mm": 3,
                "width_mm": 0.35,
                "y_mm": [-0.5625, -0.6875],
                "neck": {"length_mm": 0.125, "width_mm": 0.125},
            },
            "mesh": {"probe_step_mm": 0.025},
        }

    def test_pad_and_narrow_feed_sections(self):
        pad, left, right = terminal_boxes(self.settings, 1.0)
        np.testing.assert_allclose(pad, [[-1, 1, 0.16764], [-0.875, 1.125, 0.20264]])
        np.testing.assert_allclose(
            left, [[-1.125, -0.625, 0.16764], [-1, -0.5, 0.20264]]
        )
        np.testing.assert_allclose(
            right, [[1, -0.75, 0.16764], [1.125, -0.625, 0.20264]]
        )

    def test_feed_neck_cannot_include_measurement_probes(self):
        self.settings["ports"]["neck"]["length_mm"] = 9
        with self.assertRaisesRegex(ValueError, "wide feed"):
            terminal_boxes(self.settings, 1.0)

    def test_legacy_config_has_no_added_terminal_metal(self):
        del self.settings["ports"]["neck"]
        del self.settings["geometry"]["shorts"][0]["pad_width_mm"]
        self.assertEqual(terminal_boxes(self.settings, 1.0), [])
