# Research note: are short-dated options anticipative factors?

## 1. Motivation

Lehalle (2026) proposes a distinction between backward-looking liquidity factors, which are visible in historical variance, and anticipative factors, which correspond to risks/beliefs about future states that need not yet have produced historical price variation. Short-dated index options are a useful boundary case because they are simultaneously:

- listed, liquid financial instruments embedded in ordinary market microstructure;
- subject to inventory, hedging and endogenous flow effects; and
- state-contingent claims whose prices aggregate beliefs and risk premia about the near future.

The empirical strategy therefore begins with an intentionally weaker question than “are options anticipative factors?”: **does the option state contain incremental forecast information after conditioning on the historical spot state?**

## 2. Data timing

One row represents one NIFTY trading session.

- Feature observation grid: 09:59 IST.
- Forecast starts: 10:00 IST.
- Forecast ends: 15:00 IST.
- Target realized variance: sum of squared 5-minute log returns over the forecast interval.
- Evaluation block: 2025-01-01 to 2026-05-14 (337 sessions).
- Historical feature archive: 2021-01-01 to 2026-05-14 (1,322 sessions).

The current block is useful for model comparison but is **not described as a pristine prospective holdout for this newly formulated hypothesis**. The hypothesis was motivated after this historical archive already existed and had been used for other volatility research.

## 3. Nested information sets

### H — historical/spot state

`dte`, `dow`, `gap`, `morningret`, `morningrv`, `morningrange`, `rv1`, `rv5`, `rv22`, `lagret1`, `lagret5`.

### H + L — add option-implied level

Adds `premium`, `imp_sd`, `forward_offset`.

### H + L + S — add crude shape proxy

Adds `skew`.

The purpose of nesting is identification by information content: all three specifications use the same estimator and retraining schedule, so performance changes can be attributed to the additional information set rather than a more flexible model family.

## 4. Estimation

The target model is ridge regression for `log(rvtarget)`, with a fixed ridge penalty of 10. Positive volatility-scale covariates are log-transformed. Models are re-estimated at the start of each month with expanding historical data.

A crucial retransformation step is applied. If

`log(RV) = x'beta + epsilon`,

then simply exponentiating the fitted log value estimates a median-like quantity rather than the conditional mean in variance space. Each training window therefore estimates the Duan smearing factor

`m = mean(exp(epsilon_hat))`,

and forecasts

`RV_hat = exp(x'beta_hat) * m`.

This correction materially matters for QLIKE and is fixed in the repository implementation.

## 5. Primary loss and inference

Primary loss is QLIKE:

`L(y, yhat) = y/yhat - log(y/yhat) - 1`.

Pairwise model comparisons use a 10,000-draw paired circular moving-block bootstrap with 5-session blocks. The bootstrap is applied to the daily loss differential so serial dependence in forecast performance is not treated as iid noise.

## 6. Preliminary result

| Model | QLIKE | Correlation |
|---|---:|---:|
| H | 0.18196 | 0.429 |
| H + L | **0.14579** | **0.602** |
| H + L + S | 0.14587 | 0.604 |

`H + L` improves QLIKE by 19.9% relative to `H`. The paired QLIKE differential (`H+L` minus `H`) is -0.03617, with bootstrap 95% interval [-0.07687, -0.00463]. The direction is also stable in the two calendar slices: QLIKE improves from 0.1895 to 0.1529 in 2025 and from 0.1609 to 0.1259 in the available 2026 block.

The incremental skew result is null: QLIKE differential (`H+L+S` minus `H+L`) is +0.00008, 95% interval [-0.00106, +0.00121].

## 7. What this does and does not mean

### Supported by the current exercise

The short-dated option **level** contains forecast information about subsequent realized variance that is incremental to the chosen backward-looking spot state.

### Not supported yet

The analysis does not identify why the option signal is informative. In particular it does not separate:

- informed expectations from variance risk premia;
- exogenous information from dealer/inventory effects;
- genuine state-price shape information from a superior volatility-scale estimate;
- causal price discovery from correlated response to a common latent state.

The current legacy skew proxy also has weak structural interpretation, so its null result should not be treated as evidence that surface shape is useless.

## 8. Phase-II status and exact next experiment

The first shape extension has now been run and is documented separately in [`phase2_tail_geometry.md`](phase2_tail_geometry.md). Rather than reusing the same-day variance target, Phase II-A conditions the future expiry return on an ex-ante ATM-implied movement scale and asks whether multi-width smile geometry adds information about tail direction.

Its main result is deliberately modest: geometry does **not** improve prediction of two-sided large-move probability, while directional tail scores improve more consistently but remain statistically uncertain because the independent weekly-expiry sample is small.

The exact eSSVI experiment remains the cleaner next step. The existing Shaurya research tree already contains the causal one-slice eSSVI reconstruction at 10:00, including `theta`, `rho`, `psi`, RR/BF and fit-quality diagnostics. The future test should preserve that implementation and compare:

`history + theta` versus `history + theta + {rho, psi, RR, BF, shape innovations}`

using a genuinely later untouched block, with total/day/night variance and directional-tail targets reported separately.

## 9. Connection to Lehalle

The experiment is designed as an empirical response to a conceptual boundary in Lehalle's recent work. His July 2026 note asks when backward-looking statistical factors and forward-looking information might separate. His 2025 price-formation talk emphasizes the chain from information to flows to prices, and his Queue-Reactive project asks whether exogenous price moves can be distinguished from endogenous liquidity dynamics.

Options create a particularly interesting test because they are *both* prices generated inside the ordinary liquidity mechanism and state-contingent contracts explicitly linked to future outcomes. The central unresolved question is therefore not simply whether options forecast volatility, but **which component of their information is anticipative and which component is the endogenous price of liquidity/risk bearing?**
