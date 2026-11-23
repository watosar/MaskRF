# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check XDG installation paths and first-use setup behavior."""

import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maskrf import SimulationError, evaluate_mask, load_response, runtime

PROJECT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="maskrf-runtime-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.environment = dict(os.environ)
        self.environment.update(
            XDG_DATA_HOME=str(self.directory / "data"),
            XDG_CACHE_HOME=str(self.directory / "cache"),
            XDG_STATE_HOME=str(self.directory / "state"),
        )
        self.environment.pop("MASKRF_NATIVE", None)
        self.environment.pop("LD_LIBRARY_PATH", None)
        self.environment.pop("MPLCONFIGDIR", None)
        self.environment["PYTHONPATH"] = str(self.directory / "modules")

    def installed_files(self, environment):
        root = runtime.solver_paths().data
        (root / "lib").mkdir(parents=True)
        for name in ("libopenEMS.so", "libCSXCAD.so"):
            (root / "lib" / name).touch()
        modules = self.directory / "modules"
        modules.mkdir(exist_ok=True)
        (modules / "openEMS.py").write_text("class openEMS: pass\n")
        (modules / "CSXCAD.py").write_text("class ContinuousStructure: pass\n")

    def test_xdg_defaults_ignore_empty_or_relative_paths(self):
        for value in ("", "relative"):
            with (
                self.subTest(value=value),
                patch.dict(
                    os.environ,
                    {
                        "XDG_DATA_HOME": value,
                        "XDG_CACHE_HOME": value,
                        "XDG_STATE_HOME": value,
                    },
                ),
            ):
                paths = runtime.solver_paths()
                self.assertEqual(
                    paths.data, Path.home() / ".local/share/maskrf/openems-0.0.36"
                )
                self.assertEqual(
                    paths.cache, Path.home() / ".cache/maskrf/openems-0.0.36"
                )
                self.assertEqual(paths.state, Path.home() / ".local/state/maskrf")

    def test_empty_answer_installs_and_installed_runtime_does_not_prompt_again(self):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch("sys.stdin", io.StringIO("\n")),
            patch.object(runtime, "_install_solver", side_effect=self.installed_files),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            environment = runtime.prepare_solver()
            second = runtime.prepare_solver()
        self.assertEqual(environment, second)
        self.assertEqual(errors.getvalue().count("(Y/n)"), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            environment["LD_LIBRARY_PATH"].split(os.pathsep)[0],
            str(self.directory / "data/maskrf/openems-0.0.36/lib"),
        )

    def test_invalid_answer_reprompts_then_yes_installs(self):
        errors = io.StringIO()
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch("sys.stdin", io.StringIO("unknown\nY\n")),
            patch.object(runtime, "_install_solver", side_effect=self.installed_files),
            contextlib.redirect_stderr(errors),
        ):
            environment = runtime.prepare_solver()
        self.assertEqual(errors.getvalue().count("(Y/n)"), 2)
        self.assertTrue(
            environment["LD_LIBRARY_PATH"].startswith(str(self.directory / "data"))
        )

    def test_eof_does_not_install(self):
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch("sys.stdin", io.StringIO()),
            patch.object(
                runtime,
                "_install_solver",
                side_effect=AssertionError("Unexpected installation"),
            ),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaisesRegex(RuntimeError, "中止"),
        ):
            runtime.prepare_solver()
        self.assertFalse((self.directory / "data").exists())
        self.assertFalse((self.directory / "state").exists())

    def test_declining_api_install_keeps_stdout_and_output_directory_empty(self):
        out = self.directory / "api-output"
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch("sys.stdin", io.StringIO("n\n")),
            patch.object(
                runtime,
                "_install_solver",
                side_effect=AssertionError("Unexpected installation"),
            ),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
            self.assertRaisesRegex(SimulationError, "中止"),
        ):
            evaluate_mask(PROJECT / "examples/data/fig3a-mask.csv", out)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("(Y/n)", errors.getvalue())
        self.assertFalse(out.exists())

    def test_cached_wheels_are_installed_into_the_active_python(self):
        def install(command, *, env, stdout, stderr, check):
            stdout.write(
                json.dumps({"command": command, "python": env["MASKRF_PYTHON"]})
            )
            return subprocess.CompletedProcess(command, 0)

        with patch.dict(os.environ, self.environment, clear=True):
            self.installed_files(self.environment)
            wheels = runtime.solver_paths().data / "wheels"
            wheels.mkdir()
            for name in ("CSXCAD-0.6.2-cp312.whl", "openEMS-0.0.33-cp312.whl"):
                (wheels / name).touch()
            with (
                patch.object(runtime, "_probe", return_value=False),
                patch.object(runtime.subprocess, "run", side_effect=install),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                log = runtime._install_solver(runtime.solver_environment())
        assert log is not None
        record = json.loads(log.read_text())
        self.assertEqual(
            record["command"][:5], ["uv", "pip", "install", "--python", sys.executable]
        )
        self.assertIn("--reinstall", record["command"])
        self.assertEqual(record["python"], sys.executable)
        self.assertEqual(
            len([value for value in record["command"] if value.endswith(".whl")]), 2
        )

    def test_failed_install_reports_log_and_preserves_diagnostics(self):
        def fail(command, *, env, stdout, stderr, check):
            stdout.write("installation diagnostic\n")
            raise subprocess.CalledProcessError(7, command)

        with patch.dict(os.environ, self.environment, clear=True):
            self.installed_files(self.environment)
            wheels = runtime.solver_paths().data / "wheels"
            wheels.mkdir()
            for name in ("CSXCAD-test.whl", "openEMS-test.whl"):
                (wheels / name).touch()
            with (
                patch.object(runtime, "_probe", return_value=False),
                patch.object(runtime.subprocess, "run", side_effect=fail),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaisesRegex(RuntimeError, "ログ") as caught,
            ):
                runtime._install_solver(runtime.solver_environment())
        logs = list((self.directory / "state/maskrf").glob("*.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn(str(logs[0]), str(caught.exception))
        self.assertEqual(logs[0].read_text(), "installation diagnostic\n")

    def test_help_and_saved_response_do_not_prompt_for_installation(self):
        result = subprocess.run(
            ["uv", "run", "--no-sync", "python", "-m", "maskrf", "--help"],
            env=self.environment,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("evaluate", result.stdout)
        self.assertNotIn("(Y/n)", result.stderr)
        self.assertFalse((self.directory / "cache/maskrf").exists())
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch("builtins.input", side_effect=AssertionError("Unexpected prompt")),
        ):
            response = load_response(PROJECT / "tests/fixtures/completed-run")
        self.assertEqual(response.s.shape, (401, 2, 2))
        self.assertFalse((self.directory / "data").exists())

    def test_shell_environment_uses_xdg_locations(self):
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; printf "%s\\n%s\\n" "$LD_LIBRARY_PATH" "$MPLCONFIGDIR"',
                "bash",
                str(PROJECT / "env.sh"),
            ],
            env=self.environment,
            capture_output=True,
            text=True,
            check=True,
        )
        libraries, matplotlib = result.stdout.splitlines()
        self.assertEqual(
            libraries.split(os.pathsep)[0],
            str(self.directory / "data/maskrf/openems-0.0.36/lib"),
        )
        self.assertEqual(matplotlib, str(self.directory / "cache/maskrf/matplotlib"))

    def test_declining_first_install_does_not_create_output(self):
        out = self.directory / "inspection"
        self.environment["MPLCONFIGDIR"] = str(self.directory / "cache/matplotlib")
        result = subprocess.run(
            [
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                "maskrf",
                "inspect",
                "--config",
                str(PROJECT / "examples/configs/straight_fine.yaml"),
                "--out",
                str(out),
            ],
            input="n\n",
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("(Y/n)", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(out.exists())
        self.assertFalse((self.directory / "data").exists())

    def test_missing_required_option_does_not_prompt_for_installation(self):
        result = subprocess.run(
            ["uv", "run", "--no-sync", "python", "-m", "maskrf", "inspect"],
            input="n\n",
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("(Y/n)", result.stderr)

    def test_invalid_config_and_existing_output_do_not_prompt_for_installation(self):
        out = self.directory / "existing-output"
        out.mkdir()
        for command, config in (
            ("inspect", self.directory / "missing.yaml"),
            ("run", PROJECT / "examples/configs/straight_fine.yaml"),
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "--no-sync",
                        "python",
                        "-m",
                        "maskrf",
                        command,
                        "--config",
                        str(config),
                        "--out",
                        str(out),
                    ],
                    input="n\n",
                    env=self.environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("(Y/n)", result.stderr)
        self.assertEqual(list(out.iterdir()), [])

    def test_build_scripts_install_under_xdg_paths_from_another_directory(self):
        root = self.directory / "build with spaces"
        root.mkdir()
        binaries = root / "bin"
        binaries.mkdir()
        uv = shutil.which("uv")
        assert uv is not None
        driver = PROJECT / "tests/fixtures/build_tool.py"
        for name in ("uv", "git", "apt-get", "dpkg-deb", "cmake"):
            executable = binaries / name
            executable.write_text(
                "#!/bin/bash\nexec "
                + shlex.quote(uv)
                + " run --no-project --python "
                + shlex.quote(sys.executable)
                + " python "
                + shlex.quote(str(driver))
                + " "
                + name
                + ' "$@"\n'
            )
            executable.chmod(0o755)
        calls = root / "commands.jsonl"
        environment = dict(self.environment)
        environment.update(
            XDG_DATA_HOME=str(root / "data"),
            XDG_CACHE_HOME=str(root / "cache"),
            MASKRF_PYTHON=sys.executable,
            MASKRF_TEST_ROOT=str(root),
            MASKRF_TEST_CALLS=str(calls),
            PATH=str(binaries) + os.pathsep + self.environment["PATH"],
        )
        subprocess.run(
            ["bash", str(PROJECT / "scripts/bootstrap.sh")],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        prefix = root / "data/maskrf/openems-0.0.36"
        self.assertTrue((prefix / "lib/libCSXCAD.so").is_file())
        self.assertTrue((prefix / "lib/libopenEMS.so").is_file())
        self.assertEqual(len(list((prefix / "wheels").glob("*.whl"))), 2)
        self.assertTrue((root / "cache/maskrf/openems-0.0.36/build/openEMS").is_dir())
        commands = [json.loads(line) for line in calls.read_text().splitlines()]
        target = commands[-1]
        self.assertEqual(target["tool"], "uv")
        self.assertEqual(
            target["arguments"][:4], ["pip", "install", "--python", sys.executable]
        )
        self.assertIn("--reinstall", target["arguments"])
        self.assertTrue(
            all(
                str(prefix) in value
                for value in target["arguments"]
                if value.endswith(".whl")
            )
        )
        self.assertFalse((root / ".native").exists())


if __name__ == "__main__":
    unittest.main()
