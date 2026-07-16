"""Tests for models list endpoint."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_models import router

app = FastAPI()
app.include_router(router, prefix="/api")

client = TestClient(app)


def test_models_returns_defaults():
    r = client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert data["default_model"] == "mobilevit"
    models = data["models"]
    names = [m["name"] for m in models]
    assert "mobilevit" in names
    assert "bisenetv2" in names


def test_models_thresholds():
    r = client.get("/api/models")
    models = {m["name"]: m for m in r.json()["models"]}
    assert models["mobilevit"]["fg_threshold"] == 0.65
    assert models["bisenetv2"]["fg_threshold"] == 0.50
