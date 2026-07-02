from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.core.database import db
from app.services.quant_service import quant_service
from app.services.trade_lifecycle_service import trade_lifecycle_service


def parse_utc(value: str):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    return parsed


def create_trade(**overrides):
    payload = {
        "symbol": "EURUSD",
        "side": "BUY",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit_1": 1.1050,
        "take_profit_2": 1.1100,
        "take_profit_3": 1.1150,
        "quantity": 1.0,
        "account_balance": 10000,
        "risk_pct": 1,
    }
    payload.update(overrides)
    trade = trade_lifecycle_service.create_trade(**payload)
    assert "error" not in trade, trade
    return trade


def test_buy_and_sell_stop_loss_validation():
    assert "error" not in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="BUY", entry_price=1.1000, stop_loss=1.0950, quantity=1
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="BUY", entry_price=1.1000, stop_loss=1.1000, quantity=1
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="BUY", entry_price=1.1000, stop_loss=1.1050, quantity=1
    )

    assert "error" not in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="SELL", entry_price=1.1000, stop_loss=1.1050, quantity=1
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="SELL", entry_price=1.1000, stop_loss=1.1000, quantity=1
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="SELL", entry_price=1.1000, stop_loss=1.0950, quantity=1
    )


def test_take_profit_direction_and_sequence_validation():
    assert "error" not in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="BUY", entry_price=1.1000, stop_loss=1.0950,
        take_profit_1=1.1050, take_profit_2=1.1100, quantity=1,
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="BUY", entry_price=1.1000, stop_loss=1.0950,
        take_profit_1=1.1050, take_profit_2=1.1040, quantity=1,
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="BUY", entry_price=1.1000, stop_loss=1.0950,
        take_profit_1=1.0990, quantity=1,
    )

    assert "error" not in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="SELL", entry_price=1.1000, stop_loss=1.1050,
        take_profit_1=1.0950, take_profit_2=1.0900, quantity=1,
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="SELL", entry_price=1.1000, stop_loss=1.1050,
        take_profit_1=1.0950, take_profit_2=1.0960, quantity=1,
    )
    assert "error" in trade_lifecycle_service.create_trade(
        symbol="EURUSD", side="SELL", entry_price=1.1000, stop_loss=1.1050,
        take_profit_1=1.1010, quantity=1,
    )


def test_partial_then_full_close_uses_weighted_r_and_decimal_pnl():
    trade = create_trade()

    partial = trade_lifecycle_service.partial_close(trade["id"], 0.30, 1.1100, "TP1")
    assert partial["remaining_quantity"] == 0.7
    assert partial["realized_pnl"] == 300.0
    assert partial["legs"][0]["quantity"] == 0.3
    assert partial["legs"][0]["pnl"] == 300.0
    assert partial["legs"][0]["r_multiple"] == 2.0
    assert partial["legs"][0]["r_contribution"] == 0.6
    assert partial["total_r"] == 0.6
    assert partial["closed_at"] is None

    closed = trade_lifecycle_service.full_close(trade["id"], 1.1050)
    assert closed["status"] == "CLOSED"
    assert closed["remaining_quantity"] == 0.0
    assert closed["realized_pnl"] == 650.0
    assert len(closed["legs"]) == 2
    assert closed["legs"][1]["quantity"] == 0.7
    assert closed["legs"][1]["pnl"] == 350.0
    assert closed["legs"][1]["r_multiple"] == 1.0
    assert closed["legs"][1]["r_contribution"] == 0.7
    assert closed["total_r"] == 1.3
    parse_utc(closed["created_at"])
    parse_utc(closed["updated_at"])
    parse_utc(closed["closed_at"])
    parse_utc(closed["legs"][0]["closed_at"])
    parse_utc(closed["legs"][1]["closed_at"])


def test_sell_trade_close_math_is_side_aware():
    trade = create_trade(
        side="SELL",
        entry_price=1.1000,
        stop_loss=1.1050,
        take_profit_1=1.0950,
        take_profit_2=1.0900,
        take_profit_3=1.0850,
    )

    partial = trade_lifecycle_service.partial_close(trade["id"], 0.5, 1.0900, "TP1")
    assert partial["realized_pnl"] == 500.0
    closed = trade_lifecycle_service.full_close(trade["id"], 1.0950)
    assert closed["realized_pnl"] == 750.0
    assert closed["total_r"] == 1.5


def test_no_over_close_or_double_close_corruption():
    trade = create_trade()
    assert "error" in trade_lifecycle_service.partial_close(trade["id"], 1.01, 1.1100, "BAD")

    closed = trade_lifecycle_service.full_close(trade["id"], 1.1050)
    before = db.find_one("trades", trade["id"])
    assert closed["status"] == "CLOSED"

    assert "error" in trade_lifecycle_service.full_close(trade["id"], 1.1060)
    assert "error" in trade_lifecycle_service.partial_close(trade["id"], 0.5, 1.1060, "LATE")
    after = db.find_one("trades", trade["id"])
    assert after["remaining_quantity"] == before["remaining_quantity"] == 0.0
    assert after["realized_pnl"] == before["realized_pnl"]
    assert after["closed_at"] == before["closed_at"]
    assert len(after["legs"]) == len(before["legs"]) == 1


def test_concurrent_full_close_only_records_one_leg():
    trade = create_trade()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: trade_lifecycle_service.full_close(trade["id"], 1.1050), range(2)))

    saved = db.find_one("trades", trade["id"])
    assert saved["status"] == "CLOSED"
    assert saved["remaining_quantity"] == 0.0
    assert len(saved["legs"]) == 1
    assert sum(1 for result in results if "error" not in result) == 1


def test_kelly_consistency_between_trade_lifecycle_and_quant():
    for idx, pnl in enumerate([100, 100, 100, -50, -50]):
        db.insert("trades", {
            "id": f"kelly-{idx}",
            "status": "CLOSED",
            "symbol": "EURUSD",
            "realized_pnl": pnl,
            "total_r": pnl / 50,
        })

    lifecycle = trade_lifecycle_service.get_kelly_criterion()
    quant = quant_service.compute_kelly(db.find("trades", status="CLOSED"))

    assert lifecycle["win_rate"] == quant["win_rate"] == 0.6
    assert lifecycle["win_pct"] == quant["win_pct"] == 60.0
    assert abs(lifecycle["avg_loss"]) == quant["avg_loss"] == 50.0
    assert lifecycle["avg_win"] == quant["avg_win"] == 100.0
    assert lifecycle["kelly_fraction"] == quant["kelly_fraction"] == 0.4
    assert lifecycle["kelly_half"] == quant["kelly_half"] == 0.2
