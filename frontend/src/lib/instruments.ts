// Single source of truth for the instruments the app supports.
// Matches the backend instrument config (app/services/instrument_config.py):
// symbols that exist on the MT5 broker AND have exact lot-calc config, so the
// price feed, execution, signals and alerts all stay within what's tradeable.
// Keep this in sync with the backend list.
export const SUPPORTED_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD', 'XAUUSD']
