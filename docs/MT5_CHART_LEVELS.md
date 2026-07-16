# Drawing ICT levels on your MT5 chart

The MetaTrader5 **Python** API can read data and place trades, but it **cannot draw
objects** (lines/rectangles) on a chart — that's MQL-only, run inside the terminal.
So the levels are drawn by a tiny companion indicator that reads a file the bridge
writes.

Flow: **App (Signals → "Draw on MT5 chart")** → bridge writes
`MQL5\Files\ictos_levels_<SYMBOL>.csv` → **ICTOSLevels indicator** on your chart
reads it and draws the zones.

## One-time install of the indicator

1. In MetaTrader 5: **File → Open Data Folder** → `MQL5\Indicators\`.
2. Copy **`mt5-bridge/ICTOSLevels.mq5`** into that folder.
3. Open **MetaEditor** (F4), open `ICTOSLevels.mq5`, press **F7** to compile.
4. Back in MT5, in the Navigator → Indicators, drag **ICTOSLevels** onto the chart
   of the symbol you want (e.g. XAUUSD). Allow it (no special permissions needed —
   it only reads its own file from the sandbox).

It re-reads the file every few seconds (configurable via `RefreshSeconds`), so
once attached it stays current.

## Using it

- Make sure the **bridge is running** and connected (the watchdog handles this).
- Pull the latest bridge code and restart it (adds the `/draw-levels` route):
  ```powershell
  cd <ict-trading-os>\mt5-bridge && git pull   # then restart the bridge/watchdog
  ```
- In the app: **Signals → pick a symbol → "Draw on MT5 chart".** The zones appear
  on that symbol's chart within a few seconds:
  - **green** = bullish zones, **red** = bearish
  - **rectangles** = Order Blocks / Fair Value Gaps (price ranges)
  - **dotted lines** = market-structure / liquidity levels

Push again anytime to refresh (the indicator clears its old objects each read).

## Notes

- One file per symbol, so multiple charts each show their own levels.
- The app **refuses to draw** when the price feed is simulated (no fake levels).
- Honest reminder: these are the *detected* ICT zones, not proven trade signals —
  the backtest showed the raw signal has no net edge. Use them as context.
