"""Mask-to-circuit interface for the existing two-port simulation model."""

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .geometry import load_mask, mask_audit
from .runtime import prepare_solver

DEFAULT_CONFIG = Path(__file__).resolve().parent / "configs/paper_corrected.yaml"


class SimulationError(RuntimeError):
    """Simulation failed, is incomplete, or did not reach its decay criterion."""


def _completed_excitations(statuses):
    """Require both port excitations to exit normally and satisfy decay."""
    if not isinstance(statuses, list):
        return False
    try:
        return sorted(s["excitation"] for s in statuses) == [1, 2] and all(
            s["exit_code"] == 0 and s["normal_finish"] and s["decay_confirmed"]
            for s in statuses
        )
    except (KeyError, TypeError):
        return False


def read_mask(mask):
    """Read a 16x16 binary array, CSV, JSON array, or strictly black/white PNG."""
    if isinstance(mask, (str, Path)):
        path = Path(mask)
        if path.suffix.lower() == ".json":
            mask = json.loads(path.read_text())
        elif path.suffix.lower() in (".csv", ".png"):
            mask = load_mask(path)
        else:
            raise ValueError("Mask file must be CSV, JSON, or PNG")
    try:
        array = np.asarray(mask)
    except (TypeError, ValueError) as error:
        raise ValueError("Mask must be a rectangular 16x16 binary array") from error
    if array.shape != (16, 16):
        raise ValueError(
            f"Mask must have shape (16, 16), got {array.shape}; 18x18 terminal encoding is not supported"
        )
    if array.dtype.kind not in "biuf" or not np.isin(array, [0, 1]).all():
        raise ValueError("Mask must contain only numeric 0/1 or booleans")
    return array.astype(np.uint8, copy=True)


def _settings(config):
    """Extract simulation and measurement settings without the mask file path."""
    result = {
        key: copy.deepcopy(config[key])
        for key in (
            "geometry",
            "substrate",
            "metal",
            "frequency_GHz",
            "ports",
            "mesh",
            "domain",
            "boundary",
            "solver",
            "validation",
        )
    }
    result["geometry"].pop("file", None)
    return result


@dataclass
class CircuitResponse:
    frequency_Hz: np.ndarray
    s: np.ndarray  # [frequency, output port, input port], zero-based indices
    metrics: dict
    settings: dict
    mask: np.ndarray
    run_dir: Path
    execution: str = "loaded"

    def to_dict(self):
        """JSON-safe schema: explicit units and real/imaginary complex encoding."""
        parameters = {}
        for i in range(2):
            for j in range(2):
                values = self.s[:, i, j]
                parameters[f"s{i + 1}{j + 1}"] = {
                    "real": values.real.tolist(),
                    "imag": values.imag.tolist(),
                    "magnitude_dB": (
                        20 * np.log10(np.maximum(abs(values), 1e-15))
                    ).tolist(),
                    "phase_deg": np.rad2deg(np.angle(values)).tolist(),
                }
        return {
            "schema_version": 1,
            "status": "completed",
            "execution": self.execution,
            "frequency_Hz": self.frequency_Hz.tolist(),
            "s_parameters": parameters,
            "reference_impedance_ohm": self.settings["ports"]["reference_ohm"],
            "metrics": self.metrics,
            "settings": self.settings,
            "mask": self.mask.tolist(),
            "mask_sha256": hashlib.sha256(self.mask.tobytes()).hexdigest(),
            "conventions": {
                "mask": "1=metal, row 0=+y, column 0=-x; centred; fixed 16x16 interior",
                "s_indices": "s[frequency, output_port, input_port]; s[:,1,0] is S21",
                "phase_deg": "principal phase [-180,180]; magnitude floor -300 dB",
            },
            "validation": {
                "both_excitations_completed": True,
                "decay_confirmed": True,
                "mesh_convergence_checked_by_this_call": False,
            },
            "artifacts": {
                "run_dir": str(self.run_dir),
                "csv": str(self.run_dir / "sparameters.csv"),
                "touchstone": str(self.run_dir / "network.s2p"),
            },
        }


def load_response(run_dir):
    """Read a completed native run (or an evaluate output directory), without rerunning."""
    run_dir = Path(run_dir).resolve()
    try:
        if (run_dir / "run/effective.json").exists():
            run_dir = run_dir / "run"
        elif (run_dir / "response.json").exists() and not (
            run_dir / "effective.json"
        ).exists():
            target = Path(
                json.loads((run_dir / "response.json").read_text())["artifacts"][
                    "run_dir"
                ]
            ).resolve()
            if target == run_dir:
                raise SimulationError(
                    "Response refers to itself instead of a native run"
                )
            run_dir = target
        statuses = json.loads((run_dir / "status.json").read_text())
        if not _completed_excitations(statuses):
            raise SimulationError(f"Both excitations must finish and decay: {run_dir}")
        config = json.loads((run_dir / "effective.json").read_text())
        mask = read_mask(run_dir / "mask.csv")
        data = np.atleast_1d(
            np.genfromtxt(run_dir / "sparameters.csv", names=True, delimiter=",")
        )
        frequency = data["frequency_Hz"]
        s = np.array(
            [
                [data[f"s{i}{j}_real"] + 1j * data[f"s{i}{j}_imag"] for j in (1, 2)]
                for i in (1, 2)
            ]
        ).transpose(2, 0, 1)
        expected = np.linspace(
            config["frequency_GHz"][0] * 1e9,
            config["frequency_GHz"][1] * 1e9,
            config["frequency_GHz"][2],
        )
        if not np.array_equal(frequency, expected) or not np.isfinite(s).all():
            raise SimulationError(
                f"Invalid frequency grid or nonfinite S parameters: {run_dir}"
            )
        metrics = json.loads((run_dir / "metrics.json").read_text())
        coherent = float(np.linalg.svd(s, compute_uv=False)[:, 0].max() ** 2)
        metrics.update(
            max_coherent_power_ratio=coherent,
            passivity_within_2pct=coherent <= 1.02,
            strict_passivity=coherent <= 1,
        )
        return CircuitResponse(frequency, s, metrics, _settings(config), mask, run_dir)
    except (OSError, KeyError, ValueError, TypeError) as error:
        raise SimulationError(
            f"Cannot read completed circuit response from {run_dir}: {error}"
        ) from error


def evaluate_mask(mask, out_dir, *, config_path=None):
    """Evaluate a 16x16 metal mask; preserve inputs, logs and response.json in out_dir.

    Defaults to the accepted Fig.3(a) substrate, feeds, shorts and finest mesh.
    This synchronous call always runs a new simulation and may take tens of
    minutes. Existing output paths are refused.
    """
    array = read_mask(mask)
    path = Path(config_path or DEFAULT_CONFIG).resolve()
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        raise TypeError("Configuration must be a YAML mapping")
    if config["geometry"]["kind"] != "mask":
        raise ValueError("evaluate_mask requires a mask geometry configuration")
    if config["solver"]["excitations"] != [1, 2]:
        raise ValueError(
            "evaluate_mask requires excitations [1, 2] for a full S matrix"
        )
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        raise FileExistsError(out_dir)
    try:
        environment = prepare_solver()
    except RuntimeError as error:
        raise SimulationError(str(error)) from error
    out_dir.mkdir(parents=True, exist_ok=False)
    np.savetxt(out_dir / "mask.csv", array, delimiter=",", fmt="%d")
    config["geometry"]["file"] = str(out_dir / "mask.csv")
    (out_dir / "request.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    request = {
        "config_source": str(path),
        "mask_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
        "geometry_audit": mask_audit(config),
    }
    (out_dir / "request.json").write_text(
        json.dumps(request, indent=2, allow_nan=False)
    )
    try:
        command = [
            "uv",
            "run",
            "--no-project",
            "--python",
            sys.executable,
            "-m",
            "maskrf",
            "run",
            "--config",
            str(out_dir / "request.yaml"),
            "--out",
            str(out_dir / "run"),
        ]
        with (out_dir / "execution.log").open("w") as log:
            result = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                env=environment,
            )
        if result.returncode:
            raise SimulationError(
                f"Simulator exited with {result.returncode}; see {out_dir}/execution.log"
            )
        response = load_response(out_dir / "run")
        response.execution = "simulated"
        (out_dir / "response.json").write_text(
            json.dumps(response.to_dict(), indent=2, allow_nan=False)
        )
        return response
    except Exception as error:
        (out_dir / "error.json").write_text(
            json.dumps({"status": "failed", "error": str(error)}, indent=2)
        )
        raise
