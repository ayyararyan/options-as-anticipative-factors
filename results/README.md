# Results

This directory contains only aggregate outputs from the two experiments reported in the main README. Raw market observations and row-level predictions are not versioned.

- `summary.json` and `tables/rv_*` contain the realized-variance forecast results for Question 1.
- `phase2_summary.json` and `tables/phase2_*` contain the expiry-tail results for Question 2.
- `figures/main_result.svg` is the main public figure; PNG and PDF versions can be regenerated with `python src/make_main_figure.py`.
