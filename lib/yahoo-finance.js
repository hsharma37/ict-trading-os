const SYMBOL_MAP = {
  "NQ1!": "NQ=F",
  "ES1!": "ES=F",
  "EURUSD": "EURUSD=X",
  "GBPUSD": "GBPUSD=X",
  "XAUUSD": "GC=F",
  "USDJPY": "USDJPY=X",
  "BTCUSD": "BTC-USD",
  "CL1!": "CL=F"
};

const BASE_PRICES = {
  "NQ1!": 18445.25,
  "ES1!": 5523.75,
  "EURUSD": 1.08342,
  "GBPUSD": 1.26581,
  "XAUUSD": 2382.40,
  "USDJPY": 157.423,
  "BTCUSD": 64820,
  "CL1!": 82.34
};

const INSTRUMENTS = [
  { symbol: "NQ1!", name: "Nasdaq Futures", category: "index" },
  { symbol: "ES1!", name: "S&P Futures", category: "index" },
  { symbol: "EURUSD", name: "EUR/USD", category: "forex" },
  { symbol: "GBPUSD", name: "GBP/USD", category: "forex" },
  { symbol: "XAUUSD", name: "Gold", category: "metal" },
  { symbol: "USDJPY", name: "USD/JPY", category: "forex" },
  { symbol: "BTCUSD", name: "Bitcoin", category: "crypto" },
  { symbol: "CL1!", name: "Crude Oil", category: "commodity" }
];

function mapSymbol(symbol) {
  return SYMBOL_MAP[symbol] || symbol;
}

function safeValue(value, fallback = 0) {
  return value === undefined || value === null ? fallback : value;
}

async function fetchJson(url) {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (!res.ok) {
    throw new Error(`Yahoo Finance request failed ${res.status}`);
  }
  return res.json();
}

function lastValid(values) {
  if (!Array.isArray(values)) return null;
  for (let i = values.length - 1; i >= 0; i -= 1) {
    if (values[i] !== null && values[i] !== undefined) return values[i];
  }
  return null;
}

function syntheticPrice(symbol) {
  const base = BASE_PRICES[symbol] ?? 100;
  const price = base + (Math.random() - 0.5) * base * 0.001;
  return {
    symbol,
    price: Number(price.toFixed(5)),
    bid: Number((price - base * 0.0002).toFixed(5)),
    ask: Number((price + base * 0.0002).toFixed(5)),
    change: 0,
    change_pct: 0,
    volume: 0,
    timestamp: new Date().toISOString(),
    source: 'synthetic'
  };
}

export async function getPrice(symbol) {
  const yahooSymbol = mapSymbol(symbol);
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}?range=1d&interval=1m`;
    const payload = await fetchJson(url);
    const result = payload?.chart?.result?.[0];
    if (!result) throw new Error('No result');

    const meta = result.meta || {};
    const quote = result.indicators?.quote?.[0] || {};
    const close = quote.close || [];
    const high = quote.high || [];
    const low = quote.low || [];
    const volume = quote.volume || [];
    const price = lastValid(close) ?? meta.regularMarketPrice ?? meta.previousClose;
    const prev = meta.previousClose ?? price;
    if (price === null || price === undefined) throw new Error('Missing price');

    const bid = lastValid(low, price);
    const ask = lastValid(high, price);
    const change = price - prev;

    return {
      symbol,
      price: Number(price.toFixed(5)),
      bid: Number((bid ?? price).toFixed(5)),
      ask: Number((ask ?? price).toFixed(5)),
      change: Number(change.toFixed(5)),
      change_pct: prev ? Number(((change / prev) * 100).toFixed(3)) : 0,
      volume: Number(lastValid(volume, 0) ?? 0),
      timestamp: new Date().toISOString(),
      source: 'yahoo'
    };
  } catch (error) {
    return syntheticPrice(symbol);
  }
}

export async function getHistory(symbol, timeframe = '1h', limit = 200) {
  const yahooSymbol = mapSymbol(symbol);
  const tfMap = {
    '1m': ['1d', '1m'],
    '5m': ['5d', '5m'],
    '15m': ['5d', '15m'],
    '1h': ['1mo', '1h'],
    '4h': ['3mo', '1h'],
    '1d': ['6mo', '1d']
  };
  const [period, interval] = tfMap[timeframe] || ['1mo', '1h'];

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}?period=${period}&interval=${interval}&events=div%2Csplit`;
    const payload = await fetchJson(url);
    const result = payload?.chart?.result?.[0];
    if (!result) throw new Error('No result');

    const timestamps = result.timestamp || [];
    const quote = result.indicators?.quote?.[0] || {};
    const open = quote.open || [];
    const high = quote.high || [];
    const low = quote.low || [];
    const close = quote.close || [];
    const volume = quote.volume || [];

    const candles = [];
    for (let idx = 0; idx < timestamps.length && candles.length < limit; idx += 1) {
      const ts = timestamps[idx];
      const o = open[idx];
      const h = high[idx];
      const l = low[idx];
      const c = close[idx];
      const v = volume[idx] ?? 0;
      if ([o, h, l, c].some(x => x === null || x === undefined)) continue;
      candles.push({
        time: ts,
        open: Number(o.toFixed(5)),
        high: Number(h.toFixed(5)),
        low: Number(l.toFixed(5)),
        close: Number(c.toFixed(5)),
        volume: Number(v)
      });
    }
    return candles.slice(-limit);
  } catch (error) {
    return syntheticHistory(symbol, limit);
  }
}

export function getInstruments() {
  return INSTRUMENTS;
}

function syntheticHistory(symbol, limit) {
  const base = BASE_PRICES[symbol] ?? 100;
  const candles = [];
  let price = base;
  const now = Math.floor(Date.now() / 1000);
  for (let i = 0; i < limit; i += 1) {
    const o = price;
    const c = price + (Math.random() - 0.48) * base * 0.002;
    const h = Math.max(o, c) + Math.random() * base * 0.001;
    const l = Math.min(o, c) - Math.random() * base * 0.001;
    candles.push({
      time: now - (limit - i) * 3600,
      open: Number(o.toFixed(5)),
      high: Number(h.toFixed(5)),
      low: Number(l.toFixed(5)),
      close: Number(c.toFixed(5)),
      volume: Math.floor(Math.random() * 1000)
    });
    price = c;
  }
  return candles;
}
