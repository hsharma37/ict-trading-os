import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from app.core.database import db

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    yield
    # Cleanup all test data between runs
    for collection in ['test_settings', 'test_signals']:
        try:
            for doc in db.find(collection):
                db.delete(collection, doc.get('id', doc.get('_id')))
        except:
            pass
