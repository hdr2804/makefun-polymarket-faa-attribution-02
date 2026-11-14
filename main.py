#!/usr/bin/env python3
"""Forecast a Polymarket market's Yes price for the 240 minutes after a
checkpoint: five quantiles (5/25/50/75/95%) per minute.

Scaling a random walk from one-minute volatility badly overstates how
far these prices travel in four hours, because the grid midpoints bounce
between bid and ask.  So this program reads the travel distribution
straight out of each market's own recent history instead: for a grid of
horizons H it samples the empirical quantiles of the H-minute price
changes over the last HISTORY_MINUTES minutes, interpolates them in
sqrt(h) for the minutes in between, and shrinks the result toward a
house-style normal spread centred on the checkpoint price, which keeps
the forecast sane where a market's own samples are thin.  The blend is
taken in change space, quantile by quantile: each final change is
(1 - SHRINK) times the empirical change plus SHRINK times the house
change z_tau * BASE_SIGMA * sqrt(h).
"""

import json
import math
import os

# The quantile levels the contest scores, in the order each row lists.
TAUS = [0.05, 0.25, 0.5, 0.75, 0.95]

# The standard normal's quantile at each scored level.
Z = {
    0.05: -1.6448536269514722,
    0.25: -0.6744897501960817,
    0.5: 0.0,
    0.75: 0.6744897501960817,
    0.95: 1.6448536269514722,
}

# Minutes of a market's own history its change samples are drawn from.
HISTORY_MINUTES = 720
# Spread of the house-style normal the empirical quantiles shrink
# toward, in price units per square-root minute.
BASE_SIGMA = 0.002
# Weight of the house spread in the final blend; the data keeps the rest.
SHRINK = 0.45

# Horizons sampled exactly; horizons in between are interpolated.
GRID_HORIZONS = (1, 2, 3, 5, 8, 12, 18, 27, 40, 60, 90, 135, 180, 240)
# A horizon needs at least this many change samples to be sampled.
MIN_SAMPLES = 24


def _quantile(sorted_vals, tau):
    """The tau-quantile of an ascending list, linearly interpolated."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _change_quantiles(seg, horizon, taus):
    """Empirical quantiles of the horizon-minute changes inside seg."""
    changes = sorted(seg[i + horizon] - seg[i] for i in range(len(seg) - horizon))
    return [_quantile(changes, tau) for tau in taus]


def _price6(value):
    """Clamp to [0, 1] and round to 6 decimals, never negative zero."""
    r = round(min(1.0, max(0.0, value)) * 1e6) / 1e6
    return r if r else 0.0


def forecast_market(prices, horizon, taus):
    """Forecast rows for one market: horizon rows, one quantile per tau."""
    if not prices:
        raise ValueError("a market with no prices cannot be forecast")
    x = prices[-1]
    if len(prices) > HISTORY_MINUTES:
        seg = prices[-HISTORY_MINUTES:]
    else:
        seg = list(prices)

    # Sampled change quantiles for every grid horizon with enough data.
    sampled = {}
    for h in GRID_HORIZONS:
        if len(seg) - h >= MIN_SAMPLES:
            sampled[h] = _change_quantiles(seg, h, taus)
    keys = sorted(sampled)

    rows = []
    for h in range(1, horizon + 1):
        root = math.sqrt(h)
        house = [Z[tau] * BASE_SIGMA * root for tau in taus]
        if not keys:
            blended = house
        else:
            if h <= keys[0]:
                emp = sampled[keys[0]]
            elif h >= keys[-1]:
                emp = sampled[keys[-1]]
            else:
                upper = next(k for k in keys if k > h)
                lower = keys[keys.index(upper) - 1]
                w = (root - math.sqrt(lower)) / (math.sqrt(upper) - math.sqrt(lower))
                emp = [a * (1.0 - w) + b * w for a, b in zip(sampled[lower], sampled[upper])]
            blended = [(1.0 - SHRINK) * e + SHRINK * s for e, s in zip(emp, house)]
        row = []
        prev = 0.0
        for change in blended:
            value = _price6(x + change)
            if value < prev:
                value = prev
            row.append(value)
            prev = value
        rows.append(row)
    return rows


def _run(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for name in sorted(os.listdir(input_dir)):
        if not name.endswith(".in"):
            continue
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        taus = [float(t) for t in case["quantiles"]]
        horizon = int(case["horizon_minutes"])
        forecasts = [
            {"id": market["id"], "q": forecast_market(market["prices"], horizon, taus)}
            for market in case["markets"]
        ]
        out_name = name[: -len(".in")] + ".out"
        with open(os.path.join(output_dir, out_name), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"forecasts": forecasts}) + "\n")


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    _run(input_dir, output_dir)


if __name__ == "__main__":
    main()
