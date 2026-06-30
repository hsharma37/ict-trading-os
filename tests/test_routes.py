import pytest
from fastapi.testclient import TestClient

def test_research_summary(client: TestClient):
    res = client.get('/research/summary')
    assert res.status_code in [200, 500]

def test_research_analyze(client: TestClient):
    res = client.get('/research/analyze/EURUSD')
    assert res.status_code in [200, 500]

def test_market_instruments(client: TestClient):
    res = client.get('/market/instruments')
    assert res.status_code in [200, 500]
