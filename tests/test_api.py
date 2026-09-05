"""Tests for the FastAPI endpoints."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_data(client):
    response = client.post("/generate-data")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data or "success" in data


def test_reconcile_endpoint(client):
    # Generate data first
    client.post("/generate-data")
    response = client.post("/reconcile")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "metrics" in data
    assert "results" in data


def test_metrics_endpoint(client):
    # Run reconciliation first
    client.post("/generate-data")
    client.post("/reconcile")
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_records" in data
    assert "match_rate" in data


def test_transactions_endpoint(client):
    client.post("/generate-data")
    client.post("/reconcile")
    response = client.get("/transactions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_exceptions_endpoint(client):
    client.post("/generate-data")
    client.post("/reconcile")
    response = client.get("/exceptions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
