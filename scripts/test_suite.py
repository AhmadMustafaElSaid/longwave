"""Release checks require all media dependencies and zero skipped tests."""
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
suite = unittest.defaultTestLoader.discover(str(root / "companion/tests"))
results = unittest.TextTestRunner(verbosity=2).run(suite)
if not results.wasSuccessful() or results.skipped:
    raise SystemExit(1)
