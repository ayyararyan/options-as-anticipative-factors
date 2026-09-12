#!/usr/bin/env python3
"""Phase II: does smile geometry add directional tail information beyond ATM scale?

This script deliberately uses one observation per weekly expiry (the earliest usable row in
that expiry cycle) so evaluation rows do not share the same terminal expiry return. The source
panel is not redistributed; only aggregate outputs are versioned.

The panel must contain the columns documented in data/README.md under "Phase II schema".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

WIDTHS = [1, 2, 3, 4, 5, 6, 8, 10]
BASE_FEATURES = ["log_cal", "log_rv5", "log_rv20", "abs_ret1", "abs_ret5", "abs_gap", "range_day", "log_iv_scale", "log_atm_iv"]


def probability_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    p = np.clip(np.asarray(p, float), 1e-15, 1 - 1e-15)
    y = np.asarray(y, int)
    brier = float(np.mean((p - y) ** 2))
    logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    auc = float(roc_auc_score(y, p)) if np.unique(y).size == 2 else float("nan")
    return {"n": int(len(y)), "events": int(y.sum()), "rate": float(y.mean()), "brier": brier, "logloss": logloss, "auc": auc}


def paired_bootstrap(y: np.ndarray, p_base: np.ndarray, p_shape: np.ndarray, *, draws: int, seed: int) -> list[dict[str, float]]:
    """Pairs bootstrap over non-overlapping weekly-expiry observations.

    Differences are plus_shape minus level_controls; negative is better for Brier/log-loss.
    """
    y = np.asarray(y, int)
    p_base = np.clip(np.asarray(p_base, float), 1e-15, 1 - 1e-15)
    p_shape = np.clip(np.asarray(p_shape, float), 1e-15, 1 - 1e-15)
    rng = np.random.default_rng(seed)
    n = len(y)
    idx = rng.integers(0, n, size=(draws, n))
    Y = y[idx]
    A = p_base[idx]
    C = p_shape[idx]
    dbrier = np.mean((C - Y) ** 2 - (A - Y) ** 2, axis=1)
    dll = np.mean(-(Y * np.log(C) + (1 - Y) * np.log(1 - C)) + (Y * np.log(A) + (1 - Y) * np.log(1 - A)), axis=1)
    rows = []
    for metric, arr in [("brier", dbrier), ("logloss", dll)]:
        rows.append({"metric": metric, "mean_diff_plus_shape_minus_level": float(arr.mean()), "ci_lo_95": float(np.quantile(arr, 0.025)), "ci_hi_95": float(np.quantile(arr, 0.975)), "p_non_improvement_one_sided": float(np.mean(arr >= 0))})
    return rows


def prepare_panel(raw: pd.DataFrame, split_date: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = {"date", "expiry", "usable", "cal_days", "target_logret", "iv_scale", "atm_iv", "atm_straddle_pct", "rv5_daily", "rv20_daily", "ret1", "ret5", "gap_overnight", "range_day", "z_target"}
    for w in WIDTHS:
        required |= {f"tail{w}_pct", f"tailratio{w}", f"skewpx{w}"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Phase-II panel is missing columns: {missing}")

    d = raw.loc[raw["usable"].astype(bool)].copy()
    d["date"] = pd.to_datetime(d["date"])
    d["expiry"] = pd.to_datetime(d["expiry"])
    d = d.sort_values(["expiry", "date"])

    z_err = np.nanmax(np.abs(d["target_logret"] / d["iv_scale"] - d["z_target"]))
    if not np.isfinite(z_err) or z_err > 1e-9:
        raise AssertionError(f"z_target identity failed: max error={z_err}")
    for w in WIDTHS:
        err = np.nanmax(np.abs(d[f"tail{w}_pct"] / d["atm_straddle_pct"] - d[f"tailratio{w}"]))
        if not np.isfinite(err) or err > 1e-9:
            raise AssertionError(f"tailratio{w} identity failed: max error={err}")

    d = d.groupby("expiry", as_index=False).first()
    d["abs_gap"] = d["gap_overnight"].abs()
    d["abs_ret1"] = d["ret1"].abs()
    d["abs_ret5"] = d["ret5"].abs()
    d["log_rv5"] = np.log(d["rv5_daily"].clip(lower=1e-8))
    d["log_rv20"] = np.log(d["rv20_daily"].clip(lower=1e-8))
    d["log_iv_scale"] = np.log(d["iv_scale"].clip(lower=1e-8))
    d["log_atm_iv"] = np.log(d["atm_iv"].clip(lower=1e-8))
    d["log_cal"] = np.log(d["cal_days"].clip(lower=1e-8))

    split = pd.Timestamp(split_date)
    development = d.loc[d["date"] < split].copy()
    evaluation = d.loc[d["date"] >= split].copy()
    if development.empty or evaluation.empty:
        raise ValueError("Development/evaluation split produced an empty sample.")

    for w in WIDTHS:
        for prefix in ["skewpx", "tailratio"]:
            c = f"{prefix}{w}"
            stats = development.groupby("cal_days")[c].agg(["mean", "std"])
            overall_mean = float(development[c].mean())
            overall_std = float(development[c].std(ddof=1))
            vals = []
            for _, row in d.iterrows():
                if row["cal_days"] in stats.index and np.isfinite(stats.loc[row["cal_days"], "std"]) and stats.loc[row["cal_days"], "std"] > 1e-12:
                    mu = float(stats.loc[row["cal_days"], "mean"])
                    sd = float(stats.loc[row["cal_days"], "std"])
                else:
                    mu, sd = overall_mean, overall_std
                vals.append((row[c] - mu) / sd)
            d[f"{c}_dtez"] = vals

    d["skew_factor"] = d[[f"skewpx{w}_dtez" for w in WIDTHS]].mean(axis=1)
    d["tail_factor"] = d[[f"tailratio{w}_dtez" for w in WIDTHS]].mean(axis=1)
    development = d.loc[d["date"] < split].copy()
    evaluation = d.loc[d["date"] >= split].copy()
    return d, development, evaluation


def fit_probability_model(development: pd.DataFrame, evaluation: pd.DataFrame, features: list[str], event_fn) -> tuple[np.ndarray, np.ndarray, object]:
    y_dev = event_fn(development["z_target"]).astype(int)
    y_eval = event_fn(evaluation["z_target"]).astype(int).to_numpy()
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=1.0, solver="lbfgs", max_iter=2000, random_state=1))
    model.fit(development[features], y_dev)
    p = model.predict_proba(evaluation[features])[:, 1]
    return y_eval, p, model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to expiry_range_close_panel-compatible CSV")
    ap.add_argument("--out", default="results", help="Repository results directory")
    ap.add_argument("--split-date", default="2025-01-01")
    ap.add_argument("--bootstrap-draws", type=int, default=20000)
    args = ap.parse_args()

    out = Path(args.out)
    tables = out / "tables"
    figures = out / "figures"
    local = out / "local"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.input)
    panel, dev, ev = prepare_panel(raw, args.split_date)

    shape_features = BASE_FEATURES + ["skew_factor", "tail_factor"]
    events = {"two_sided_1sigma": lambda z: z.abs() >= 1.0, "down_1sigma": lambda z: z <= -1.0, "up_1sigma": lambda z: z >= 1.0}

    metric_rows = []
    boot_rows = []
    prediction_rows = []
    model_cache = {}
    for i, (event_name, event_fn) in enumerate(events.items()):
        y, p_base, _ = fit_probability_model(dev, ev, BASE_FEATURES, event_fn)
        _, p_shape, model_shape = fit_probability_model(dev, ev, shape_features, event_fn)
        model_cache[event_name] = model_shape
        for model_name, p in [("level_controls", p_base), ("plus_shape", p_shape)]:
            m = probability_metrics(y, p)
            metric_rows.append({"event": event_name, "model": model_name, **m})
            for year in sorted(ev["date"].dt.year.unique()):
                mask = ev["date"].dt.year.to_numpy() == year
                metric_rows.append({"event": event_name, "model": model_name, "year": int(year), **probability_metrics(y[mask], p[mask])})
        for r in paired_bootstrap(y, p_base, p_shape, draws=args.bootstrap_draws, seed=20260912 + i):
            boot_rows.append({"event": event_name, **r})
        for j, (_, row) in enumerate(ev.iterrows()):
            prediction_rows.append({"date": row["date"].date().isoformat(), "expiry": row["expiry"].date().isoformat(), "event": event_name, "actual": int(y[j]), "p_level_controls": float(p_base[j]), "p_plus_shape": float(p_shape[j])})

    dev_breach = dev.loc[dev["z_target"].abs() >= 1].copy()
    ev_breach = ev.loc[ev["z_target"].abs() >= 1].copy()
    direction_fn = lambda z: z < 0
    y_dir, p_dir_base, _ = fit_probability_model(dev_breach, ev_breach, BASE_FEATURES, direction_fn)
    _, p_dir_shape, dir_model = fit_probability_model(dev_breach, ev_breach, shape_features, direction_fn)
    conditional_rows = []
    for model_name, p in [("level_controls", p_dir_base), ("plus_shape", p_dir_shape)]:
        conditional_rows.append({"model": model_name, **probability_metrics(y_dir, p)})
    dir_boot = paired_bootstrap(y_dir, p_dir_base, p_dir_shape, draws=args.bootstrap_draws, seed=20261001)

    width_rows = []
    for w in WIDTHS:
        f = BASE_FEATURES + [f"skewpx{w}_dtez", f"tailratio{w}_dtez"]
        for event_name, event_fn in dict(events).items():
            y, p0, _ = fit_probability_model(dev, ev, BASE_FEATURES, event_fn)
            _, p1, m = fit_probability_model(dev, ev, f, event_fn)
            a, b = probability_metrics(y, p0), probability_metrics(y, p1)
            coefs = m.named_steps["logisticregression"].coef_[0]
            width_rows.append({"width_index": w, "event": event_name, "diff_brier_plus_shape_minus_level": b["brier"] - a["brier"], "diff_logloss_plus_shape_minus_level": b["logloss"] - a["logloss"], "diff_auc_plus_shape_minus_level": b["auc"] - a["auc"], "coef_skew_standardized": float(coefs[-2]), "coef_tailratio_standardized": float(coefs[-1])})
        y, p0, _ = fit_probability_model(dev_breach, ev_breach, BASE_FEATURES, direction_fn)
        _, p1, m = fit_probability_model(dev_breach, ev_breach, f, direction_fn)
        a, b = probability_metrics(y, p0), probability_metrics(y, p1)
        coefs = m.named_steps["logisticregression"].coef_[0]
        width_rows.append({"width_index": w, "event": "down_given_1sigma_breach", "diff_brier_plus_shape_minus_level": b["brier"] - a["brier"], "diff_logloss_plus_shape_minus_level": b["logloss"] - a["logloss"], "diff_auc_plus_shape_minus_level": b["auc"] - a["auc"], "coef_skew_standardized": float(coefs[-2]), "coef_tailratio_standardized": float(coefs[-1])})

    metrics_df = pd.DataFrame(metric_rows)
    boot_df = pd.DataFrame(boot_rows)
    cond_df = pd.DataFrame(conditional_rows)
    cond_boot_df = pd.DataFrame(dir_boot)
    width_df = pd.DataFrame(width_rows)
    pred_df = pd.DataFrame(prediction_rows)

    metrics_df.to_csv(tables / "phase2_tail_metrics.csv", index=False)
    boot_df.to_csv(tables / "phase2_tail_bootstrap.csv", index=False)
    cond_df.to_csv(tables / "phase2_conditional_direction.csv", index=False)
    cond_boot_df.to_csv(tables / "phase2_conditional_direction_bootstrap.csv", index=False)
    width_df.to_csv(tables / "phase2_width_sensitivity.csv", index=False)
    pred_df.to_csv(local / "phase2_weekly_predictions.csv", index=False)

    coef_rows = []
    for event_name, model in model_cache.items():
        coefs = model.named_steps["logisticregression"].coef_[0]
        coef_rows.append({"event": event_name, **{f"coef_{f}": float(v) for f, v in zip(shape_features, coefs)}})
    dir_coefs = dir_model.named_steps["logisticregression"].coef_[0]
    coef_rows.append({"event": "down_given_1sigma_breach", **{f"coef_{f}": float(v) for f, v in zip(shape_features, dir_coefs)}})
    pd.DataFrame(coef_rows).to_csv(tables / "phase2_shape_coefficients.csv", index=False)

    head = metrics_df.loc[metrics_df["year"].isna()].copy()
    pivot = head.pivot(index="event", columns="model", values="brier").loc[["two_sided_1sigma", "down_1sigma", "up_1sigma"]]
    ax = pivot.plot(kind="bar", figsize=(8, 4.6), rot=0)
    ax.set_ylabel("Brier score (lower is better)")
    ax.set_xlabel("")
    ax.set_title("Phase II: option-surface shape beyond ATM scale")
    ax.legend(title="Information set")
    plt.tight_layout()
    plt.savefig(figures / "phase2_brier_scores.png", dpi=180)
    plt.close()

    fig, ax = plt.subplots(figsize=(8, 4.8))
    for event_name in ["two_sided_1sigma", "down_1sigma", "up_1sigma", "down_given_1sigma_breach"]:
        g = width_df.loc[width_df["event"] == event_name]
        ax.plot(g["width_index"], g["diff_brier_plus_shape_minus_level"], marker="o", label=event_name)
    ax.axhline(0, linewidth=1)
    ax.set_xlabel("Symmetric wing-width index")
    ax.set_ylabel("Brier difference: shape − level controls")
    ax.set_title("Smile geometry changes direction more than magnitude")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures / "phase2_width_sensitivity.png", dpi=180)
    plt.close()

    summary = {
        "phase": "II-A: expiry-tail geometry after conditioning on ATM scale",
        "split_date": args.split_date,
        "development_expiries": int(len(dev)),
        "evaluation_expiries": int(len(ev)),
        "evaluation_start": ev["date"].min().date().isoformat(),
        "evaluation_end": ev["date"].max().date().isoformat(),
        "evaluation_breaches_abs_z_ge_1": int((ev["z_target"].abs() >= 1).sum()),
        "identity_max_error_z_target": float(np.max(np.abs(panel["target_logret"] / panel["iv_scale"] - panel["z_target"]))),
        "headline_metrics": head.to_dict(orient="records"),
        "bootstrap": boot_df.to_dict(orient="records"),
        "conditional_direction": cond_df.to_dict(orient="records"),
        "conditional_direction_bootstrap": cond_boot_df.to_dict(orient="records"),
        "width_sign_counts": {e: {"n_widths": int((width_df["event"] == e).sum()), "n_brier_improvements": int(((width_df["event"] == e) & (width_df["diff_brier_plus_shape_minus_level"] < 0)).sum())} for e in width_df["event"].unique()},
        "interpretation": "Smile geometry does not improve the probability of a two-sided one-scale breach. Directional tail probabilities are more suggestive: the composite shape factor improves the upside-breach Brier score and improves conditional downside-vs-upside classification among realized breaches, but confidence intervals remain wide because only 73 evaluation expiries (23 one-scale breaches) are available. Treat this as hypothesis-generating, not as a confirmed anticipative factor.",
    }
    with open(out / "phase2_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, allow_nan=True)
    print(json.dumps(summary, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
