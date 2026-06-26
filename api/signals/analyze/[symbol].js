import { getHistory } from '../../../../lib/yahoo-finance.js';
import { analyze } from '../../../../lib/ict-patterns.js';

function buildSignal(analysis) {
  const bias = analysis.current_bias;
  const score = analysis.confluence_score || 0;
  let direction = 'NEUTRAL';
  let confidence = 0.5;
  let entryZone = null;
  let stopLoss = null;
  let takeProfit = null;

  if (bias === 'BULLISH' && score >= 5) {
    direction = 'BUY';
    confidence = Math.min(0.95, 0.4 + score * 0.1);
    entryZone = analysis.current_price - 0.002 * analysis.current_price;
    stopLoss = Number((analysis.current_price - 0.01 * analysis.current_price).toFixed(5));
    takeProfit = Number((analysis.current_price + 0.015 * analysis.current_price).toFixed(5));
  } else if (bias === 'BEARISH' && score >= 5) {
    direction = 'SELL';
    confidence = Math.min(0.95, 0.4 + score * 0.1);
    entryZone = analysis.current_price + 0.002 * analysis.current_price;
    stopLoss = Number((analysis.current_price + 0.01 * analysis.current_price).toFixed(5));
    takeProfit = Number((analysis.current_price - 0.015 * analysis.current_price).toFixed(5));
  }

  return {
    direction,
    confidence: Number(confidence.toFixed(3)),
    confluences: analysis.active_confluences || [],
    entryZone: entryZone ? Number(entryZone.toFixed(5)) : null,
    stopLoss,
    takeProfit
  };
}

export default async function handler(req, res) {
  const { symbol } = req.query;
  if (!symbol) return res.status(400).json({ error: 'Symbol is required' });

  try {
    const candles = await getHistory(symbol, '15m', 100);
    const analysis = analyze(candles, symbol, '15m');
    const signal = buildSignal(analysis);
    return res.status(200).json({ symbol, signal });
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Signal generation failed' });
  }
}
