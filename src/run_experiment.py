#!/usr/bin/env python3
"""Nested-information-set experiment for NIFTY options.

Question: does the option-implied state observed immediately before 10:00 IST
contain incremental information about subsequent 10:00-15:00 realized variance
beyond a backward-looking spot/realized-volatility information set?

The script intentionally uses simple models. Its purpose is an information-set
comparison, not a model horse race.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss

EVAL_START = pd.Timestamp('2025-01-01')
EVAL_END = pd.Timestamp('2026-05-14')
RIDGE_ALPHA = 10.0
LOGIT_C = 0.1
BLOCK = 5
BOOT_DRAWS = 10000
SEED = 20260912

HIST = ['dte','dow','gap','morningret','morningrv','morningrange','rv1','rv5','rv22','lagret1','lagret5']
LEVEL = HIST + ['premium','imp_sd','forward_offset']
SHAPE = LEVEL + ['skew']
SETS = {
    'history_only': HIST,
    'history_plus_option_level': LEVEL,
    'history_plus_level_plus_skew': SHAPE,
}


def qlike(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    z = y / np.clip(p, 1e-12, None)
    return z - np.log(z) - 1.0


def circular_block_bootstrap_mean_diff(a, b, block=5, draws=10000, seed=1):
    """Paired circular block bootstrap for mean(a-b); negative favours a."""
    pair = pd.concat([pd.Series(a), pd.Series(b)], axis=1).dropna()
    d = (pair.iloc[:, 0] - pair.iloc[:, 1]).to_numpy(float)
    n = len(d)
    if n == 0:
        return {'n': 0, 'mean_diff': np.nan, 'ci_low': np.nan, 'ci_high': np.nan, 'p_one_sided': np.nan}
    rng = np.random.default_rng(seed)
    starts = np.arange(n)
    vals = np.empty(draws)
    offsets = np.arange(block)
    n_blocks = int(np.ceil(n / block))
    for j in range(draws):
        chosen = rng.choice(starts, size=n_blocks, replace=True)
        idx = ((chosen[:, None] + offsets[None, :]) % n).ravel()[:n]
        vals[j] = d[idx].mean()
    return {
        'n': int(n),
        'mean_diff': float(d.mean()),
        'ci_low': float(np.quantile(vals, 0.025)),
        'ci_high': float(np.quantile(vals, 0.975)),
        'p_one_sided': float(np.mean(vals >= 0)),
    }


def prep_X(f, cols):
    X = f[cols].replace([np.inf, -np.inf], np.nan).copy()
    for c in ['morningrv','rv1','rv5','rv22','premium','imp_sd']:
        if c in X:
            X[c] = np.log(X[c].clip(lower=1e-10))
    return X


def monthly_expanding_predictions(f):
    reg_preds = {k: pd.Series(np.nan, index=f.index, dtype=float) for k in SETS}
    tail_preds = {k: pd.Series(np.nan, index=f.index, dtype=float) for k in SETS}
    tail_actual = pd.Series(np.nan, index=f.index, dtype=float)
    tail_threshold = pd.Series(np.nan, index=f.index, dtype=float)
    smearing_rows = []
    windows = []

    months = sorted(f.loc[EVAL_START:EVAL_END].index.to_period('M').unique())
    for month in months:
        start = month.start_time
        end = min(month.end_time, EVAL_END)
        tr = (f.index < start - pd.Timedelta(days=1)) & np.isfinite(f.rvtarget) & (f.rvtarget > 0)
        te = (f.index >= start) & (f.index <= end)
        if tr.sum() < 500 or te.sum() == 0:
            continue

        q10 = float(np.quantile(f.loc[tr, 'return_target'], 0.10))
        ytail_tr = (f.loc[tr, 'return_target'] < q10).astype(int)
        tail_actual.loc[te] = (f.loc[te, 'return_target'] < q10).astype(int)
        tail_threshold.loc[te] = q10

        for name, cols in SETS.items():
            X = prep_X(f, cols)
            reg = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), Ridge(alpha=RIDGE_ALPHA))
            ylog = np.log(f.loc[tr, 'rvtarget'].clip(lower=1e-12))
            reg.fit(X.loc[tr], ylog)
            train_log_hat = reg.predict(X.loc[tr])
            smear = float(np.mean(np.exp(ylog.to_numpy() - train_log_hat)))
            reg_preds[name].loc[te] = np.exp(reg.predict(X.loc[te])) * smear
            smearing_rows.append({'month': str(month), 'model': name, 'smearing_factor': smear})

            clf = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=LOGIT_C, max_iter=3000))
            clf.fit(X.loc[tr], ytail_tr)
            tail_preds[name].loc[te] = clf.predict_proba(X.loc[te])[:, 1]

        windows.append({'month': str(month), 'n_train': int(tr.sum()), 'n_test': int(te.sum()), 'train_end': str(f.index[tr][-1].date()), 'tail_threshold': q10})

    return reg_preds, tail_preds, tail_actual, tail_threshold, pd.DataFrame(smearing_rows), pd.DataFrame(windows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Path to daily_features.csv')
    ap.add_argument('--output', default=str(Path(__file__).resolve().parents[1] / 'results'))
    args = ap.parse_args()

    input_path = Path(args.input)
    results = Path(args.output)
    tables = results / 'tables'
    figs = results / 'figures'
    local = results / 'local'
    tables.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)

    f = pd.read_csv(input_path, parse_dates=['date']).set_index('date').sort_index()
    missing = sorted(set(sum(SETS.values(), []) + ['rvtarget', 'return_target']) - set(f.columns))
    if missing:
        raise ValueError(f'Missing required columns: {missing}')

    reg, tail, ytail, thr, smear, windows = monthly_expanding_predictions(f)
    evalmask = (f.index >= EVAL_START) & (f.index <= EVAL_END)
    y = f.loc[evalmask, 'rvtarget']

    rows, loss = [], {}
    for name, p in reg.items():
        pp = p.loc[evalmask]
        ok = np.isfinite(pp) & np.isfinite(y)
        yy, ph = y[ok].to_numpy(), pp[ok].to_numpy()
        lq = qlike(yy, ph)
        loss[name] = pd.Series(lq, index=y.index[ok])
        rows.append({'model': name, 'n': int(ok.sum()), 'qlike': float(np.mean(lq)), 'log_rmse': float(np.sqrt(np.mean((np.log(yy) - np.log(ph)) ** 2))), 'median_abs_pct_error': float(np.median(np.abs(ph - yy) / yy)), 'corr_variance': float(np.corrcoef(yy, ph)[0, 1]), 'mean_actual_variance': float(np.mean(yy)), 'mean_predicted_variance': float(np.mean(ph))})
    regmetrics = pd.DataFrame(rows).sort_values('qlike')
    regmetrics.to_csv(tables / 'rv_incremental_metrics.csv', index=False)

    comps = []
    for a, b, label in [('history_plus_option_level','history_only','level_minus_history'), ('history_plus_level_plus_skew','history_plus_option_level','skew_minus_level'), ('history_plus_level_plus_skew','history_only','full_minus_history')]:
        d = circular_block_bootstrap_mean_diff(loss[a], loss[b], BLOCK, BOOT_DRAWS, SEED + len(comps))
        d.update({'comparison': label, 'loss': 'QLIKE', 'interpretation': 'negative favors first model'})
        comps.append(d)
    boot = pd.DataFrame(comps)
    boot.to_csv(tables / 'rv_paired_block_bootstrap.csv', index=False)

    yr = []
    for year in [2025, 2026]:
        for name in SETS:
            z = loss[name][loss[name].index.year == year]
            yr.append({'year': year, 'model': name, 'n': int(z.size), 'qlike': float(z.mean())})
    pd.DataFrame(yr).to_csv(tables / 'rv_metrics_by_year.csv', index=False)

    tailrows, brier_losses = [], {}
    yy = ytail.loc[evalmask]
    for name, p in tail.items():
        pp = p.loc[evalmask]
        ok = np.isfinite(pp) & np.isfinite(yy)
        ya, pr = yy[ok].astype(int).to_numpy(), pp[ok].to_numpy()
        brier = (pr - ya) ** 2
        brier_losses[name] = pd.Series(brier, index=yy.index[ok])
        tailrows.append({'model': name, 'n': int(ok.sum()), 'event_rate': float(ya.mean()), 'roc_auc': float(roc_auc_score(ya, pr)), 'average_precision': float(average_precision_score(ya, pr)), 'brier': float(brier_score_loss(ya, pr)), 'log_loss': float(log_loss(ya, pr, labels=[0, 1]))})
    tailmetrics = pd.DataFrame(tailrows).sort_values('brier')
    tailmetrics.to_csv(tables / 'downside_tail_metrics.csv', index=False)
    tcomps = []
    for a, b, label in [('history_plus_option_level','history_only','level_minus_history'), ('history_plus_level_plus_skew','history_plus_option_level','skew_minus_level'), ('history_plus_level_plus_skew','history_only','full_minus_history')]:
        d = circular_block_bootstrap_mean_diff(brier_losses[a], brier_losses[b], BLOCK, BOOT_DRAWS, SEED + 100 + len(tcomps))
        d.update({'comparison': label, 'loss': 'Brier', 'interpretation': 'negative favors first model'})
        tcomps.append(d)
    pd.DataFrame(tcomps).to_csv(tables / 'downside_tail_paired_block_bootstrap.csv', index=False)

    smear.to_csv(tables / 'monthly_smearing_factors.csv', index=False)
    windows.to_csv(tables / 'forecast_windows.csv', index=False)

    out = pd.DataFrame(index=f.index[evalmask])
    out['rv_actual'] = f.loc[evalmask, 'rvtarget']
    out['return_10_15'] = f.loc[evalmask, 'return_target']
    out['tail_event'] = ytail.loc[evalmask]
    out['tail_threshold'] = thr.loc[evalmask]
    for name in SETS:
        out[f'rv_pred__{name}'] = reg[name].loc[evalmask]
        out[f'tail_prob__{name}'] = tail[name].loc[evalmask]
    out.to_csv(local / 'oos_predictions.csv')

    import matplotlib.pyplot as plt
    order = ['history_only','history_plus_option_level','history_plus_level_plus_skew']
    labels = ['History only','+ option level','+ crude skew']
    r = regmetrics.set_index('model').loc[order]
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    ax.bar(labels, r['qlike'].values)
    ax.set_ylabel('Out-of-sample QLIKE (lower is better)')
    ax.set_title('Nested information sets: future 10:00–15:00 realized variance')
    ax.spines[['top','right']].set_visible(False)
    fig.tight_layout(); fig.savefig(figs / 'rv_qlike_nested_models.png', dpi=180); plt.close(fig)

    d_level = (loss['history_plus_option_level'] - loss['history_only']).sort_index().cumsum()
    d_skew = (loss['history_plus_level_plus_skew'] - loss['history_plus_option_level']).sort_index().cumsum()
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.plot(d_level.index, d_level.values, label='Option level − history')
    ax.plot(d_skew.index, d_skew.values, label='Skew − option level')
    ax.axhline(0, linewidth=1)
    ax.set_ylabel('Cumulative paired QLIKE difference')
    ax.set_title('Incremental forecast loss through the evaluation block')
    ax.legend(frameon=False)
    ax.spines[['top','right']].set_visible(False)
    fig.tight_layout(); fig.savefig(figs / 'cumulative_qlike_differences.png', dpi=180); plt.close(fig)

    option_row = regmetrics.set_index('model').loc['history_plus_option_level']
    hist_row = regmetrics.set_index('model').loc['history_only']
    skew_row = regmetrics.set_index('model').loc['history_plus_level_plus_skew']
    qlike_improvement = 100.0 * (hist_row.qlike - option_row.qlike) / hist_row.qlike
    skew_change = 100.0 * (option_row.qlike - skew_row.qlike) / option_row.qlike

    summary = {
        'sample': {'full_start': str(f.index.min().date()), 'full_end': str(f.index.max().date()), 'evaluation_start': str(EVAL_START.date()), 'evaluation_end': str(EVAL_END.date()), 'n_eval': int(evalmask.sum())},
        'primary_question': 'Does the 09:59 option-implied level add information for 10:00-15:00 realized variance beyond backward-looking spot/history variables?',
        'secondary_question': 'Does the available crude skew proxy add incremental information beyond option level?',
        'feature_sets': SETS,
        'regression_metrics': regmetrics.to_dict(orient='records'),
        'rv_bootstrap': boot.to_dict(orient='records'),
        'qlike_improvement_option_level_vs_history_pct': float(qlike_improvement),
        'qlike_change_skew_vs_level_pct': float(skew_change),
        'tail_metrics_secondary': tailmetrics.to_dict(orient='records'),
        'notes': ['Monthly expanding-window estimation.', 'One-calendar-day purge before each test month.', 'Duan smearing is estimated from each training window before retransformation.', '2025-01-01 through 2026-05-14 is an evaluation block, but it is not claimed to be a pristine prospective holdout for this newly formulated Lehalle-motivated hypothesis.', 'The skew variable is a crude legacy proxy, not a fully identified eSSVI rho/psi or fixed-delta risk reversal.', 'Row-level predictions and source market data are excluded from the public repository.'],
    }
    (results / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
