import sys, json
d = json.load(sys.stdin)
trades = d.get('trades', [])
if trades:
    t = trades[0]
    total = (t.get('realized_pnl',0) + t.get('unrealized_pnl',0))
    print(f"Trade: {t['symbol']} {t['side']} Entry: {t['entry_price']} Current: {t.get('current_price','-')} Qty: {t['remaining_quantity']}")
    print(f"Realized: ${t.get('realized_pnl',0)} | Unrealized: ${t.get('unrealized_pnl',0)} | Total: ${total}")
    print(f"R: {t.get('total_r',0)} | Status: {t['status']}")
else:
    print('No open trades')
