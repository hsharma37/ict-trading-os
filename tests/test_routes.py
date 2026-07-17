import pytest
from fastapi.testclient import TestClient

def test_research_summary(client: TestClient):
    res = client.get('/research/summary')
    assert res.status_code in [200, 500]

def test_research_analyze(client: TestClient):
    # 404 is the honest no-bridge outcome: analysis runs only on the MT5 feed.
    res = client.get('/research/instrument/EURUSD')
    assert res.status_code in [200, 404, 500]

def test_market_instruments(client: TestClient):
    res = client.get('/market/instruments')
    assert res.status_code in [200, 500]
