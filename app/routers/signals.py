"""Signals Router."""
from fastapi import APIRouter
from app.services.signal_engine import signal_engine
from app.services.mt5_trades_service import mt5_trades_service

router = APIRouter(prefix="/signals", tags=["Signals"])


def _held_map() -> dict:
    """symbol -> live MT5 position (so signals can flag existing exposure)."""
    if not mt5_trades_service.is_active():
        return {}
    return {p["symbol"]: p for p in mt5_trades_service.get_open_trades()}


def _annotate(signal: dict, held: dict) -> dict:
    """Tag a signal with the user's current live exposure in that symbol."""
    if not signal:
        return signal
    pos = held.get(signal.get("symbol"))
    signal["held"] = bool(pos)
    signal["held_direction"] = pos.get("direction") if pos else None
    return signal


@router.get("/analyze/{symbol}")
def analyze_signal(symbol: str, target_r: float = 2.0):
    """Direction from the fused Signal Intelligence read, scored by the ICT
    confluence checklist. `target_r` sets the reward:risk of the proposed targets."""
    target_r = max(0.5, min(float(target_r), 10.0))
    signal = signal_engine.analyze(symbol, target_r=target_r)
    if not signal:
        return {"symbol": symbol, "signal": None, "message": "No valid signal. Setup below confluence threshold."}
    return {"symbol": symbol, "signal": _annotate(signal, _held_map())}

@router.get("/active")
def active_signals(symbol: str = None):
    held = _held_map()
    signals = [_annotate(s, held) for s in signal_engine.get_active(symbol)]
    return {"signals": signals, "count": len(signals)}

@router.get("/stats/{symbol}")
def signal_stats(symbol: str):
    return signal_engine.get_stats(symbol)

@router.post("/scan")
def scan_all(target_r: float = 2.0):
    from app.services.instrument_config import get_all_instruments
    target_r = max(0.5, min(float(target_r), 10.0))
    symbols = list(get_all_instruments().keys())
    held = _held_map()
    results = []
    for sym in symbols:
        sig = signal_engine.analyze(sym, target_r=target_r)
        if sig: results.append(_annotate(sig, held))
    return {"scanned": len(symbols), "signals_found": len(results), "signals": results}


@router.get("/intelligence/{symbol}", summary="News+technical+ICT fused signal")
def intelligence(symbol: str):
    """A reasoned signal for one instrument: news sentiment fused with technicals
    and ICT knowledge, with factor breakdown, reasoning, and suggestions."""
    from app.services.signal_intelligence import signal_intelligence
    return signal_intelligence.generate(symbol)


@router.get("/intelligence", summary="Fused signals for all supported instruments")
def intelligence_all():
    from app.services.instrument_config import get_all_instruments
    from app.services.signal_intelligence import signal_intelligence
    signals = [signal_intelligence.generate(sym) for sym in get_all_instruments()]
    # Strongest conviction first.
    signals.sort(key=lambda s: s.get("confidence_score", 0), reverse=True)
    return {"signals": signals, "count": len(signals)}
