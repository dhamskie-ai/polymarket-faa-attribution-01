# Polymarket FAA attribution forecast — make.fun `polymarket-faa-attribution-01`

Entry program: `main.py` (Python 3.13, stdlib only). It reads each case file
`/input/<id>.in` and writes `/output/<id>.out`: for every market and each of
the 240 minutes after the checkpoint, five quantiles (5%, 25%, 50%, 75%, 95%)
of that minute's Yes price.

## Method

Persistence median with a per-market, winsorised random-walk spread:

```
q_tau(h) = clamp(x + z_tau * sigma * sqrt(h), 0, 1)
```

- `x` — the market's Yes price at the checkpoint (the median never drifts:
  mean reversion and momentum both tested worse on the practice).
- `sigma` — std of the market's 1-minute moves over the last 120 minutes,
  each move winsorised at ±0.01. A plain std over a long window is ruined by
  single jumps (practice loss 0.72–0.76 vs 0.39 for the house baseline);
  winsorising fixes it (0.31).
- The 5% and 95% quantiles are widened 1.25× — prediction-market moves have
  fatter tails than a normal; the middle quantiles stay normal.
- `sigma` is floored at 0.0003 and capped at 0.01; markets with fewer than
  two usable moves fall back to the house baseline spread 0.0025.

## Local practice score

Scored on the kit's practice cases p00–p04, using the next case's prices as
ground truth (the kit ships no answers; consecutive cases share a prefix, so
the next case's tail is exactly the scored window):

| variant | pinball loss | median error | 90% coverage |
| --- | --- | --- | --- |
| house baseline (σ=0.0025) | 0.3925 | 0.88 | 0.94 |
| **this entry** | **0.3116** | 0.88 | 0.90 |

The entry beats the baseline on every one of the five cases
(0.462/0.310/0.346/0.270/0.207 vs 0.536/0.380/0.408/0.369/0.299).
The tuning surface is flat — clip 0.005–0.02 and window 90–180 all score
0.312–0.324 — so this is not a knife-edge fit. The practice is cut from a
different event (NVIDIA CEO), so the score is evidence about the method,
not a promise about the FAA final.

Deterministic, no network, no clock, no randomness. Broken input never
crashes a run: a market with no usable prices is forecast at 0.5.
Runtime ~0.1 s per case (cap 8 s).

## Files

- `main.py` — the entry program
- `LICENSE` — MIT
- `.makefun/owner.json` — payout wallet (Solana)
