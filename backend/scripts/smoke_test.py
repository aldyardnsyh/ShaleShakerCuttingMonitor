"""End-to-end smoke test (Task 12).

Exercises the integrated stack in-process via Starlette TestClient:
static frontend serving + health + models + full session pipeline on the
REAL test video. Uses a throwaway DB + data dir.

Run: backend/.venv/Scripts/python scripts/smoke_test.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Throwaway data dir + DB BEFORE importing the app.
_tmp = Path(tempfile.mkdtemp(prefix="shaker_smoke_"))
os.environ["DATA_DIR"] = str(_tmp)
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'smoke.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.workers.processor import session_video_path  # noqa: E402

init_db()

REAL_VIDEO = Path(r"D:/Kuliah/Tugas Akhir/Dataset/Kode Uji Coba Test Video/dataset_asli_pdu_2.mp4")
ROI = [[760, 650], [1300, 614], [1315, 795], [780, 845]]

ok = 0
fail = 0


def check(name: str, cond: bool, extra: str = ""):
    global ok, fail
    mark = "PASS" if cond else "FAIL"
    if cond:
        ok += 1
    else:
        fail += 1
    print(f"  [{mark}] {name} {extra}")


def main():
    client = TestClient(app)

    # 1. health
    r = client.get("/api/health")
    check("GET /api/health", r.status_code == 200 and r.json()["status"] == "healthy")

    # 2. static frontend index
    r = client.get("/")
    served = r.status_code == 200 and ("<html" in r.text.lower() or "<!doctype html" in r.text.lower())
    check("GET / (static index)", served, f"(status={r.status_code})")

    # 3. models
    r = client.get("/api/models")
    names = {m["name"] for m in r.json().get("models", [])} if r.status_code == 200 else set()
    check("GET /api/models", {"mobilevit", "bisenetv2"}.issubset(names), f"-> {sorted(names)}")

    # 4. create session
    r = client.post("/api/sessions", json={
        "name": "smoke", "model": "bisenetv2", "threshold": 0.5, "roi_json": ROI, "stride": 10,
    })
    check("POST /api/sessions", r.status_code == 201)
    sid = r.json()["id"]

    # 5. provide the real video (copy to the session path; equivalent to upload)
    if REAL_VIDEO.exists():
        shutil.copyfile(REAL_VIDEO, session_video_path(sid))
        have_video = True
    else:
        have_video = False
        print(f"  [WARN] real video not found at {REAL_VIDEO}; skipping processing")

    if have_video:
        # 6. process a few frames
        r = client.post(f"/api/sessions/{sid}/process", params={"max_frames": 5})
        body = r.json() if r.status_code == 200 else {}
        check("POST /process (5 frames, real video)", r.status_code == 200 and body.get("frames_processed") == 5,
              f"-> {body}")

        # 7. measurements persisted
        r = client.get(f"/api/sessions/{sid}/measurements")
        rows = r.json() if r.status_code == 200 else []
        valid = len(rows) == 5 and all(0.0 <= m["fg_area_pct"] <= 100.0 for m in rows)
        check("GET /measurements", valid, f"-> {len(rows)} rows; sample pct={rows[0]['fg_area_pct'] if rows else 'NA'}")

        # 8. CSV export
        r = client.get(f"/api/sessions/{sid}/export.csv")
        check("GET /export.csv", r.status_code == 200 and r.text.splitlines()[0].startswith("frame_idx"))

    print(f"\nSMOKE RESULT: {ok} passed, {fail} failed")
    print(f"(temp data dir: {settings.DATA_DIR})")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
