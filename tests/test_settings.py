import pytest
from fastapi.testclient import TestClient

def test_settings_crud(client: TestClient):
    # GET default settings
    res = client.get('/settings')
    assert res.status_code == 200
    data = res.json()
    assert 'theme' in data
    
    # UPDATE settings
    res = client.post('/settings', json={'theme': 'light', 'risk_pct': 2.0})
    assert res.status_code == 200
    data = res.json()
    assert data['theme'] == 'light'
    assert data['risk_pct'] == 2.0
    
    # Verify persistence
    res = client.get('/settings')
    assert res.json()['theme'] == 'light'
