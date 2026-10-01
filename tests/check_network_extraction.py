"""Run the production network-extraction regression independently."""
from pathlib import Path
import unittest

suite = unittest.defaultTestLoader.discover(
    start_dir=str(Path(__file__).resolve().parent),
    pattern='test_postprocess.py',
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
