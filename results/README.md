# Results

This folder contains only aggregate tables and figures suitable for a public repository. Row-level predictions are written to `results/local/`, which is gitignored.

## Phase I — realised-variance information

- `tables/rv_incremental_metrics.csv` — nested information-set forecast metrics.
- `tables/rv_paired_block_bootstrap.csv` — paired QLIKE block-bootstrap comparisons.
- `tables/rv_metrics_by_year.csv` — fixed-specification calendar-year diagnostics.
- Phase-I PNG figures are generated locally by `src/run_experiment.py`; binary exports are intentionally not versioned.

## Phase II — tail geometry conditional on ATM scale

- `phase2_summary.json` — machine-readable Phase-II summary.
- `tables/phase2_tail_metrics.csv` — weekly-expiry probability metrics.
- `tables/phase2_tail_bootstrap.csv` — pairs-bootstrap differences in Brier/log-loss.
- `tables/phase2_conditional_direction.csv` — downside-vs-upside diagnostics among realised one-scale breaches.
- `tables/phase2_conditional_direction_bootstrap.csv` — uncertainty for the conditional-direction comparison.
- `tables/phase2_width_sensitivity.csv` — every tested symmetric width; no winner selection.
- `tables/phase2_shape_coefficients.csv` — standardized logistic coefficients for the predeclared composite shape factors.
- `figures/lehalle_anticipative_map.svg` — compact public figure combining the Phase-II score and width-robustness results.
- Phase-II PNG figures are generated locally by `src/run_phase2.py`; binary exports are intentionally not versioned.
