"""Pytest configuration.

Ensure `backend/` is importable AND that the whole suite uses a throwaway
SQLite DB + data dir. These env vars are set BEFORE any `app` import so the
DB engine (created at import time) binds to the temp database, regardless of
test collection order.
"""
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP_DATA = Path(tempfile.mkdtemp(prefix="shaker_test_"))
os.environ["DATA_DIR"] = str(_TMP_DATA)
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DATA / 'test.db').as_posix()}"
