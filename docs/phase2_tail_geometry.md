# Phase II — does smile geometry say *which* tail?

## Executive result

Phase I found that the short-dated option **level** materially improves forecasts of subsequent realised variance, while a single crude skew proxy does not improve aggregate variance forecasting.

Phase II asks a different question: once the ATM option market has already supplied an ex-ante movement scale, does the **shape of the option price surface** contain information about *which side of that scale is more likely to be breached*?

The result is deliberately mixed:

- **Magnitude:** no. Adding smile geometry does not improve the probability of a two-sided one-implied-scale breach.
- **Direction:** suggestive, but not established. Shape improves the upside-tail probability score in the 2025–May 2026 evaluation block, and improves downside-vs-upside classification conditional on a realised large move. The evaluation contains only 73 independent expiry cycles and 23 one-scale breaches, so the uncertainty remains wide.
- **Across wing widths:** the direction pattern is surprisingly stable. Shape worsens the two-sided breach Brier score at all eight tested symmetric widths, improves the upside-breach Brier score at all eight widths, and improves conditional tail direction at all eight widths. These widths are highly correlated and therefore **not eight independent confirmations**; the width table is a robustness diagnostic, not a multiple-testing victory lap.

The narrow interpretation is therefore:

> The current evidence is consistent with ATM options carrying most of the information about **how much** the market may move, while cross-strike geometry may carry weaker information about **where** tail risk is tilted. The latter is a hypothesis for a cleaner eSSVI test, not yet a confirmed “anticipative factor.”

## 1. Data object and non-overlap rule

The historical panel contains daily NIFTY spot state, ATM option state, symmetric tail-price measures, and the return from the observation date to the nearest weekly expiry.

For each usable row,

\[
z_t = \frac{r_{t\rightarrow E}}{s^{IV}_t},
\]

where `target_logret = r_(t→E)` and `iv_scale = s_IV`. The source panel satisfies the identity

`z_target = target_logret / iv_scale`

to numerical precision. Thus `|z_target| >= 1` means the realised expiry move exceeded one ex-ante option-implied movement scale.

The daily panel has overlapping targets within an expiry cycle. The headline Phase-II test therefore keeps **one observation per weekly expiry**: the earliest usable observation for that expiry. This produces:

- development: **209 expiries**, through 2024-12-31;
- evaluation: **73 expiries**, 2025-01-03 through 2026-05-13;
- one-scale breaches in evaluation: **23**.

This is intentionally more conservative than treating every daily row as independent.

## 2. Surface-shape variables

At symmetric wing-width index `w`, the panel contains:

- `tailratio_w = tail_w_pct / atm_straddle_pct`, a dimensionless measure of symmetric tail richness relative to the ATM straddle;
- `skewpx_w`, a signed fixed-width price-skew proxy.

Widths `w ∈ {1,2,3,4,5,6,8,10}` are retained. No width is chosen from the evaluation sample.

Because both measures change mechanically with time to expiry, each raw shape field is converted into a **DTE-conditioned development z-score**. The mean and standard deviation for each calendar-DTE bucket are estimated only on 2021–2024. Evaluation rows are transformed with those frozen statistics.

The predeclared composite shape state is then

\[
SkewFactor_t = \frac{1}{8}\sum_w z^{DTE}(skewpx_{w,t}),
\]

\[
TailFactor_t = \frac{1}{8}\sum_w z^{DTE}(tailratio_{w,t}).
\]

Averaging across all widths is deliberate: it avoids picking whichever wing looks best after seeing 2025–2026.

## 3. Information sets

The **level-controls** model includes only information available at the observation date:

- horizon (`log_cal`),
- lagged realised volatility (`log_rv5`, `log_rv20`),
- lagged absolute returns,
- current overnight gap magnitude,
- current daily range,
- `log(iv_scale)`,
- `log(ATM IV)`.

The **plus-shape** model uses the identical specification and adds only:

- `skew_factor`,
- `tail_factor`.

Both use the same fixed L2 logistic regression (`C=1`); no hyperparameter search is performed on the evaluation block.

## 4. Primary tail events

Three unconditional events are evaluated:

1. **two-sided breach:** `|z_target| >= 1`;
2. **downside breach:** `z_target <= -1`;
3. **upside breach:** `z_target >= +1`.

Proper probability scores are primary: Brier score and log loss. AUC is reported only as a ranking diagnostic.

### 4.1 Evaluation metrics

| Event | Model | Events / N | Brier ↓ | Log loss ↓ | AUC ↑ |
|---|---|---:|---:|---:|---:|
| Two-sided | Level controls | 23 / 73 | **0.22676** | **0.64759** | 0.5009 |
| Two-sided | + shape | 23 / 73 | 0.22877 | 0.65275 | 0.4930 |
| Downside | Level controls | 13 / 73 | 0.15644 | 0.50056 | 0.5744 |
| Downside | + shape | 13 / 73 | **0.15613** | **0.49151** | **0.5962** |
| Upside | Level controls | 10 / 73 | 0.12268 | 0.40682 | 0.6048 |
| Upside | + shape | **10 / 73** | **0.11344** | **0.38523** | **0.6349** |

The two-sided result is a clean null: shape does not help predict whether the realised move will exceed the ATM-implied scale.

The upside-tail result is more interesting. Adding the composite surface shape reduces Brier score by about **7.5%** relative to level controls and improves AUC by about **3.0 points**. A pairs bootstrap over weekly expiries gives a Brier difference (`shape − level`) of approximately **−0.00925**, with a 95% interval **[−0.01982, +0.00102]**. The one-sided non-improvement fraction is about **3.8%**. Because the two-sided interval still includes zero and only ten upside events occur, this is reported as **suggestive**, not definitive.

For downside breaches, the average proper scores improve only slightly and bootstrap uncertainty is much larger.

## 5. Conditional tail direction

A secondary diagnostic conditions on the future event `|z_target| >= 1` and asks: **given that a large move occurred, can today’s state distinguish downside from upside?**

This is *not* a directly tradeable ex-ante event definition because the sample is selected using the future realised breach. It is used only to diagnose whether smile geometry contains directional state information.

There are 23 evaluation breaches, 13 downside and 10 upside.

| Model | Brier ↓ | Log loss ↓ | AUC ↑ |
|---|---:|---:|---:|
| Level controls | 0.26320 | 0.72730 | 0.6308 |
| + shape | **0.22410** | **0.66706** | **0.6846** |

The Brier score falls by roughly **14.9%**. However the pairs-bootstrap 95% interval for the difference is **[−0.1103, +0.0376]**. With only 23 realised breaches, this is far from a confirmation.

The standardized composite-model coefficients are nevertheless economically interpretable as a clue rather than a result: greater tail richness loads positively toward downside conditional on a large move, while the aggregate skew factor loads negatively. These signs should be retested with clean eSSVI/RR/BF objects before being given structural meaning.

## 6. Width sensitivity: a useful pattern, not independent evidence

The analysis is repeated separately at every available symmetric width without selecting a winner.

For Brier score (`shape − level`, negative is better):

- **two-sided breach:** 0 of 8 widths improve;
- **downside breach:** 4 of 8 widths improve;
- **upside breach:** 8 of 8 widths improve;
- **downside vs upside conditional on a breach:** 8 of 8 widths improve.

The striking point is qualitative: **shape behaves much more consistently for direction than for magnitude**. Since adjacent smile widths are highly correlated, a sign count cannot be interpreted as eight independent tests or converted into a naive binomial p-value.

![Phase II score and width sensitivity](../results/figures/lehalle_anticipative_map.svg)

## 7. How this relates to the exact eSSVI implementation

The Shaurya research tree already contains a one-slice historical eSSVI reconstruction at the causal 10:00 origin in:

`research/scratch/gap_open_analysis/rv_forecast_v2.py`

That implementation constructs `theta`, `rho`, `psi`, `phi`, local total-variance skew, fixed-width RR/BF objects, fit RMSE and support diagnostics from the rolling option archive. It also constructs total/day/night realised-variance targets with strict no-lookahead rules.

Phase II-A does **not** pretend that the current price-skew/tail-ratio panel is equivalent to those eSSVI parameters. The raw 2021–2024 archive surfaced through the connected Drive is represented partly through symlink manifests, while directly downloadable rolling files are readily available for the later period. Rather than reverse-engineer `rho` or `psi` from summary columns, this repository keeps the current result explicitly labelled as a **tail-geometry proxy experiment**.

The next exact replication should use the existing Shaurya surface builder unchanged and freeze:

`history + theta` versus `history + theta + {rho, psi, RR, BF, shape innovations}`

on a later, genuinely untouched block.

## 8. Connection to Lehalle

This result sharpens the question we can eventually put to Charles-Albert Lehalle.

Phase I suggests that listed option prices contain a forward-looking volatility scale that is not fully reconstructed from recent spot history. Phase II-A says that **surface geometry does not add obvious information about the absolute size of the move**, but may contain weaker information about **the direction in which tail probability is tilted**.

That distinction maps naturally onto his backward-looking-versus-anticipative framing:

> If the ATM level is mostly a forward conditional variance estimate, while cross-strike state prices tilt the distribution toward particular future states, should the latter be viewed as closer to an “anticipative factor”? Or are both simply endogenous risk prices generated by the same inventory, hedging and information-flow mechanism?

The empirical evidence here is not yet strong enough to answer that question. It is strong enough to make the question non-generic.
