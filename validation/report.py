"""StockX — live quant-correctness report.

Runs each deterministic engine on LIVE market data and cross-checks it against an
independent oracle (empyrical / closed-form mean-variance / statsmodels), then
prints a PASS/FAIL table. Loads the user's real portfolio from data/portfolio.json
when present.

Usage:
    python validation/report.py
    python validation/report.py --tickers AAPL,MSFT,NVDA,JNJ --period 2y

Requires the validate extras:  pip install -e ".[validate]"
Exits non-zero if any check FAILS (SKIPs do not fail the run).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Repo root on path so `services` / `paths` import when run as a script.
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__file__)))

import empyrical as ep  # noqa: E402
import statsmodels.api as sm  # noqa: E402

import paths  # noqa: E402

try:  # load .env so FRED/EIA keys are visible, same as the app does at startup
    from dotenv import load_dotenv
    load_dotenv(paths.dotenv_path())
except ImportError:
    pass

from services import perf_metrics as pm  # noqa: E402
from services.optimize import optimize_portfolio, fetch_returns  # noqa: E402
from services.factor_exposure import compute_factor_betas, fetch_factor_data  # noqa: E402
from services.backtest import run_backtest  # noqa: E402

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
_DEFAULT_BASKET = ["AAPL", "MSFT", "NVDA", "JNJ", "XOM"]


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _load_portfolio() -> list[dict]:
    f = paths.data_dir() / "portfolio.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
        return data if isinstance(data, list) else []
    except (ValueError, OSError):
        return []


# ── individual checks ─────────────────────────────────────────────────────────

def check_perf_metrics(period: str) -> list[Check]:
    import yfinance as yf
    out: list[Check] = []
    try:
        px = yf.Ticker("SPY").history(period=period, auto_adjust=True)["Close"]
        r = px.pct_change().dropna()
        if len(r) < 30:
            return [Check("perf_metrics vs empyrical", SKIP, "insufficient SPY data")]
    except Exception as e:  # noqa: BLE001 - network failure -> skip, never crash
        return [Check("perf_metrics vs empyrical", SKIP, f"fetch failed: {e}")]

    def cmp(name, mine, theirs, tol, rel=False):
        d = abs(mine - theirs)
        ref = d / (abs(theirs) + 1e-12) if rel else d
        ok = ref <= tol
        out.append(Check(f"perf: {name}", PASS if ok else FAIL,
                         f"stockx={mine:.6f} empyrical={theirs:.6f} d={d:.2e}"))

    cmp("sharpe", pm.sharpe(r), ep.sharpe_ratio(r), 1e-6)
    cmp("ann_vol", pm.annualized_vol(r), ep.annual_volatility(r), 1e-6)
    cmp("max_drawdown", pm.max_drawdown(px), ep.max_drawdown(r), 1e-6)
    cmp("cagr (period-count conv.)", pm.cagr(px), ep.annual_return(r), 3e-3)
    return out


def check_optimize(tickers: list[str], period: str) -> list[Check]:
    out: list[Check] = []
    try:
        rdf = fetch_returns(tickers, period=period)
    except Exception as e:  # noqa: BLE001
        return [Check("optimize vs closed-form", SKIP, f"fetch failed: {e}")]
    if rdf is None or rdf.shape[1] < 2 or len(rdf) < 30:
        return [Check("optimize vs closed-form", SKIP, "insufficient return data")]

    res = optimize_portfolio(rdf, rf=0.0)
    mu = rdf.mean().to_numpy() * 252
    cov = rdf.cov().to_numpy() * 252
    inv = np.linalg.inv(cov)
    ones = np.ones(len(mu))
    w_mv = inv @ ones / (ones @ inv @ ones)
    w_tan = inv @ mu / (ones @ inv @ mu)

    # Simplex validity (always holds for a long-only optimizer).
    for label, pt in (("min_var", res.min_var), ("max_sharpe", res.max_sharpe)):
        w = np.array(pt["weights"])
        ok = abs(w.sum() - 1.0) < 1e-6 and np.all(w >= -1e-9)
        out.append(Check(f"optimize: {label} simplex", PASS if ok else FAIL,
                         f"sum={w.sum():.6f} min_w={w.min():.4f}"))

    # Closed-form match only when the long-only constraint is non-binding.
    interior = np.all(w_mv > 0) and np.all(w_tan > 0)
    if interior:
        for label, w_ref, pt in (("min_var", w_mv, res.min_var),
                                 ("max_sharpe", w_tan, res.max_sharpe)):
            d = float(np.max(np.abs(np.array(pt["weights"]) - w_ref)))
            out.append(Check(f"optimize: {label} vs closed-form",
                             PASS if d < 1e-3 else FAIL, f"max|dw|={d:.2e}"))
    else:
        # Constraint binds on this real data: verify tangency optimality instead.
        best = res.max_sharpe["sharpe"]
        beaten = any((rr / vv if vv > 0 else 0) > best + 1e-6
                     for vv, rr in zip(res.frontier_vol, res.frontier_ret))
        out.append(Check("optimize: tangency optimality (long-only binds)",
                         FAIL if beaten else PASS,
                         "no frontier point beats max-Sharpe" if not beaten
                         else "a frontier point beats max-Sharpe"))
    return out


def check_factor_exposure(portfolio: list[dict], period: str) -> list[Check]:
    if not portfolio:
        return [Check("factor betas vs statsmodels", SKIP, "no saved portfolio")]
    try:
        port_r, factor_df = fetch_factor_data(portfolio, period=period)
    except Exception as e:  # noqa: BLE001
        return [Check("factor betas vs statsmodels", SKIP, f"fetch failed: {e}")]
    if port_r is None or factor_df is None:
        return [Check("factor betas vs statsmodels", SKIP, "insufficient factor data")]

    out = compute_factor_betas(port_r, factor_df)
    X = sm.add_constant(factor_df.to_numpy())
    sm_res = sm.OLS(port_r.to_numpy(), X).fit()
    mine = np.array([out["betas"][c] for c in factor_df.columns])
    d_beta = float(np.max(np.abs(mine - sm_res.params[1:])))
    d_r2 = abs(out["r_squared"] - sm_res.rsquared)
    ok = d_beta < 1e-4 and d_r2 < 1e-4
    return [Check("factor betas vs statsmodels", PASS if ok else FAIL,
                  f"max_dbeta={d_beta:.2e} dR2={d_r2:.2e} R2={out['r_squared']:.3f}")]


def check_recession_probit() -> list[Check]:
    from services.yield_curve import recession_probability, _add_months
    from services.research import fetch_fred_series
    try:
        model = recession_probability()
    except Exception as e:  # noqa: BLE001
        return [Check("recession probit vs statsmodels", SKIP, f"FRED error: {e}")]
    if not model:
        return [Check("recession probit vs statsmodels", SKIP,
                      "no FRED_API_KEY or insufficient data")]

    p = model["probability"]
    sane = 0.0 <= p <= 1.0
    checks = [Check("recession probit: probability in [0,1]",
                    PASS if sane else FAIL, f"P={p:.3f} spread={model['spread']:.2f}")]

    # Independent statsmodels refit on the same FRED series.
    try:
        spread_obs = fetch_fred_series("T10Y3M", limit=700, frequency="m")
        rec_obs = fetch_fred_series("USREC", limit=900, frequency="m")
        spread = {o["date"][:7]: float(o["value"]) for o in spread_obs}
        rec = {o["date"][:7]: float(o["value"]) for o in rec_obs}
        X, Y = [], []
        for m in sorted(spread):
            fut = _add_months(m, 12)
            if fut in rec:
                X.append(spread[m]); Y.append(rec[fut])
        res = sm.Probit(np.array(Y), sm.add_constant(np.array(X))).fit(disp=0)
        b0, b1 = model["coef"]
        d = max(abs(b0 - res.params[0]), abs(b1 - res.params[1]))
        checks.append(Check("recession probit: coef vs statsmodels",
                            PASS if d < 0.05 else FAIL,
                            f"stockx=({b0:.3f},{b1:.3f}) sm=({res.params[0]:.3f},{res.params[1]:.3f})"))
    except Exception as e:  # noqa: BLE001
        checks.append(Check("recession probit: coef vs statsmodels", SKIP, str(e)))
    return checks


def check_backtest_lookahead(ticker: str, period: str) -> list[Check]:
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        prices = hist[["Close"]].dropna()
        if len(prices) < 60:
            return [Check("backtest lookahead-safety", SKIP, "insufficient data")]
    except Exception as e:  # noqa: BLE001
        return [Check("backtest lookahead-safety", SKIP, f"fetch failed: {e}")]

    ar = prices["Close"].pct_change().fillna(0.0)
    peek = (ar > 0).astype(float)
    cheat_sharpe = pm.sharpe(peek * ar)
    res = run_backtest(prices, lambda p: peek, commission_bps=0.0, slippage_bps=0.0)
    eng = res.metrics["sharpe"]
    safe = eng < cheat_sharpe / 3 and cheat_sharpe > 5.0
    expected_held = peek.shift(1).fillna(0.0)
    max_dev = float((res.positions - expected_held).abs().max())
    shift_ok = max_dev < 1e-12
    return [
        Check("backtest: same-bar peek neutralized", PASS if safe else FAIL,
              f"cheat_sharpe={cheat_sharpe:.2f} engine_sharpe={eng:.2f}"),
        Check("backtest: held == prior-bar signal", PASS if shift_ok else FAIL,
              f"max|held - target.shift(1)|={max_dev:.1e}"),
    ]


# ── driver ──────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="StockX live quant-correctness report")
    ap.add_argument("--tickers", help="comma-separated tickers for the optimizer "
                                       "(default: your portfolio or a sample basket)")
    ap.add_argument("--period", default="2y", help="yfinance history period (default 2y)")
    args = ap.parse_args(argv)

    portfolio = _load_portfolio()
    if args.tickers:
        opt_tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif portfolio:
        opt_tickers = [h["ticker"] for h in portfolio]
    else:
        opt_tickers = _DEFAULT_BASKET

    print("=" * 78)
    print("StockX - Live Quant Correctness Report")
    print(f"portfolio holdings: {len(portfolio)}   optimizer tickers: {opt_tickers}")
    print("=" * 78)

    checks: list[Check] = []
    checks += check_perf_metrics(args.period)
    checks += check_optimize(opt_tickers, args.period)
    checks += check_factor_exposure(portfolio, args.period)
    checks += check_recession_probit()
    checks += check_backtest_lookahead("AAPL", args.period)

    width = max(len(c.name) for c in checks)
    for c in checks:
        print(f"  {c.status:4}  {c.name:<{width}}  {c.detail}")

    n_pass = sum(c.status == PASS for c in checks)
    n_fail = sum(c.status == FAIL for c in checks)
    n_skip = sum(c.status == SKIP for c in checks)
    print("-" * 78)
    print(f"  {n_pass} passed, {n_fail} failed, {n_skip} skipped "
          f"of {len(checks)} checks")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
