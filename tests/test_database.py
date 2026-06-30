import pytest
from app.core.database import db

def test_db_insert_and_find():
    db.insert('test_signals', {'id': 'sig1', 'symbol': 'EURUSD', 'score': 3})
    docs = db.find('test_signals', symbol='EURUSD')
    assert len(docs) >= 1
    assert any(d['symbol'] == 'EURUSD' for d in docs)

def test_db_find_one():
    db.insert('test_settings', {'id': 'global', 'theme': 'dark'})
    doc = db.find_one('test_settings', 'global')
    assert doc is not None
    assert doc['theme'] == 'dark'

def test_db_update():
    db.insert('test_settings', {'id': 'global', 'theme': 'dark'})
    db.update('test_settings', 'global', {'theme': 'light'})
    doc = db.find_one('test_settings', 'global')
    assert doc['theme'] == 'light'

def test_db_stats():
    stats = db.get_stats()
    assert 'tables' in stats
