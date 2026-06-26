#!/usr/bin/env python3
"""Thin redirect to the canonical v2 ingest in backend/."""
import sys
from pathlib import Path

_backend_ingest = Path(__file__).resolve().parent / "backend" / "rnp_ingest_pg.py"
if not _backend_ingest.exists():
    print("Error: backend/rnp_ingest_pg.py not found", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    import runpy
    runpy.run_path(str(_backend_ingest), run_name="__main__")
