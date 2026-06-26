function average(values) {
  return values.reduce((sum, item) => sum + item, 0) / Math.max(values.length, 1);
}

export function analyze(candles, symbol, timeframe) {
  const closes = candles.map(c => c.close);
  const opens = candles.map(c => c.open);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);

  const currentPrice = closes[closes.length - 1] ?? 0;
  const recentRange = closes.slice(-10);
  const momentum = recentRange[recentRange.length - 1] - recentRange[0];
  const bias = momentum > 0 ? 'BULLISH' : momentum < 0 ? 'BEARISH' : 'NEUTRAL';

  const patterns = [];
  if (candles.length >= 5) {
    const lastHigh = Math.max(...highs.slice(-5));
    const lastLow = Math.min(...lows.slice(-5));
    const lastClose = closes[closes.length - 1];
    const prevClose = closes[closes.length - 2] ?? lastClose;

    if (lastClose > prevClose && lastClose > lastHigh * 0.995) {
      patterns.push({ type: 'MSS', direction: 'bullish', price_level: lastHigh, confidence: 0.75 });
    }
    if (lastClose < prevClose && lastClose < lastLow * 1.005) {
      patterns.push({ type: 'MSS', direction: 'bearish', price_level: lastLow, confidence: 0.75 });
    }

    const gaps = [];
    for (let i = 2; i < candles.length; i += 1) {
      if (highs[i - 2] < lows[i]) gaps.push({ type: 'FVG', direction: 'bullish', price_level: (highs[i - 2] + lows[i]) / 2, confidence: 0.7 });
      if (lows[i - 2] > highs[i]) gaps.push({ type: 'FVG', direction: 'bearish', price_level: (lows[i - 2] + highs[i]) / 2, confidence: 0.7 });
    }
    patterns.push(...gaps.slice(-2));
  }

  const liquidity = [];
  if (candles.length >= 6) {
    const highsWindow = highs.slice(-6);
    const lowsWindow = lows.slice(-6);
    if (Math.max(...highsWindow) - Math.min(...highsWindow) > average(highsWindow) * 0.01) {
      liquidity.push({ type: 'LIQUIDITY', direction: bias === 'BULLISH' ? ' bearish' : 'bullish', price_level: average(highsWindow), confidence: 0.6 });
    }
  }
  patterns.push(...liquidity);

  const score = patterns.reduce((sum, pattern) => sum + (pattern.confidence ?? 0.5), 0);
  const confluence_score = Number(score.toFixed(2));
  const active_confluences = patterns.map(p => `${p.type}_${p.direction}`);

  return {
    symbol,
    timeframe,
    patterns,
    current_bias: bias,
    confluence_score,
    active_confluences,
    current_price: currentPrice,
    premium_discount: currentPrice > average(highs) ? 'premium' : 'discount'
  };
}

export function calculateEntry(patterns, bias, currentPrice) {
  if (!patterns || bias === 'NEUTRAL') return null;
  const relevant = patterns.filter(p => p.direction && p.direction.toUpperCase().includes(bias[0] === 'B' && bias === 'BULLISH' ? 'bull' : 'bear'));
  if (!relevant.length) return null;
  const nearest = relevant.reduce((closest, pattern) => {
    if (!closest) return pattern;
    return Math.abs(pattern.price_level - currentPrice) < Math.abs(closest.price_level - currentPrice) ? pattern : closest;
  }, null);

  const entry = nearest?.price_level ?? currentPrice;
  if (bias === 'BULLISH') {
    const sl = entry * 0.995;
    const risk = entry - sl;
    return {
      entry: Number(entry.toFixed(5)),
      sl: Number(sl.toFixed(5)),
      tp1: Number((entry + risk).toFixed(5)),
      tp2: Number((entry + risk * 2).toFixed(5)),
      tp3: Number((entry + risk * 3).toFixed(5)),
      risk: Number(risk.toFixed(5))
    };
  }

  const sl = entry * 1.005;
  const risk = sl - entry;
  return {
    entry: Number(entry.toFixed(5)),
    sl: Number(sl.toFixed(5)),
    tp1: Number((entry - risk).toFixed(5)),
    tp2: Number((entry - risk * 2).toFixed(5)),
    tp3: Number((entry - risk * 3).toFixed(5)),
    risk: Number(risk.toFixed(5))
  };
}
