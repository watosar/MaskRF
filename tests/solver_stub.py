# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Stand in for the solver process while retaining real API input/output handling."""

import json
import shutil
import subprocess
from pathlib import Path

import yaml

FIXTURE = Path(__file__).resolve().parent / "fixtures/completed-run"


def complete_solver(command, *, stdout, stderr, check, env):
    config_path = Path(command[command.index("--config") + 1])
    out = Path(command[command.index("--out") + 1])
    config = yaml.safe_load(config_path.read_text())
    out.mkdir()
    (out / "mask.csv").write_bytes(Path(config["geometry"]["file"]).read_bytes())
    config["geometry"]["file"] = str(out / "mask.csv")
    (out / "effective.json").write_text(json.dumps(config))
    for filename in ("status.json", "metrics.json", "sparameters.csv"):
        shutil.copyfile(FIXTURE / filename, out / filename)
    stdout.write("Completed test solver output\n")
    return subprocess.CompletedProcess(command, 0)
