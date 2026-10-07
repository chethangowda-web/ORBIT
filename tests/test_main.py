"""
Tests for ORBIT base endpoints
"""

import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns status ok."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ORBIT"
    assert "version" in data


def test_health_endpoint():
    """Verify health endpoint returns status healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
