import pytest
from app.services.signal_engine import SignalEngine
from app.services.ict_engine import ICTEngine

engine = SignalEngine()
ict_engine = ICTEngine()

def test_signal_with_strong_bias():
    # Strong bullish: 1+1+1+1+0 = 4
    result = engine.evaluate_signals({'symbol': 'EURUSD', 'bias': 'BULLISH'}, ['FVG'], 1.001, 0.999, 1.002)
    assert result['score'] >= 4
    assert result['signal'] == 'BUY'
    assert 'quality' in result

def test_signal_with_bearish_bias():
    result = engine.evaluate_signals({'symbol': 'EURUSD', 'bias': 'BEARISH'}, ['FVG'], 0.999, 1.001, 0.998)
    assert result['score'] >= 4
    assert result['signal'] == 'SELL'

def test_signal_below_threshold():
    # Neutral bias with no patterns = 0
    result = engine.evaluate_signals({'symbol': 'EURUSD', 'bias': 'NEUTRAL'}, [], 1.0, 1.0, 1.0)
    assert result['score'] < 2
    assert result['signal'] is None

def test_signal_quality_ratings():
    result = engine.evaluate_signals({'symbol': 'EURUSD', 'bias': 'BULLISH'}, ['FVG'], 1.001, 0.999, 1.002)
    assert result['quality'] in ['STRONG', 'MODERATE', 'WEAK', 'NONE']
    assert 'breakdown' in result

def test_ict_engine_entry_zone():
    patterns = [{
        'type': 'FVG',
        'direction': 'bullish',
        'price_level': 1.1000,
        'metadata': {'top': 1.1005, 'bottom': 1.0995}
    }]
    entry = ict_engine.calculate_entry(patterns, 'BULLISH', 1.1000)
    assert entry is not None
    assert 'entry' in entry
    assert 'sl' in entry
    assert 'tp1' in entry
    assert entry['sl'] < entry['entry']
    assert entry['tp1'] > entry['entry']

def test_ict_engine_ob_metadata():
    patterns = [{
        'type': 'OB',
        'direction': 'bearish',
        'price_level': 1.2000,
        'metadata': {'ob_high': 1.2005, 'ob_low': 1.1995}
    }]
    entry = ict_engine.calculate_entry(patterns, 'BEARISH', 1.2000)
    assert entry is not None
    assert entry['sl'] > entry['entry']
    assert entry['tp1'] < entry['entry']
