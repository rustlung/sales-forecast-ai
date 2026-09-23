from __future__ import annotations

import math

import numpy as np


def calculate_metrics(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted values must be non-empty and same length")
    errors = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    nonzero_actual = [(truth, estimate) for truth, estimate in zip(actual, predicted, strict=True) if truth != 0]
    mape = None
    if len(nonzero_actual) / len(actual) >= 0.5:
        mape = float(np.mean([abs((truth - estimate) / truth) for truth, estimate in nonzero_actual]) * 100)
    return {"mae": _finite(mae), "rmse": _finite(rmse), "mape": _finite(mape), "zero_actual_count": len(actual) - len(nonzero_actual)}


def _finite(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None
