# Data schema

The public repository does not redistribute the source NIFTY spot/options archive.

`src/run_experiment.py` expects a CSV with one row per session and at least these columns:

| Column | Meaning |
|---|---|
| `date` | trading date |
| `dte` | known calendar days to relevant option expiry |
| `dow` | day of week |
| `gap` | log(open / previous close) |
| `morningret` | log return from open to the 09:59 observation state |
| `morningrv` | realized variance during the morning pre-forecast window |
| `morningrange` | morning high-low range normalized by spot |
| `rv1`, `rv5`, `rv22` | lagged realized-variance state variables |
| `lagret1`, `lagret5` | lagged return state variables |
| `premium` | ATM call+put premium normalized by spot, observed at 09:59 |
| `imp_sd` | implied normal standard-deviation scale normalized by spot |
| `forward_offset` | parity-implied forward offset normalized by spot |
| `skew` | legacy cross-wing price/skew proxy |
| `rvtarget` | future 10:00–15:00 realized variance |
| `return_target` | future 10:00–15:00 log return |

The repository's aggregate results were produced from a historical Dhan/NIFTY research archive. Users should reconstruct compatible features from data they are licensed to use.

## Phase II schema

`src/run_phase2.py` expects the close-to-expiry research panel used for the tail-geometry experiment. In addition to `date`, `expiry`, and `usable`, it requires:

- spot/history controls: `cal_days`, `rv5_daily`, `rv20_daily`, `ret1`, `ret5`, `gap_overnight`, `range_day`;
- ATM option level: `atm_iv`, `atm_straddle_pct`, `iv_scale`;
- terminal target: `target_logret`, `z_target` where `z_target = target_logret / iv_scale`;
- symmetric surface summaries for widths `1,2,3,4,5,6,8,10`: `tail{w}_pct`, `tailratio{w}`, `skewpx{w}`.

The script verifies that `tailratio{w} = tail{w}_pct / atm_straddle_pct` and that the `z_target` identity holds before estimating anything. Raw/licensed rows remain excluded from git.

Run locally with:

```bash
python src/run_phase2.py \
  --input data/expiry_range_close_panel.csv \
  --out results
```
