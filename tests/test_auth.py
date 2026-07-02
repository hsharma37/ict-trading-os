import pytest
from fastapi.testclient import TestClient
import os

from app.main import app

def test_health_no_auth(client: TestClient):
    res = client.get('/health')
    assert res.status_code == 200
    data = res.json()
    assert 'status' in data

def test_docs_no_auth(client: TestClient):
    res = client.get('/docs')
    assert res.status_code == 200

def test_settings_without_auth(client: TestClient):
    res = client.get('/settings')
    # With no auth and AUTH_ENABLED=false, should succeed
    assert res.status_code in [200, 404]
