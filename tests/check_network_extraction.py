# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run the production network-extraction regression independently."""

import unittest
from pathlib import Path

suite = unittest.defaultTestLoader.discover(
    start_dir=str(Path(__file__).resolve().parent),
    pattern="test_postprocess.py",
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
