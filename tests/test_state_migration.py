from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from gui.state import AppState


class AppStateMigrationTests(unittest.TestCase):
    def _make_data_dir(self) -> Path:
        temp_root = Path("data") / "_test_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        data_dir = temp_root / str(uuid.uuid4())
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def test_legacy_watchlist_migrates_with_new_alert_fields(self) -> None:
        data_dir = self._make_data_dir()
        try:
            legacy = [
                {"ticker": "aapl", "price_above": 200},
                {"ticker": "TSLA", "rsi_below": 30},
            ]
            (data_dir / "watchlist.json").write_text(json.dumps(legacy), encoding="utf-8")

            with patch("gui.state._DATA_DIR", data_dir):
                state = AppState()
                state.load_watchlist()

                self.assertEqual(len(state.watchlist), 2)
                for row in state.watchlist:
                    self.assertIn("alert_cooldown_minutes", row)
                    self.assertIn("min_confidence", row)
                    self.assertGreaterEqual(row["alert_cooldown_minutes"], 1)
                    self.assertGreaterEqual(row["min_confidence"], 0.0)
                    self.assertLessEqual(row["min_confidence"], 1.0)
                    self.assertEqual(row["ticker"], row["ticker"].upper())

                state.save_watchlist()
                saved = json.loads((data_dir / "watchlist.json").read_text(encoding="utf-8"))
                self.assertIn("_schema_version", saved)
                self.assertIn("data", saved)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_load_uses_backup_when_primary_is_corrupt(self) -> None:
        data_dir = self._make_data_dir()
        try:
            primary = data_dir / "watchlist.json"
            backup = data_dir / "watchlist.json.bak"

            primary.write_text("{not-valid-json", encoding="utf-8")
            backup_payload = {
                "_schema_version": 2,
                "data": [{"ticker": "MSFT", "price_below": 350, "alert_cooldown_minutes": 15, "min_confidence": 0.6}],
            }
            backup.write_text(json.dumps(backup_payload), encoding="utf-8")

            with patch("gui.state._DATA_DIR", data_dir):
                state = AppState()
                state.load_watchlist()
                self.assertEqual(len(state.watchlist), 1)
                self.assertEqual(state.watchlist[0]["ticker"], "MSFT")

                # Primary should be repaired from backup.
                repaired = json.loads(primary.read_text(encoding="utf-8"))
                self.assertIn("data", repaired)
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
