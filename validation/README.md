# Quant Correctness Validation

Independent verification that StockX's deterministic quant engines produce
*correct* numbers — not plausible-looking slop. Each engine is cross-checked
against a trusted external oracle, on both fixed fixtures and live market data.

| Engine | Oracle | Verdict |
|---|---|---|
| `services/perf_metrics` (Sharpe, vol, max DD, beta) | `empyrical` | exact match |
| `services/perf_metrics` (CAGR, Calmar) | `empyrical` | match within a documented period-count convention (~0.2%) |
| `services/perf_metrics` (Sortino, alpha) | own definition | StockX uses sample-downside-std / arithmetic alpha — **differs from empyrical by design**, see test comments |
| `services/optimize` (max-Sharpe, min-var) | closed-form `S^-1 mu` / `S^-1 1` | exact match where long-only is non-binding |
| `services/yield_curve` (recession probit) | `statsmodels.Probit` | coefficients match |
| `services/factor_exposure` (OLS betas, R^2) | `statsmodels.OLS` | match to machine precision |
| `services/backtest` | adversarial lookahead probe | future-peeking is provably neutralized |

## Install

```bash
pip install -e ".[validate]"     # adds empyrical-reloaded + statsmodels (dev-only)
```

## Offline reference tests (hermetic, reproducible)

```bash
pytest tests/validation/
```

Run on a committed real SPY price fixture (`tests/validation/fixtures/spy_prices.csv`)
plus seeded synthetic data. No network. They skip cleanly if the `[validate]`
extras are not installed, so the base test suite is unaffected.

## Live report (your real portfolio + live data)

```bash
python validation/report.py
python validation/report.py --tickers AAPL,MSFT,NVDA,JNJ --period 2y
```

Pulls live data, loads your real holdings from `data/portfolio.json`, runs every
cross-check, and prints a PASS / FAIL / SKIP table. Exits non-zero if any check
FAILs (network-unavailable checks SKIP, they don't fail the run). The recession
probit check needs `FRED_API_KEY` in `.env`; without it that check SKIPs.

## Honest findings (read these)

- **Sortino** — StockX divides by the sample std (ddof=1) of only-negative excess
  returns. empyrical uses target semideviation (RMS of `min(r,0)` over all
  periods). The two differ ~14% on real SPY data. Both are defensible; StockX's
  choice is documented and validated against its own definition.
- **CAGR / Calmar** — StockX counts `len(equity)` periods; empyrical counts
  `len(returns) = len(equity) - 1`. ~0.2% gap at n=500. Internally consistent.
- **alpha** — StockX annualizes arithmetically (`mean * 252`); empyrical
  annualizes geometrically.

These are *conventions*, not bugs — but they are real differences, surfaced here
rather than hidden behind an inflated tolerance.
