"""Check target units, amplitude scoring, and the public-API consumer CLI."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from solver_stub import complete_solver

from maskrf import load_response

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "examples/score_mask.py"
spec = importlib.util.spec_from_file_location("score_mask_example", SCRIPT)
assert spec is not None and spec.loader is not None
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class ScoreMaskTests(unittest.TestCase):
    def setUp(self):
        ready = patch("maskrf.api.prepare_solver", return_value=dict(os.environ))
        ready.start()
        self.addCleanup(ready.stop)

    def test_squared_and_maximum_errors(self):
        # Amplitude errors are 0 and .6. MSE=.18; RMSE=sqrt(.18); max=.6.
        expected = {"mae": 0.3, "mse": 0.18, "rmse": 0.4242640687119285, "max": 0.6}
        for metric, value in expected.items():
            with self.subTest(metric=metric):
                actual = example.s21_error(
                    [10e9, 12e9], [1j, -0.4], [10e9, 12e9], [1, 1], metric=metric
                )
                self.assertIs(type(actual), float)
                self.assertAlmostEqual(actual, value)
        self.assertAlmostEqual(
            example.s21_error([10e9, 12e9], [1j, -0.4], [10e9, 12e9], [1, 1]),
            expected["rmse"],
        )

    def test_mae_and_rmse_rank_candidates_differently(self):
        frequencies = [10e9, 11e9, 12e9]
        target = [1, 1, 1]
        a, b = [1, 1, 0.4], [0.75, 0.75, 0.75]
        scores = {
            metric: (
                example.s21_error(frequencies, a, frequencies, target, metric=metric),
                example.s21_error(frequencies, b, frequencies, target, metric=metric),
            )
            for metric in ("mae", "mse", "rmse", "max")
        }
        self.assertLess(*scores["mae"])
        for metric in ("mse", "rmse", "max"):
            self.assertGreater(*scores[metric])

    def test_mean_absolute_magnitude_error_and_phase(self):
        # Errors .4 and .4, averaged over two points; phases must not affect them.
        value = example.s21_mae([10e9, 12e9], [0.6j, -0.4], [10e9, 12e9], [1, 0])
        self.assertIs(type(value), float)
        self.assertAlmostEqual(value, 0.4)
        # Magnitudes .2 and .8 interpolate to .5; interpolating complex waves differs.
        self.assertAlmostEqual(
            example.s21_mae([10e9, 12e9], [0.2, 0.8j], [11e9], [0.5]), 0
        )

    def test_decibel_and_linear_target_units(self):
        linear = example.parse_target_csv("frequency_GHz,s21_magnitude\n10,1\n12,.1\n")
        decibel = example.parse_target_csv("frequency_GHz,s21_dB\n10,0\n12,-20\n")
        np.testing.assert_array_equal(linear[0], [10e9, 12e9])
        np.testing.assert_allclose(linear[1], [1, 0.1])
        np.testing.assert_allclose(decibel, linear)

    def test_invalid_values_and_extrapolation_are_rejected(self):
        for frequencies, magnitudes in (
            ([9e9], [1]),
            ([13e9], [1]),
            ([10e9, 10e9], [1, 1]),
            ([12e9, 10e9], [1, 1]),
            ([10e9], [np.nan]),
            ([10e9], [-1]),
        ):
            with (
                self.subTest(frequencies=frequencies, magnitudes=magnitudes),
                self.assertRaises(ValueError),
            ):
                example.s21_mae([10e9, 12e9], [0.2, 0.8], frequencies, magnitudes)
        for text in (
            "frequency_GHz,s21_magnitude\n",
            "frequency_GHz,s21_dB\n10,-inf\n",
            "frequency_GHz,s21_dB\n10,1e9\n",
            "frequency_GHz,s21_magnitude\n10,1,2\n",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                example.parse_target_csv(text)

    def test_invalid_target_does_not_invoke_simulator(self):
        with tempfile.TemporaryDirectory(prefix="maskrf-score-mask-") as directory:
            target = Path(directory) / "invalid.csv"
            target.write_text("frequency_GHz,s21_magnitude\n10,nan\n")
            with patch.object(example, "evaluate_mask") as evaluate:
                with self.assertRaises(ValueError):
                    example.score_mask(
                        np.zeros((16, 16)), target, Path(directory) / "output"
                    )
                evaluate.assert_not_called()
                self.assertFalse((Path(directory) / "output").exists())

    def test_invalid_metric_does_not_invoke_simulator(self):
        with patch.object(example, "evaluate_mask") as evaluate:
            with self.assertRaisesRegex(ValueError, "Unknown metric"):
                example.score_mask(
                    np.zeros((16, 16)), "not-read.csv", "not-created", metric="unknown"
                )
            evaluate.assert_not_called()

    def test_cli_runs_simulator_and_prints_only_float(self):
        with tempfile.TemporaryDirectory(prefix="maskrf-score-mask-") as directory:
            out = Path(directory) / "result"
            target = Path(directory) / "target.csv"
            target.write_text("frequency_GHz,s21_magnitude\n10.5,1\n12,0\n")
            output = io.StringIO()
            with (
                patch("maskrf.api.subprocess.run", side_effect=complete_solver),
                contextlib.redirect_stdout(output),
            ):
                returncode = example.main(
                    [
                        "--mask",
                        str(PROJECT / "examples/data/fig3a-mask.csv"),
                        "--target",
                        str(target),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(returncode, 0)
            value = float(output.getvalue())
            self.assertEqual(output.getvalue(), f"{value}\n")
            # 60-digit Decimal reference from the fixture's real/imaginary components.
            # |S21| at 10.5 and 12 GHz is .6364795251 and .8240304457.
            self.assertAlmostEqual(value, 0.6368568563857028)
            record = json.loads((out / "score.json").read_text())
            self.assertEqual(record["metric"], "s21_magnitude_rmse")
            self.assertEqual(record["sample_count"], 2)
            self.assertEqual(record["value"], value)
            self.assertEqual((out / "target.csv").read_bytes(), target.read_bytes())
            self.assertEqual(
                json.loads((out / "response.json").read_text())["execution"],
                "simulated",
            )
            with patch("maskrf.api.subprocess.run", side_effect=complete_solver):
                direct = example.score_mask(
                    PROJECT / "examples/data/fig3a-mask.csv",
                    target,
                    Path(directory) / "python-default",
                )
            self.assertIs(type(direct), float)
            self.assertEqual(direct, value)

    def test_saved_response_can_be_scored_without_simulating(self):
        response = load_response(PROJECT / "tests/fixtures/completed-run")
        value = example.s21_error(
            response.frequency_Hz, response.s[:, 1, 0], [10.5e9, 12e9], [1, 0]
        )
        self.assertAlmostEqual(value, 0.6368568563857028)

    def test_cli_rejects_invalid_target_from_other_directory(self):
        with tempfile.TemporaryDirectory(prefix="maskrf-score-mask-") as directory:
            target = Path(directory) / "invalid.csv"
            target.write_text("frequency_GHz,s21_magnitude\n10,nan\n")
            out = Path(directory) / "result"
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    str(SCRIPT),
                    "--mask",
                    str(PROJECT / "examples/data/fig3a-mask.csv"),
                    "--target",
                    str(target),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("Target values must be finite", result.stderr)
            self.assertFalse(out.exists())

    def test_removed_reuse_option_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory(prefix="maskrf-score-mask-") as directory:
            out = Path(directory) / "removed-option"
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    str(SCRIPT),
                    "--mask",
                    str(PROJECT / "examples/data/fig3a-mask.csv"),
                    "--target",
                    str(PROJECT / "examples/data/lowpass-target.csv"),
                    "--out",
                    str(out),
                    "--reuse-run",
                    str(PROJECT / "tests/fixtures/completed-run"),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=directory,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
