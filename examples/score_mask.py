"""Score a mask against a target S21 using only the public maskrf API."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from maskrf import SimulationError, evaluate_mask

METRIC_FORMULAS = {
    "mae": "mean(abs(abs(S21_response) - S21_target_magnitude))",
    "mse": "mean((abs(S21_response) - S21_target_magnitude)**2)",
    "rmse": "sqrt(mean((abs(S21_response) - S21_target_magnitude)**2))",
    "max": "max(abs(abs(S21_response) - S21_target_magnitude))",
}


def _metric(metric):
    if metric not in METRIC_FORMULAS:
        raise ValueError(f"Unknown metric {metric!r}; choose mae, mse, rmse or max")
    return metric


def _frequencies(values, label):
    if np.iscomplexobj(values):
        raise ValueError(f"{label} must be real frequencies in Hz")
    values = np.asarray(values, dtype=float)
    if (
        values.ndim != 1
        or values.size == 0
        or not np.isfinite(values).all()
        or np.any(values <= 0)
        or np.any(np.diff(values) <= 0)
    ):
        raise ValueError(f"{label} must be finite, positive and strictly increasing")
    return values


def _target(frequency_hz, magnitude):
    frequency_hz = _frequencies(frequency_hz, "Target frequencies")
    if np.iscomplexobj(magnitude):
        raise ValueError("Target magnitude must be real")
    magnitude = np.asarray(magnitude, dtype=float)
    if (
        magnitude.shape != frequency_hz.shape
        or not np.isfinite(magnitude).all()
        or np.any(magnitude < 0)
    ):
        raise ValueError(
            "Target magnitude must be finite, nonnegative and match the frequencies"
        )
    return frequency_hz, magnitude


def parse_target_csv(text):
    """Read frequency_GHz plus s21_magnitude or s21_dB; return Hz and linear magnitude."""
    reader = csv.reader(io.StringIO(text))
    header = [column.strip() for column in next(reader, [])]
    if header not in (["frequency_GHz", "s21_magnitude"], ["frequency_GHz", "s21_dB"]):
        raise ValueError(
            "Target CSV header must be frequency_GHz,s21_magnitude or frequency_GHz,s21_dB"
        )
    frequency_hz, values = [], []
    for line, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 2:
            raise ValueError(f"Target CSV line {line} must have two columns")
        try:
            frequency_hz.append(float(row[0]) * 1e9)
            values.append(float(row[1]))
        except ValueError as error:
            raise ValueError(f"Target CSV line {line} must contain numbers") from error
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(
            "Target values must be finite; use magnitude 0 for zero transmission"
        )
    if header[1] == "s21_dB":
        with np.errstate(over="ignore", under="ignore"):
            values = np.power(10.0, values / 20.0)
    return _target(frequency_hz, values)


def s21_error(
    frequency_hz, s21, target_frequency_hz, target_magnitude, *, metric="rmse"
) -> float:
    """Score linear |S21| at target points with MAE, MSE, RMSE or maximum error.

    MAE/MSE/RMSE weight target points equally. Interpolate magnitude without
    extrapolation. Phase is excluded. RMSE is the default. MSE and RMSE give the
    same candidate ranking.
    """
    _metric(metric)
    frequency_hz = _frequencies(frequency_hz, "Response frequencies")
    s21 = np.asarray(s21, dtype=complex)
    if s21.shape != frequency_hz.shape or not np.isfinite(s21).all():
        raise ValueError(
            "Response S21 must be finite and match the response frequencies"
        )
    target_frequency_hz, target_magnitude = _target(
        target_frequency_hz, target_magnitude
    )
    if (
        target_frequency_hz[0] < frequency_hz[0]
        or target_frequency_hz[-1] > frequency_hz[-1]
    ):
        raise ValueError(
            "Target frequencies must be within the simulated frequency range; extrapolation is not allowed"
        )
    sampled = np.interp(target_frequency_hz, frequency_hz, np.abs(s21))
    with np.errstate(over="ignore", invalid="ignore"):
        error = sampled - target_magnitude
        if metric == "mae":
            value = float(np.mean(np.abs(error)))
        elif metric == "mse":
            value = float(np.mean(error**2))
        elif metric == "rmse":
            value = float(np.sqrt(np.mean(error**2)))
        else:
            value = float(np.max(np.abs(error)))
    if not np.isfinite(value):
        raise ValueError("S21 error is not finite")
    return value


def s21_mae(frequency_hz, s21, target_frequency_hz, target_magnitude) -> float:
    """Compatibility helper for the original linear-magnitude MAE score."""
    return s21_error(
        frequency_hz, s21, target_frequency_hz, target_magnitude, metric="mae"
    )


def score_mask(
    mask, target_path, out_dir, *, metric="rmse", config_path=None, reuse_run=None
) -> float:
    """Evaluate a mask, save response and score evidence, and return one float.

    out_dir must be unused, as required by evaluate_mask. Invalid target CSVs are
    rejected before invoking the simulator. reuse_run is checked by the library.
    RMSE is the default; choose metric explicitly to use another aggregation.
    """
    _metric(metric)
    target_path = Path(target_path).resolve()
    target_bytes = target_path.read_bytes()
    target_frequency_hz, target_magnitude = parse_target_csv(
        target_bytes.decode("utf-8-sig")
    )
    response = evaluate_mask(
        mask, out_dir, config_path=config_path, reuse_run=reuse_run
    )
    value = s21_error(
        response.frequency_Hz,
        response.s[:, 1, 0],
        target_frequency_hz,
        target_magnitude,
        metric=metric,
    )
    out_dir = Path(out_dir)
    (out_dir / "target.csv").write_bytes(target_bytes)
    record = {
        "metric": f"s21_magnitude_{metric}",
        "value": value,
        "formula": METRIC_FORMULAS[metric],
        "sample_count": int(target_frequency_hz.size),
        "sampling": "linear interpolation of magnitude at target frequencies; no extrapolation",
        "frequency_Hz": target_frequency_hz.tolist(),
        "target_magnitude": target_magnitude.tolist(),
        "response_magnitude": np.interp(
            target_frequency_hz, response.frequency_Hz, np.abs(response.s[:, 1, 0])
        ).tolist(),
        "target_source": str(target_path),
        "target_sha256": hashlib.sha256(target_bytes).hexdigest(),
        "response_run_dir": str(response.run_dir),
    }
    (out_dir / "score.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n"
    )
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print one float for target S21 magnitude error (smaller is better)."
    )
    parser.add_argument(
        "--mask",
        required=True,
        type=Path,
        help="16x16 mask: CSV, JSON or black/white PNG",
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="CSV: frequency_GHz,s21_magnitude or frequency_GHz,s21_dB",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Unused directory for response and score evidence, e.g. tmp/score-01",
    )
    parser.add_argument(
        "--metric",
        choices=METRIC_FORMULAS,
        default="rmse",
        help="Error aggregation; default rmse",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional simulation YAML; defaults to the adopted lossless RO setup",
    )
    parser.add_argument(
        "--reuse-run",
        type=Path,
        help="Completed run with the same mask and simulation settings",
    )
    args = parser.parse_args(argv)
    try:
        value = score_mask(
            args.mask,
            args.target,
            args.out,
            metric=args.metric,
            config_path=args.config,
            reuse_run=args.reuse_run,
        )
    except (OSError, ValueError, SimulationError) as error:
        parser.exit(1, f"error: {error}\n")
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
