"""Test bootstrap: make backend/ importable and satisfy required settings.

Settings has two fields without defaults (jwt secret, internal token), and
core.database builds its engine at import time from settings — so harmless
dummies must exist BEFORE any application import. No test in this suite
touches the network or a database.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AQUASIGNAL_JWT_SECRET_KEY", "test-only-secret")
os.environ.setdefault("AQUASIGNAL_INTERNAL_API_TOKEN", "test-only-token")
