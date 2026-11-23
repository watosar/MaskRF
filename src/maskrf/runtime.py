# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Locate and install the openEMS libraries needed for simulation."""

import importlib
import os
import platform
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass
from pathlib import Path

OPENEMS_VERSION = "0.0.36"
INSTALL_SUBDIR = f"maskrf/openems-{OPENEMS_VERSION}"


@dataclass(frozen=True)
class SolverPaths:
    data: Path
    cache: Path
    state: Path


def xdg_home(variable: str, default: str) -> Path:
    value = os.environ.get(variable, "")
    return Path(value) if Path(value).is_absolute() else Path.home() / default


def solver_paths() -> SolverPaths:
    return SolverPaths(
        xdg_home("XDG_DATA_HOME", ".local/share") / INSTALL_SUBDIR,
        xdg_home("XDG_CACHE_HOME", ".cache") / INSTALL_SUBDIR,
        xdg_home("XDG_STATE_HOME", ".local/state") / "maskrf",
    )


def configure_environment() -> None:
    os.environ.setdefault(
        "MPLCONFIGDIR", str(xdg_home("XDG_CACHE_HOME", ".cache") / "maskrf/matplotlib")
    )


def solver_environment() -> dict[str, str]:
    environment = dict(os.environ)
    root = solver_paths().data
    paths = [
        str(root / "lib"),
        str(root / "usr/lib/x86_64-linux-gnu"),
        str(root / "usr/lib/x86_64-linux-gnu/hdf5/serial"),
        *environment.get("LD_LIBRARY_PATH", "").split(os.pathsep),
    ]
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        dict.fromkeys(p for p in paths if p)
    )
    environment.setdefault(
        "MPLCONFIGDIR", str(xdg_home("XDG_CACHE_HOME", ".cache") / "maskrf/matplotlib")
    )
    return environment


def _probe(environment: dict[str, str]) -> bool:
    root = solver_paths().data
    if not all(
        (root / "lib" / name).exists() for name in ("libopenEMS.so", "libCSXCAD.so")
    ):
        return False
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "--python",
            sys.executable,
            "python",
            "-c",
            "from CSXCAD import ContinuousStructure; from openEMS import openEMS",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _confirm_install() -> bool:
    print(
        "openEMS・CSXCADを実行するためのライブラリが未導入か、読み込めません。\n"
        f"導入先: {solver_paths().data}\n"
        "必要に応じてダウンロードとビルドを行います（空き領域の目安は約5 GB）。",
        file=sys.stderr,
    )
    while True:
        print("インストールしますか？ (Y/n): ", file=sys.stderr, end="", flush=True)
        try:
            answer = input().strip().lower()
        except EOFError:
            return False
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Yまたはnを入力してください。", file=sys.stderr)


def _installer_script() -> Path:
    source = Path(__file__).resolve().parents[2] / "scripts/bootstrap.sh"
    installed = Path(sysconfig.get_path("data")) / "share/maskrf/scripts/bootstrap.sh"
    for candidate in (source, installed):
        if candidate.is_file():
            return candidate
    raise RuntimeError("openEMS・CSXCADの構築スクリプトがパッケージに含まれていません")


def _cached_wheels() -> list[Path]:
    root = solver_paths().data
    if not all(
        (root / "lib" / name).exists() for name in ("libopenEMS.so", "libCSXCAD.so")
    ):
        return []
    wheels = list((root / "wheels").glob("*.whl"))
    result = []
    for package in ("csxcad-", "openems-"):
        candidates = sorted(p for p in wheels if p.name.lower().startswith(package))
        if not candidates:
            return []
        result.append(candidates[-1])
    return result


def _install_solver(environment: dict[str, str]) -> Path | None:
    if sys.platform != "linux":
        raise RuntimeError("自動導入の対象はUbuntu 24.04／x86_64です")
    import fcntl

    paths = solver_paths()
    paths.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (paths.cache / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _probe(environment):
            return None
        paths.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        log_path = paths.state / f"openems-install-{time.time_ns()}.log"
        print(f"インストール中です。ログ: {log_path}", file=sys.stderr)
        try:
            with log_path.open("w") as log:
                wheels = _cached_wheels()
                if wheels:
                    command = [
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        sys.executable,
                        "--reinstall",
                        *(str(wheel) for wheel in wheels),
                    ]
                else:
                    release = platform.freedesktop_os_release()
                    if (
                        release.get("ID") != "ubuntu"
                        or release.get("VERSION_ID") != "24.04"
                        or platform.machine() != "x86_64"
                    ):
                        raise RuntimeError("自動ビルドの対象はUbuntu 24.04／x86_64です")
                    command = ["bash", str(_installer_script())]
                install_environment = dict(environment, MASKRF_PYTHON=sys.executable)
                subprocess.run(
                    command,
                    env=install_environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
        except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
            raise RuntimeError(
                f"openEMS・CSXCADの導入に失敗しました: {error}。ログ: {log_path}"
            ) from error
        return log_path


def prepare_solver() -> dict[str, str]:
    """Return the solver environment, installing only after an affirmative answer."""
    environment = solver_environment()
    if _probe(environment):
        return environment
    if not _confirm_install():
        raise RuntimeError("openEMS・CSXCADが必要です。インストールを中止しました")
    log_path = _install_solver(environment)
    importlib.invalidate_caches()
    if not _probe(environment):
        raise RuntimeError(f"導入後もopenEMS・CSXCADを読み込めません。ログ: {log_path}")
    return environment
