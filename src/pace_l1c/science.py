"""PACE L1C Technical Report equations 6 and 10; no display clipping."""
import numpy as np


def reflectance(radiance, f0, solar_zenith, distance):
    if not np.isfinite(distance) or distance <= 0:
        raise ValueError("Missing or invalid sun_earth_distance")
    mu = np.cos(np.deg2rad(solar_zenith))
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.pi * distance**2 * radiance / (f0 * mu)
    return np.where((mu > 0) & (f0 > 0), result, np.nan)


def rotate(q, u, angle):
    a = np.deg2rad(2 * angle)
    return q * np.cos(a) + u * np.sin(a), -q * np.sin(a) + u * np.cos(a)


def dolp(i, q, u):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(i > 0, np.hypot(q, u) / i, np.nan)


def branches(angles, nominal):
    """Turning-point heuristic, explicitly exploratory; preserve channel identity."""
    nominal=np.asarray(nominal)
    # Real L1C red channels follow descending nominal angle/source-view order.
    # Retain that original order; reconstruct physical ordering only for shuffled fixtures.
    delta=np.diff(nominal)
    order=np.arange(len(nominal)) if np.all(delta>=0) or np.all(delta<=0) else np.argsort(-nominal,kind="stable")
    finite = order[np.isfinite(np.asarray(angles)[order])]
    result = np.full(len(angles), -1, dtype=int)
    if not len(finite):
        return result
    vals = np.asarray(angles)[finite]
    pivot = int(np.argmax(vals))
    if pivot in (0, len(vals)-1):
        pivot = int(np.argmin(vals))
    result[finite[:pivot+1]] = 0
    result[finite[pivot+1:]] = 1
    return result
