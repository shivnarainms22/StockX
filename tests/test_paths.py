from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import paths


class PathsTests(unittest.TestCase):
    def test_base_dir_is_module_dir_in_dev(self) -> None:
        self.assertFalse(getattr(sys, "frozen", False))
        self.assertEqual(paths.base_dir(), Path(paths.__file__).resolve().parent)

    def test_frozen_mode_uses_executable_dir(self) -> None:
        tmp = Path(tempfile.gettempdir()).resolve()
        exe = tmp / "StockX.exe"
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", str(exe)):
            self.assertEqual(paths.base_dir(), tmp)
            self.assertEqual(paths.dotenv_path(), tmp / ".env")
            self.assertEqual(paths.data_dir(), tmp / "data")

    def test_data_dir_is_created(self) -> None:
        self.assertTrue(paths.data_dir().exists())


if __name__ == "__main__":
    unittest.main()
