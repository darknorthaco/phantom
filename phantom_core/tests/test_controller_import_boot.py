"""
Controller import and in-process ``/health`` smoke (cross-platform).

Uses ``TestClient`` so no real port bind is required. Sets ``PHANTOM_STATE_DIR``
before ``TestClient`` triggers application startup.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_controller_import_and_health(monkeypatch, tmp_path):
    monkeypatch.setenv("PHANTOM_STATE_DIR", str(tmp_path))
    from phantom_core.controller_api import app

    assert app is not None
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "execution_mode" in data
    assert "workers_count" in data
