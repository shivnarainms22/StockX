from __future__ import annotations
import os
import unittest
from unittest.mock import MagicMock, patch

import services.research as research


class FetchFredSeriesTests(unittest.TestCase):
    def test_returns_most_recent_observations_in_ascending_order(self) -> None:
        # FRED returns newest-first under sort_order=desc; we must return ascending.
        payload = {"observations": [
            {"date": "2025-03-01", "value": "3"},
            {"date": "2025-02-01", "value": "2"},
            {"date": "2025-01-01", "value": "1"},
        ]}
        resp = MagicMock(status_code=200)
        resp.json.return_value = payload
        with patch.dict(os.environ, {"FRED_API_KEY": "x"}, clear=False), \
                patch("httpx.get", return_value=resp) as get:
            out = research.fetch_fred_series("X", limit=3, frequency="m")
        self.assertEqual([o["date"] for o in out],
                         ["2025-01-01", "2025-02-01", "2025-03-01"])
        # Must request descending so `limit` selects newest, not oldest.
        self.assertEqual(get.call_args.kwargs["params"]["sort_order"], "desc")

    def test_drops_missing_values_and_returns_empty_without_key(self) -> None:
        payload = {"observations": [
            {"date": "2025-02-01", "value": "."},
            {"date": "2025-01-01", "value": "1"},
        ]}
        resp = MagicMock(status_code=200)
        resp.json.return_value = payload
        with patch.dict(os.environ, {"FRED_API_KEY": "x"}, clear=False), \
                patch("httpx.get", return_value=resp):
            out = research.fetch_fred_series("X")
        self.assertEqual([o["value"] for o in out], ["1"])

        with patch.dict(os.environ, {"FRED_API_KEY": ""}, clear=False):
            self.assertEqual(research.fetch_fred_series("X"), [])


if __name__ == "__main__":
    unittest.main()
