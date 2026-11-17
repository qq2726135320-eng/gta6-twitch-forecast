"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Entry for make.fun bounty gta6-twitch-ccu-forecast-01.

Method
------
For every hour h = 2..24 of the release day we fit, on the launch curves the
case file ships as `comparables`, a one-feature regression in log space:

    log(viewers at hour h) = a_h + b_h * log(viewers at hour 1)

Hour 1 (00:00-01:00 UTC) is the dead hour of the launch day, so its level
alone says little about the evening peak; the regression learns, per hour,
how the day's curve scales with that first print. We fit the regression twice
and average the two predictions in log space:

  * fit B -- the "comparable" launches only: comparables whose unlock note
    carries Tier: comparable (early-access-contaminated launches, weak
    analogues and the target's own pre-release history are left out);
  * fit D -- the rolling-midnight launches only: comparables whose unlock
    note says the game unlocked at midnight local time, rolling (the same
    unlock pattern as Grand Theft Auto VI and as the four practice launches).

The spread around the median comes from fit B's residual standard
deviation, floored at 0.08 in log units. Quantiles are log-normal around the
blended median; the upper tail is widened (x0.75) relative to the lower tail
(x0.5), because for this launch the plausible surprise is upside: an
evening peak far above every comparable, not a flop below them.

The program is deterministic, standard library only, and offline: it reads
only the case file it is given (its hour-1 print and its comparables) and
writes one forecast file per case.

Input:  /input/<id>.in (or $MAKEFUN_INPUT_DIR), schema makefun/twitch-ccu-case/v1
Output: /output/<id>.out (or $MAKEFUN_OUTPUT_DIR):
        {"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}, ...]} for h = 2..24
"""

import json
import math
import os
import re
import sys
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at LEVELS.
Z_SCORES = [-1.6448536269514722, -0.6744897501960817, 0.0,
            0.6744897501960817, 1.6448536269514722]
# Spread multipliers: lower tail x0.5, upper tail x0.75 (see module docstring).
SPREAD_LOW = 0.5
SPREAD_HIGH = 0.75
SIGMA_FLOOR = 0.08
MIN_POINTS = 8
MIN_HOURS_ON_DAY = 20

_TIER_RE = re.compile(r"Tier:\s*([a-z][a-z-]*)")


def tier_of(comparable):
    """The tier named in a comparable's unlock note; 'comparable' when unnamed."""
    match = _TIER_RE.search(comparable.get("unlock") or "")
    return match.group(1) if match else "comparable"


def is_rolling(comparable):
    """True when the comparable unlocked at midnight local time, rolling."""
    text = (comparable.get("unlock") or "").lower()
    return "midnight local" in text or "rolling" in text


def release_day_hours(comparable):
    """{hour: viewers} for the comparable's release day (UTC), or None.

    Only comparables with a usable release day count: hour 1 present and at
    least MIN_HOURS_ON_DAY hourly points on that day.
    """
    day = comparable["day_start"][:10]
    hours = {}
    for point in comparable.get("hourly") or []:
        if not point["from"].startswith(day):
            continue
        viewers = point.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        hours[int(point["from"][11:13]) + 1] = float(viewers)
    if 1 not in hours or len(hours) < MIN_HOURS_ON_DAY:
        return None
    return hours


def fit_line(xs, ys):
    """Ordinary least squares for y = a + b*x; returns (a, b, residual_sd)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return mean_y, 0.0, _resid_sd(ys, [mean_y] * n)
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    a = mean_y - b * mean_x
    return a, b, _resid_sd(ys, [a + b * x for x in xs])


def _resid_sd(ys, fitted):
    if len(ys) < 2:
        return 0.5
    mean = sum(y - f for y, f in zip(ys, fitted)) / len(ys)
    var = sum((y - f - mean) ** 2 for y, f in zip(ys, fitted)) / len(ys)
    return math.sqrt(var)


def fit_set(curves, hour, log_p1):
    """Fit log(viewers_h) ~ log(viewers_1) on the kept curves.

    Returns (mu, sigma): the predicted log viewers at `hour` for a launch
    whose hour-1 log viewers are `log_p1`, and the residual spread. Falls
    back to persistence when too few curves cover the hour.
    """
    xs, ys = [], []
    for hours in curves:
        if hour not in hours:
            continue
        xs.append(math.log(hours[1]))
        ys.append(math.log(hours[hour]))
    if len(ys) < MIN_POINTS:
        return log_p1, 0.5
    a, b, sd = fit_line(xs, ys)
    return a + b * log_p1, sd


def forecast_case(case):
    if case["levels"] != LEVELS:
        raise ValueError(f"levels {case['levels']} are not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError("case has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    log_p1 = math.log(p1)

    curves_b, curves_d = [], []
    for comp in case.get("comparables") or []:
        tier = tier_of(comp)
        if tier == "target-history":
            continue
        hours = release_day_hours(comp)
        if hours is None:
            continue
        if tier == "comparable":
            curves_b.append(hours)
        if is_rolling(comp):
            curves_d.append(hours)

    rows = []
    for row in case["forecast"]:
        h = row["hour"]
        mu_b, sd_b = fit_set(curves_b, h, log_p1)
        mu_d, _sd_d = fit_set(curves_d, h, log_p1)
        mu = 0.5 * (mu_b + mu_d)
        sigma = max(SIGMA_FLOOR, sd_b)
        quantiles = []
        for z in Z_SCORES:
            spread = SPREAD_LOW if z <= 0 else SPREAD_HIGH
            q = math.exp(mu + z * sigma * spread)
            quantiles.append(min(1e9, max(1.0, q)))
        rows.append({"hour": h, "q": quantiles})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
