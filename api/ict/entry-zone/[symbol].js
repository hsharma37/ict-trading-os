import { getHistory } from '../../../../lib/yahoo-finance.js';
import { analyze, calculateEntry } from '../../../../lib/ict-patterns.js';

export default async function handler(req, res) {
  const { symbol } = req.query;
  const bias = req.query.bias || 'NEUTRAL';
  const timeframe = req.query.timeframe || '15m';
  if (!symbol) return res.status(400).json({ error: 'Symbol is required' });

  try {
    const candles = await getHistory(symbol, timeframe, 100);
    if (!candles.length) return res.status(404).json({ error: 'No data' });

    const analysis = analyze(candles, symbol, timeframe);
    const entry = calculateEntry(analysis.patterns, bias, analysis.current_price);
    if (!entry) {
      return res.status(200).json({ symbol, bias, current_price: analysis.current_price, message: 'No clear entry zone' });
    }
    return res.status(200).json({ symbol, bias, current_price: analysis.current_price, entry_zone: entry });
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Entry zone failed' });
  }
}
