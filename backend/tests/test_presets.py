"""Tests for presets CRUD endpoints."""
import tempfile
import os

# Set DATABASE_URL to temp file BEFORE importing app modules
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.database import init_db
from app.api.routes_presets import router

app = FastAPI()
app.include_router(router, prefix="/api")
init_db()

client = TestClient(app)

_PRESET = {
    "name": "test_preset",
    "roi_json": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    "threshold": 0.65,
}


def test_create_preset():
    r = client.post("/api/presets", json=_PRESET)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "test_preset"
    assert data["model"] == "mobilevit"
    assert data["stride"] == 3


def test_list_presets():
    r = client.get("/api/presets")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_get_preset():
    r = client.get("/api/presets/1")
    assert r.status_code == 200
    assert r.json()["name"] == "test_preset"


def test_update_preset():
    r = client.put("/api/presets/1", json={"threshold": 0.75})
    assert r.status_code == 200
    assert r.json()["threshold"] == 0.75


def test_get_after_update():
    r = client.get("/api/presets/1")
    assert r.json()["threshold"] == 0.75


def test_delete_preset():
    r = client.delete("/api/presets/1")
    assert r.status_code == 204


def test_get_deleted_404():
    r = client.get("/api/presets/1")
    assert r.status_code == 404
