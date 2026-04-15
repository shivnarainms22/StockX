from __future__ import annotations

import unittest
from unittest.mock import patch

from services.consumer_inflation import estimate_consumer_inflation_nowcast


class ConsumerInflationModelTests(unittest.TestCase):
    def test_positive_oil_shock_increases_us_pressure(self) -> None:
        data = {
            "CL=F": {"delta_1m": 8.0, "vol_1m": 2.0},
            "NG=F": {"delta_1m": 0.7, "vol_1m": 3.0},
            "ZW=F": {"delta_1m": 0.4, "vol_1m": 2.0},
            "ZC=F": {"delta_1m": 0.2, "vol_1m": 2.0},
        }
        fake_cal = {
            "US": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {}},
            "EU": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {}},
            "India": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {}},
            "China": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {}},
        }
        with patch("services.consumer_inflation._get_calibration", return_value=fake_cal):
            out = estimate_consumer_inflation_nowcast(data)

        self.assertIn("US", out)
        self.assertGreater(out["US"]["h3_pp"], 0.0)
        self.assertGreaterEqual(out["US"]["confidence"], 0.20)
        self.assertLessEqual(out["US"]["confidence"], 0.94)

    def test_negative_energy_shock_reduces_pressure(self) -> None:
        data = {
            "CL=F": {"delta_1m": -9.0, "vol_1m": 3.0},
            "NG=F": {"delta_1m": -0.9, "vol_1m": 4.0},
            "HO=F": {"delta_1m": -0.6, "vol_1m": 3.0},
        }
        fake_cal = {
            "US": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
            "EU": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
            "India": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
            "China": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
        }
        with patch("services.consumer_inflation._get_calibration", return_value=fake_cal):
            out = estimate_consumer_inflation_nowcast(data)

        self.assertLess(out["US"]["h1_pp"], 0.0)
        self.assertLess(out["EU"]["h3_pp"], 0.0)

    def test_extended_payload_includes_aggregate_and_quality(self) -> None:
        data = {
            "CL=F": {"delta_1m": 5.0, "vol_1m": 2.0, "pct_1d": 1.2, "fetched_ts": 1e12},
            "NG=F": {"delta_1m": 0.6, "vol_1m": 2.8, "pct_1d": 0.5, "fetched_ts": 1e12},
            "ZW=F": {"delta_1m": 0.3, "vol_1m": 1.9, "pct_1d": 0.8, "fetched_ts": 1e12},
            "ZC=F": {"delta_1m": 0.2, "vol_1m": 2.1, "pct_1d": 0.9, "fetched_ts": 1e12},
            "ZS=F": {"delta_1m": 0.1, "vol_1m": 2.0, "pct_1d": 0.4, "fetched_ts": 1e12},
            "HO=F": {"delta_1m": 0.7, "vol_1m": 2.2, "pct_1d": 0.7, "fetched_ts": 1e12},
        }
        fake_cal = {
            "US": {"scale": 1.1, "r2": 0.5, "auto_factor": 0.95, "tracker": {"samples": 20, "mae_pp": 0.2, "hit_rate": 0.7}},
            "EU": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {"samples": 20, "mae_pp": 0.2, "hit_rate": 0.7}},
            "India": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {"samples": 20, "mae_pp": 0.2, "hit_rate": 0.7}},
            "China": {"scale": 1.0, "r2": 0.4, "auto_factor": 1.0, "tracker": {"samples": 20, "mae_pp": 0.2, "hit_rate": 0.7}},
        }
        with patch("services.consumer_inflation._get_calibration", return_value=fake_cal):
            out = estimate_consumer_inflation_nowcast(data)

        self.assertIn("aggregate", out)
        self.assertIn("regions", out)
        self.assertIn("data_quality", out)
        self.assertIn("consumer_pressure_index", out["aggregate"])
        self.assertIn("data_quality", out["US"])
        self.assertIn(out["data_quality"]["badge"], {"good", "caution", "poor"})

    def test_portfolio_and_hedge_payload(self) -> None:
        data = {"CL=F": {"delta_1m": 2.0, "vol_1m": 2.0, "pct_1d": 0.1}}
        fake_cal = {
            "US": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
            "EU": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
            "India": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
            "China": {"scale": 1.0, "r2": None, "auto_factor": 1.0, "tracker": {}},
        }
        fake_port = {
            "score": 66,
            "regime": "inflation-sensitive",
            "beta": 0.55,
            "top_contributors": ["AAPL: weight 20.0% x beta +0.50 = +0.100"],
            "sample_months": 24,
            "hedge_candidates": [
                {"symbol": "TIP", "name": "US TIPS ETF", "direction": "long", "hedge_ratio": 0.4, "estimated_risk_reduction_pct": 12.0}
            ],
        }
        portfolio = [{"ticker": "AAPL", "qty": 10, "avg_cost": 100}]
        with patch("services.consumer_inflation._get_calibration", return_value=fake_cal):
            with patch("services.consumer_inflation._compute_portfolio_exposure", return_value=fake_port):
                out = estimate_consumer_inflation_nowcast(data, portfolio=portfolio)

        self.assertIsNotNone(out.get("portfolio_exposure"))
        self.assertIsNotNone(out.get("hedge_assistant"))
        self.assertEqual(out["portfolio_exposure"]["score"], 66)
        self.assertTrue(out["hedge_assistant"]["candidates"])


if __name__ == "__main__":
    unittest.main()
