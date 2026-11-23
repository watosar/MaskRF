# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exercise solver completion and comparison acceptance without native FDTD."""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import yaml

import maskrf.__main__ as cli
from maskrf import load_response

PROJECT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT / "tests/fixtures/completed-run"
FINISHED = "Time for 400000 iterations with 5491200.00 cells : 1.00 sec\n"
UNDECAYED = (
    "RunFDTD: Warning: Max. number of timesteps was reached before the end-criteria of -70dB was reached...\n"
    + FINISHED
)


class Worker:
    def __init__(self, log, exit_code, stdout):
        self.pid = 999999999
        self.exit_code = exit_code
        stdout.write(log)
        stdout.flush()

    def wait(self, timeout=None):
        return self.exit_code


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((FIXTURE / "effective.json").read_text())
        cls.config["geometry"]["file"] = str(FIXTURE / "mask.csv")
        cls.response = load_response(FIXTURE)

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="maskrf-execution-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        ready = patch.object(cli, "prepare_solver", return_value=dict(os.environ))
        ready.start()
        self.addCleanup(ready.stop)

    def workers(self, outputs):
        iterator = iter(outputs)

        def launch(command, *, stdout, stderr, start_new_session):
            log, code = next(iterator)
            return Worker(log, code, stdout)

        return patch.object(cli.subprocess, "Popen", side_effect=launch)

    def test_inspect_accepts_mask_with_default_or_custom_config(self):
        mask = np.zeros((16, 16), dtype=int)
        mask[3, 5] = 1
        csv_path = self.directory / "input.csv"
        np.savetxt(csv_path, mask, delimiter=",", fmt="%d")
        json_path = self.directory / "input.json"
        json_path.write_text(json.dumps(mask.tolist()))
        settings = copy.deepcopy(self.config)
        settings["geometry"].pop("file")
        settings["substrate"]["epsilon_r"] = 4.4
        custom = self.directory / "custom.yaml"
        custom.write_text(yaml.safe_dump(settings))
        out = self.directory / "inspection"

        def inspect_config(config, destination):
            np.testing.assert_array_equal(
                cli.load_mask(config["geometry"]["file"]), mask
            )
            self.assertEqual(config["substrate"]["epsilon_r"], epsilon_r)
            self.assertEqual(Path(destination), out)
            return {"lines_mm": {}, "cells": 10}

        for path, options, epsilon_r in (
            (csv_path, [], 3.66),
            (json_path, ["--config", str(custom)], 4.4),
        ):
            with (
                self.subTest(path=path),
                patch.object(
                    sys,
                    "argv",
                    [
                        "maskrf",
                        "inspect",
                        "--mask",
                        str(path),
                        "--out",
                        str(out),
                        *options,
                    ],
                ),
                patch.object(cli, "inspect", side_effect=inspect_config) as inspect,
                patch("builtins.print"),
            ):
                cli.main()
                inspect.assert_called_once()

    def test_run_rejects_undecayed_before_next_excitation(self):
        out = self.directory / "run"
        with (
            patch.object(cli, "inspect"),
            self.workers([(UNDECAYED, 0)]) as workers,
            patch.object(cli, "process") as process,
            self.assertRaisesRegex(RuntimeError, "decay criterion"),
        ):
            cli.run(copy.deepcopy(self.config), out)
        self.assertEqual(workers.call_count, 1)
        process.assert_not_called()
        statuses = json.loads((out / "status.json").read_text())
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["exit_code"], 0)
        self.assertTrue(statuses[0]["normal_finish"])
        self.assertFalse(statuses[0]["decay_confirmed"])
        self.assertFalse((out / "solver-2.log").exists())
        self.assertFalse((out / "sparameters.csv").exists())

    def test_run_rejects_missing_normal_finish(self):
        out = self.directory / "run"
        with (
            patch.object(cli, "inspect"),
            self.workers([("Interrupted before finishing\n", 0)]) as workers,
            patch.object(cli, "process") as process,
            self.assertRaisesRegex(RuntimeError, "did not finish normally"),
        ):
            cli.run(copy.deepcopy(self.config), out)
        self.assertEqual(workers.call_count, 1)
        process.assert_not_called()
        self.assertFalse(
            json.loads((out / "status.json").read_text())[0]["normal_finish"]
        )

    def test_run_rejects_second_undecayed_excitation(self):
        out = self.directory / "run"
        with (
            patch.object(cli, "inspect"),
            self.workers([(FINISHED, 0), (UNDECAYED, 0)]) as workers,
            patch.object(cli, "process") as process,
            self.assertRaisesRegex(RuntimeError, "excitation 2"),
        ):
            cli.run(copy.deepcopy(self.config), out)
        self.assertEqual(workers.call_count, 2)
        process.assert_not_called()
        statuses = json.loads((out / "status.json").read_text())
        self.assertEqual([s["decay_confirmed"] for s in statuses], [True, False])

    def test_run_rejects_nonzero_exit(self):
        out = self.directory / "run"
        with (
            patch.object(cli, "inspect"),
            self.workers([(FINISHED, 9)]),
            patch.object(cli, "process") as process,
            self.assertRaisesRegex(RuntimeError, "Solver failed \\(9\\)"),
        ):
            cli.run(copy.deepcopy(self.config), out)
        process.assert_not_called()
        self.assertEqual(
            json.loads((out / "status.json").read_text())[0]["exit_code"], 9
        )

    def test_run_processes_only_after_both_complete(self):
        out = self.directory / "run"
        with (
            patch.object(cli, "inspect"),
            self.workers([(FINISHED, 0), (FINISHED, 0)]) as workers,
            patch.object(cli, "process") as process,
        ):
            self.assertEqual(cli.run(copy.deepcopy(self.config), out), out.resolve())
        self.assertEqual(workers.call_count, 2)
        process.assert_called_once_with(out.resolve())
        self.assertTrue(
            all(
                s["decay_confirmed"]
                for s in json.loads((out / "status.json").read_text())
            )
        )

    def test_convergence_stops_before_next_mesh_and_comparison(self):
        out = self.directory / "convergence"
        arguments = [
            "maskrf",
            "convergence",
            "--config",
            str(PROJECT / "examples/configs/paper_corrected.yaml"),
            "--out",
            str(out),
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch.object(cli, "inspect"),
            self.workers([(UNDECAYED, 0)]) as workers,
            patch.object(cli, "process") as process,
            patch.object(cli, "compare_runs") as compare,
            self.assertRaises(RuntimeError),
        ):
            cli.main()
        self.assertEqual(workers.call_count, 1)
        process.assert_not_called()
        compare.assert_not_called()
        self.assertTrue((out / "level-1/status.json").exists())
        self.assertFalse((out / "level-2").exists())

    def status(self):
        return [
            {
                "excitation": i,
                "exit_code": 0,
                "normal_finish": True,
                "decay_confirmed": True,
            }
            for i in (1, 2)
        ]

    def compare(
        self, label, first_status, second_status, *, current_s21_scale: float = 1.0
    ):
        directory = self.directory / label
        directory.mkdir()
        paths = [directory / "previous", directory / "current"]
        for path, statuses in zip(paths, [first_status, second_status]):
            path.mkdir()
            (path / "effective.json").write_text(json.dumps(self.config))
            (path / "status.json").write_text(json.dumps(statuses))
        columns = {
            f"s{i + 1}{j + 1}": self.response.s[:, i, j]
            for i in range(2)
            for j in range(2)
        }
        current_columns = dict(columns)
        current_columns["s21"] = columns["s21"] * current_s21_scale
        responses = [
            (self.response.frequency_Hz, columns, self.response.metrics),
            (self.response.frequency_Hz, current_columns, self.response.metrics),
        ]
        with patch.object(cli, "process", side_effect=responses):
            cli.compare_runs(paths, directory / "comparison")
        return json.loads((directory / "comparison/comparison.json").read_text())

    def test_comparison_accepts_valid_identical_responses(self):
        rows = self.compare("valid", self.status(), self.status())
        self.assertTrue(rows[-1]["full_s_delta_threshold_pass"])
        self.assertTrue(rows[-1]["both_runs_completed_and_decayed"])
        self.assertTrue(rows[-1]["full_s_threshold_pass"])

    def test_comparison_rejects_invalid_current_previous_or_both(self):
        variants = {}
        for name, field, value in [
            ("undecayed", "decay_confirmed", False),
            ("unfinished", "normal_finish", False),
            ("failed", "exit_code", 9),
        ]:
            statuses = self.status()
            statuses[0][field] = value
            variants[name] = statuses
        variants["missing-port"] = self.status()[:1]
        variants["duplicate-port"] = [self.status()[0], self.status()[0]]
        variants["empty"] = []
        for name, invalid in variants.items():
            for side, first, second in [
                ("previous", invalid, self.status()),
                ("current", self.status(), invalid),
                ("both", invalid, invalid),
            ]:
                with self.subTest(reason=name, side=side):
                    rows = self.compare(f"{name}-{side}", first, second)
                    self.assertTrue(rows[-1]["full_s_delta_threshold_pass"])
                    self.assertFalse(rows[-1]["both_runs_completed_and_decayed"])
                    self.assertFalse(rows[-1]["full_s_threshold_pass"])
                    self.assertEqual(
                        rows[-1]["time_decay_confirmed"], side == "previous"
                    )

    def test_completed_responses_still_must_meet_numerical_thresholds(self):
        rows = self.compare(
            "different", self.status(), self.status(), current_s21_scale=1.1
        )
        self.assertTrue(rows[-1]["both_runs_completed_and_decayed"])
        self.assertGreater(rows[-1]["max_complex_delta"], 0.02)
        self.assertGreater(rows[-1]["passband_s21_max_delta_dB"], 0.2)
        self.assertFalse(rows[-1]["full_s_delta_threshold_pass"])
        self.assertFalse(rows[-1]["full_s_threshold_pass"])


if __name__ == "__main__":
    unittest.main()
