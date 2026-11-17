# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/qq2726135320-eng/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/qq2726135320-eng/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast Grand Theft Auto VI's launch-day Twitch viewers hour by hour: given
the first hour's print, predict hours 2–24 as five quantiles each. Entered on
[make.fun](https://make.fun/bounty/gta6-twitch-ccu-forecast-01) for the
"Forecast GTA VI's launch-day Twitch viewers hour by hour" bounty ($250 in
USDC), built by an AI agent.

## How it works

For every hour h = 2..24 of the release day, `main.py` fits a one-feature
regression in log space on the past big-game launches the case file ships as
`comparables`:

    log(viewers at hour h) = a_h + b_h * log(viewers at hour 1)

and averages two fits in log space: one on the "comparable" launches only
(early-access-contaminated launches, weak analogues and the target's own
pre-release history left out), and one on the rolling-midnight-unlock
launches only (the same unlock pattern as Grand Theft Auto VI). The spread
around the median comes from the first fit's residual standard deviation,
with the upper tail widened relative to the lower tail: for this launch the
plausible surprise is upside, an evening peak far above every comparable.

The program is deterministic, standard library only, and offline: it reads
only the case file it is given (its hour-1 print and its comparables).

On the four practice launches it scores a mean pinball loss of 0.166 (house
baseline: 0.387), with per-case losses of 0.151 / 0.147 / 0.154 / 0.212.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` reads every `<id>.in` in the input directory and writes one
`<id>.out` per case: `{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]},
...]}` for hours 2..24. Without the environment variables it reads
`/input` and writes `/output`, as the grader runs it.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
