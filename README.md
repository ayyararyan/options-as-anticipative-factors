# Options as Anticipative Factors?

**A small empirical study of whether short-dated index options contain forward-looking risk information that is not recoverable from the recent spot process.**

This repository starts from a question suggested by Charles-Albert Lehalle's July 2026 note, [*The Price Discovery Crisis? From Mechanical Flows to Foresight Narratives*](https://www.cmap.polytechnique.fr/~charles-albert.lehalle/blog/2026-07-28/). Lehalle distinguishes backward-looking **Liquidity Factors**, which are statistically visible in historical variance, from **Anticipative Factors**, which represent risk directions associated with possible future states and may not yet be visible in historical price variation.

Short-dated options sit awkwardly between those categories. They are traded on ordinary listed markets and are exposed to mechanical dealer and liquidity flows, but they are also state-contingent claims whose prices are explicitly forward-looking. This project asks whether they carry incremental information about near-future risk after conditioning on the recent spot process.

> **Status:** preliminary research note / reproducible experiment. The current evidence is deliberately treated as diagnostic rather than as a finished causal result.

## Questions

### Q1 — Does the option-implied level add information beyond spot history?

At 09:59 IST, can the option-implied state improve forecasts of NIFTY realized variance from 10:00 to 15:00 after conditioning on lagged realized variance, the opening gap, and the current morning's spot state?

### Q2 — Does smile asymmetry add information beyond the option level?

After controlling for the option-implied level, does the available skew proxy provide additional information about future variance or downside-tail risk?

The second question matters because a level effect alone may simply reflect a better estimate of the conditional volatility scale. A stable incremental shape effect would be closer to a claim that the option surface is encoding *which states* the market is concerned about.

## First result

The first pass uses 1,322 NIFTY sessions from 2021-01-01 to 2026-05-14 and evaluates monthly expanding-window forecasts over 337 sessions from 2025-01-01 to 2026-05-14. The target is five-minute realized variance from 10:00 to 15:00. All option features are observed on the 09:59 grid.

| Information set | OOS QLIKE | Corr(actual, forecast) |
|---|---:|---:|
| Spot/history only | 0.18196 | 0.429 |
| + option-implied level | **0.14579** | **0.602** |
| + crude skew proxy | 0.14587 | 0.604 |

Adding option-level information reduces QLIKE by **19.9%** relative to the history-only model. A paired 5-session circular block bootstrap gives a mean QLIKE difference of **-0.0362**, with a 95% interval **[-0.0769, -0.0046]**; negative values favor the option-level model.

The skew result is intentionally less exciting: adding the legacy skew proxy changes QLIKE by essentially zero (mean paired difference **+0.00008**, 95% interval **[-0.00106, +0.00121]**). On this dataset we therefore **do not** have evidence that this crude shape statistic contributes incremental variance information beyond the option level.

## Phase II — does smile geometry say *which* tail?

Phase II deliberately changes the estimand. Instead of asking whether a crude skew variable improves the conditional mean of realised variance, it asks whether cross-strike option geometry adds information **after normalising the future expiry return by the ex-ante option-implied movement scale**. In the source panel, `z_target = target_logret / iv_scale` exactly.

To avoid overlapping expiry targets, the headline test keeps one earliest usable observation per weekly expiry. Development is 2021–2024 (**209 expiries**) and evaluation is 2025 through 13 May 2026 (**73 expiries**). Shape variables are DTE-normalised using development statistics only, then averaged across all eight available symmetric wing widths so no evaluation-period width is selected.

| Tail event | Level controls Brier ↓ | + surface shape Brier ↓ | AUC: level → shape |
|---|---:|---:|---:|
| `|z| >= 1` | **0.22676** | 0.22877 | 0.501 → 0.493 |
| `z <= -1` | 0.15644 | **0.15613** | 0.574 → 0.596 |
| `z >= +1` | 0.12268 | **0.11344** | 0.605 → 0.635 |

The important negative result survives: **shape does not improve the probability that the move is large in absolute terms.** The more interesting result is directional. The composite shape state reduces the upside-breach Brier score by about **7.5%**; the paired weekly-expiry bootstrap difference is about **-0.00925**, with a 95% interval **[-0.01982, +0.00102]**. That is suggestive rather than conclusive because there are only ten upside breaches.

Conditioning diagnostically on the 23 realised one-scale breaches, adding shape improves downside-vs-upside classification from Brier **0.2632 → 0.2241** and AUC **0.631 → 0.685**, but the bootstrap interval is wide. Across the eight symmetric wing widths, shape improves the upside-breach Brier score at **8/8 widths** and conditional tail direction at **8/8 widths**, while it improves the two-sided breach score at **0/8 widths**. Adjacent widths are highly correlated, so those counts are a robustness pattern, not eight independent tests.

### Email-ready research note

For a compact visual summary of the Phase-II question, see the email-ready figure below and the GitHub-readable one-page note in [`docs/lehalle_one_page_note.md`](docs/lehalle_one_page_note.md). The same generator also produces a local PDF for email attachment. Both are built only from versioned aggregate outputs, so they can be reproduced without the licensed row-level market data.

![Where does the smile's extra information live?](results/figures/lehalle_anticipative_map.svg)

Rebuild the figure, compact table, and one-page note with:

```bash
python src/make_outreach_assets.py
```

The narrow working hypothesis is now: **ATM options seem to carry most of the information about movement magnitude; smile geometry may carry weaker information about the direction in which tail probability is tilted.** See [`docs/phase2_tail_geometry.md`](docs/phase2_tail_geometry.md) for the full protocol, caveats and bootstrap results.

## What remains before calling shape an anticipative factor

The current Phase-II surface measures are fixed-width price/tail proxies, not clean eSSVI state variables. The existing Shaurya research code already contains the causal 10:00 one-slice eSSVI reconstruction (`theta`, `rho`, `psi`, fixed-width RR/BF and fit diagnostics). The next exact test is therefore frozen conceptually as:

`history + theta` **vs** `history + theta + {rho, psi, RR, BF, shape innovations}`

on a genuinely later block, with total/day/night variance and directional tail targets reported separately. We do **not** reverse-engineer `rho` or `psi` from summary variables merely to manufacture a cleaner-looking Phase-II result.

## Phase I design

Three nested information sets are compared using the same ridge specification:

- **History:** DTE/day-of-week, opening gap, morning return/range/RV, lagged 1/5/22-session realized variance, and lagged returns.
- **History + option level:** adds normalized ATM straddle premium, implied normal scale, and parity/forward offset.
- **History + option level + skew:** adds the existing cross-wing skew proxy.

Models are re-estimated monthly using expanding history. The variance regression is fit in log space and **Duan smearing** is estimated inside each training window before converting predictions back to variance. QLIKE is the primary loss. Inference uses paired circular moving-block bootstrap samples with 5-session blocks.

The code also runs a secondary downside-tail classifier. Its results are retained for completeness but are **not** the primary claim: option features modestly improve ranking metrics, while paired Brier-score improvements are not statistically clean in this sample.

## Interpretation

The evidence currently supports a narrow statement:

> **The contemporaneous short-dated option level contains incremental information about same-day future realized variance that is not captured by the chosen backward-looking spot/history state.**

It does **not** yet show that this information is exogenous, causal, or an “Anticipative Factor” in Lehalle's stronger sense. Option prices themselves are generated by informed beliefs, dealer inventory, hedging, risk premia, and market microstructure. Distinguishing those channels is the research question, not something assumed away.

This framing also connects to Lehalle's recent work on the meeting of exogenous information and endogenous position adjustment in price formation, and his Queue-Reactive work on distinguishing exogenous from endogenous price moves.

## Reproduce

The underlying historical market data are not redistributed in this public repository. Put a compatible `daily_features.csv` in `data/` (schema below), then run:

```bash
python -m pip install -r requirements.txt
python src/run_experiment.py --input data/daily_features.csv
```

For Phase II, place a compatible expiry-range panel at `data/expiry_range_close_panel.csv`, then run:

```bash
python src/run_phase2.py --input data/expiry_range_close_panel.csv --out results
```

Aggregate result tables and figures are versioned under `results/`. Row-level market observations and predictions are gitignored.

See [`data/README.md`](data/README.md) for both schemas, [`docs/research_note.md`](docs/research_note.md) for Phase I, and [`docs/phase2_tail_geometry.md`](docs/phase2_tail_geometry.md) for Phase II.

## Related Lehalle material

- Charles-Albert Lehalle (2026), [*The Price Discovery Crisis? From Mechanical Flows to Foresight Narratives*](https://www.cmap.polytechnique.fr/~charles-albert.lehalle/blog/2026-07-28/).
- Charles-Albert Lehalle (2025), [*How Confrontation Of Information And Flows Shapes Prices*](https://www.cmap.polytechnique.fr/~charles-albert.lehalle/publications/2025_2/).
- Charles-Albert Lehalle (2025), [*Permanent Impact has a confounder*](https://www.cmap.polytechnique.fr/~charles-albert.lehalle/blog/2025-03-10/).
- Charles-Albert Lehalle, project note (2025), [*Detection of Exogenous Price Moves: Localising the Queue Reactive Model*](https://www.cmap.polytechnique.fr/~charles-albert.lehalle/projects/2024QR/).

## Author

Aryan Ayyar

## License

Code is released under the MIT License. Market data are not included and remain subject to their original provider/exchange terms.
