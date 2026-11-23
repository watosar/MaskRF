# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Contract and failure-path tests; native smoke simulation is run separately."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import yaml
from PIL import Image
from solver_stub import complete_solver

import maskrf.__main__ as cli
from maskrf import SimulationError, evaluate_mask, load_response
from maskrf.api import DEFAULT_CONFIG, read_mask

RUN = Path(__file__).resolve().parent / "fixtures/completed-run"
MASK = read_mask(RUN / "mask.csv")


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="maskrf-interface-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        ready = patch("maskrf.api.prepare_solver", return_value=dict(os.environ))
        ready.start()
        self.addCleanup(ready.stop)

    def test_formats_and_orientation(self):
        pattern = np.zeros((16, 16), dtype=int)
        pattern[0, 2] = 1
        pattern[7, 15] = 1
        np.savetxt(self.directory / "mask.csv", pattern, delimiter=",", fmt="%d")
        (self.directory / "mask.json").write_text(json.dumps(pattern.tolist()))
        Image.fromarray(((1 - pattern) * 255).astype("uint8")).save(
            self.directory / "mask.png"
        )
        for value in [
            pattern,
            pattern.tolist(),
            pattern.astype(bool),
            self.directory / "mask.csv",
            self.directory / "mask.json",
            self.directory / "mask.png",
        ]:
            np.testing.assert_array_equal(read_mask(value), pattern)
        Image.fromarray(np.full((16, 16), 127, dtype="uint8")).save(
            self.directory / "gray.png"
        )
        with self.assertRaises(ValueError):
            read_mask(self.directory / "gray.png")

    def test_invalid_masks(self):
        for value in [
            np.zeros((18, 18)),
            np.zeros(256),
            [[1], [1, 0]],
            np.full((16, 16), 0.5),
            np.full((16, 16), np.nan),
            np.full((16, 16), "1"),
            np.ones((16, 16), dtype=complex),
        ]:
            with self.subTest(value=str(type(value))), self.assertRaises(ValueError):
                read_mask(value)

    def test_saved_response_preserves_component_order(self):
        response = load_response(RUN)
        self.assertEqual(response.execution, "loaded")
        self.assertEqual(response.s.shape, (401, 2, 2))
        csv = np.genfromtxt(RUN / "sparameters.csv", names=True, delimiter=",")
        for i in range(2):
            for j in range(2):
                key = f"s{i + 1}{j + 1}"
                np.testing.assert_array_equal(
                    response.s[:, i, j], csv[key + "_real"] + 1j * csv[key + "_imag"]
                )
        self.assertAlmostEqual(
            response.metrics["max_coherent_power_ratio"], 1.004539833147887
        )

    def test_evaluate_runs_solver_and_saves_response(self):
        out = self.directory / "simulated"
        with patch("maskrf.api.subprocess.run", side_effect=complete_solver):
            response = evaluate_mask(MASK, out)
        self.assertEqual(response.execution, "simulated")
        self.assertEqual(response.run_dir, out / "run")
        np.testing.assert_array_equal(response.s, load_response(RUN).s)
        np.testing.assert_array_equal(load_response(out).s, response.s)
        np.testing.assert_array_equal(read_mask(out / "mask.csv"), MASK)
        self.assertTrue((out / "execution.log").is_file())
        doc = json.loads((out / "response.json").read_text())
        self.assertEqual(doc["execution"], "simulated")
        self.assertFalse(doc["validation"]["mesh_convergence_checked_by_this_call"])
        self.assertEqual(
            doc["settings"]["geometry"]["shorts"],
            response.settings["geometry"]["shorts"],
        )
        self.assertAlmostEqual(
            doc["metrics"]["max_coherent_power_ratio"], 1.004539833147887
        )
        with self.assertRaises(FileExistsError):
            evaluate_mask(MASK, out)

    def test_evaluate_passes_changed_mask_and_conditions_to_solver(self):
        changed = MASK.copy()
        changed[8, 8] = 1 - changed[8, 8]
        c = yaml.safe_load(DEFAULT_CONFIG.read_text())
        c["substrate"]["epsilon_r"] = 4
        path = self.directory / "changed.yaml"
        path.write_text(yaml.safe_dump(c))
        out = self.directory / "custom"
        with patch("maskrf.api.subprocess.run", side_effect=complete_solver):
            response = evaluate_mask(changed, out, config_path=path)
        np.testing.assert_array_equal(response.mask, changed)
        self.assertEqual(response.settings["substrate"]["epsilon_r"], 4)
        self.assertEqual(
            json.loads((out / "request.json").read_text())["config_source"], str(path)
        )

    def test_incomplete_and_undecayed_results(self):
        for label, status in [
            (
                "missing-port",
                [
                    {
                        "excitation": 1,
                        "exit_code": 0,
                        "normal_finish": True,
                        "decay_confirmed": True,
                    }
                ],
            ),
            (
                "not-decayed",
                [
                    {
                        "excitation": i,
                        "exit_code": 0,
                        "normal_finish": True,
                        "decay_confirmed": False,
                    }
                    for i in [1, 2]
                ],
            ),
        ]:
            path = self.directory / label
            path.mkdir()
            (path / "status.json").write_text(json.dumps(status))
            with self.assertRaises(SimulationError):
                load_response(path)

    def test_failure_does_not_return_response(self):
        with (
            patch(
                "maskrf.api.subprocess.run",
                return_value=subprocess.CompletedProcess([], 9),
            ) as child,
            self.assertRaises(SimulationError),
        ):
            evaluate_mask(MASK, self.directory / "failed")
        self.assertEqual(
            child.call_args.args[0][:6],
            ["uv", "run", "--no-project", "--python", sys.executable, "-m"],
        )
        self.assertNotIn("cwd", child.call_args.kwargs)
        self.assertFalse((self.directory / "failed/response.json").exists())
        self.assertEqual(
            json.loads((self.directory / "failed/error.json").read_text())["status"],
            "failed",
        )

    def test_nonfinite_results_are_rejected(self):
        path = self.directory / "nonfinite"
        path.mkdir()
        for filename in ["status.json", "effective.json", "mask.csv", "metrics.json"]:
            (path / filename).write_bytes((RUN / filename).read_bytes())
        data = np.genfromtxt(RUN / "sparameters.csv", names=True, delimiter=",")
        data["s11_real"][0] = np.nan
        names = data.dtype.names
        assert names is not None
        np.savetxt(
            path / "sparameters.csv",
            np.column_stack([data[k] for k in names]),
            delimiter=",",
            header=",".join(names),
            comments="",
        )
        with self.assertRaises(SimulationError):
            load_response(path)

    def test_cli_json_and_errors(self):
        command = [
            "maskrf",
            "evaluate",
            "--mask",
            str(RUN / "mask.csv"),
            "--out",
            str(self.directory / "cli"),
        ]
        output = io.StringIO()
        with (
            patch.object(sys, "argv", command),
            patch("maskrf.api.subprocess.run", side_effect=complete_solver),
            contextlib.redirect_stdout(output),
        ):
            cli.main()
        self.assertEqual(json.loads(output.getvalue())["execution"], "simulated")
        self.assertTrue((self.directory / "cli/response.json").is_file())
        bad = self.directory / "invalid.json"
        bad.write_text("[[2]]")
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "maskrf",
                "evaluate",
                "--mask",
                str(bad),
                "--out",
                str(self.directory / "invalid-output"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["status"], "failed")

    def test_removed_reuse_option_is_rejected_before_creating_output(self):
        out = self.directory / "removed-option"
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "maskrf",
                "evaluate",
                "--mask",
                str(RUN / "mask.csv"),
                "--out",
                str(out),
                "--reuse-run",
                str(RUN),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
