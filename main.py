"""Forecast Polymarket FAA outage-attribution Yes prices (make.fun
polymarket-faa-attribution-01).

For every case file /input/<id>.in (one checkpoint, up to 72 h of
1-minute Yes prices per market) this writes /output/<id>.out: for each
market, the 240 minutes after the checkpoint as five quantiles
(5%, 25%, 50%, 75%, 95%) of that minute's Yes price.

Method: the median stays at the last observed price; the spread is a
per-market random walk whose volatility is estimated from recent
1-minute moves.

    q_tau(h) = clamp(x + z_tau * sigma * sqrt(h), 0, 1)

with x the market's last price, z_tau the standard-normal quantile,
and sigma the standard deviation of the market's 1-minute moves over
its last 120 minutes, each move winsorised at +-0.01. The two outer
quantiles are widened 1.25x: these markets trade in ticks and jump,
so their tails are fatter than a normal's; the middle quantiles stay
normal. There is no drift: on the kit's practice cases both mean
reversion and momentum scored worse than a flat median.

Why winsorise: a single jump must not set the spread for hours. A
plain per-market std over a long window scores far worse than the
house baseline on the practice (about 0.72-0.76 vs 0.39); winsorising
the moves brings it to about 0.31. The tuning surface is flat
(clip 0.005-0.02, window 90-180 all score 0.31-0.32), so the choice
is not a knife-edge fit to one case.

Local practice score of this program: see README.md. The practice is
cut from a different event (NVIDIA "Next CEO?"), so the score is
evidence about the method, not a promise about the FAA final.

Deterministic, Python 3.13 standard library only, no network, no
clock, no randomness. Broken input never crashes a run: a market
with no usable prices is forecast at 0.5 for every quantile, a
market with too little history falls back to the house baseline
spread 0.0025, and an unreadable case file is skipped.
"""

import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard-normal quantiles at the five levels, to 6 decimals.
Z_SCORES = [-1.644854, -0.674490, 0.0, 0.674490, 1.644854]
OUTER_WIDEN = 1.25  # 5% and 95% quantiles only (fatter tails)
LOOKBACK = 120  # minutes of 1-minute moves used for sigma
MOVE_CLIP = 0.01  # winsorise each 1-minute move at +-this
SIGMA_MIN = 0.0003
SIGMA_MAX = 0.01
HOUSE_SIGMA = 0.0025  # fallback when a market has too little history


def clamp_rounded(value):
    """Clamp to [0, 1], round to 6 decimals, never -0.0."""
    return round(min(1.0, max(0.0, value)) * 1_000_000) / 1_000_000 + 0.0


def usable_prices(raw):
    """Finite floats from a case's price list, in order; junk dropped."""
    clean = []
    for item in raw or []:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            clean.append(value)
    return clean


def estimate_sigma(prices):
    """Std of the last LOOKBACK 1-minute moves, winsorised at +-MOVE_CLIP."""
    moves = []
    start = max(1, len(prices) - LOOKBACK)
    for i in range(start, len(prices)):
        step = prices[i] - prices[i - 1]
        if step > MOVE_CLIP:
            step = MOVE_CLIP
        elif step < -MOVE_CLIP:
            step = -MOVE_CLIP
        moves.append(step)
    if len(moves) < 2:
        return HOUSE_SIGMA
    mean = sum(moves) / len(moves)
    variance = sum((m - mean) ** 2 for m in moves) / len(moves)
    return min(SIGMA_MAX, max(SIGMA_MIN, math.sqrt(variance)))


def forecast_one_market(prices, horizon):
    """`horizon` rows of five quantiles for one market."""
    if horizon <= 0:
        return []
    clean = usable_prices(prices)
    if not clean:
        return [[0.5, 0.5, 0.5, 0.5, 0.5] for _ in range(horizon)]
    last = clean[-1]
    sigma = estimate_sigma(clean)
    rows = []
    for step_ahead in range(1, horizon + 1):
        spread = sigma * math.sqrt(step_ahead)
        row = []
        for index, z in enumerate(Z_SCORES):
            widened = spread * OUTER_WIDEN if index in (0, 4) else spread
            row.append(clamp_rounded(last + z * widened))
        rows.append(row)
    return rows


def forecast_case(case):
    """One parsed case dict -> its {"forecasts": [...]} output dict."""
    try:
        horizon = int(case.get("horizon_minutes") or 240)
    except (TypeError, ValueError):
        horizon = 240
    forecasts = []
    for market in case.get("markets") or []:
        try:
            rows = forecast_one_market(market.get("prices"), horizon)
        except Exception:
            rows = [[0.5, 0.5, 0.5, 0.5, 0.5] for _ in range(horizon)]
        forecasts.append({"id": market.get("id"), "q": rows})
    return {"forecasts": forecasts}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        names = sorted(n for n in os.listdir(INPUT_DIR) if n.endswith(".in"))
    except OSError:
        # No readable input directory: nothing to forecast; leave
        # quietly instead of crashing the run.
        return
    for name in names:
        case_id = name[: -len(".in")]
        try:
            with open(os.path.join(INPUT_DIR, name), "r", encoding="utf-8") as f:
                case = json.load(f)
            result = forecast_case(case)
        except Exception:
            # Unreadable case file: its market ids are unknown, so no
            # output can name them; skip it rather than writing a
            # wrong file.
            continue
        with open(
            os.path.join(OUTPUT_DIR, case_id + ".out"), "w", encoding="utf-8"
        ) as f:
            f.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
