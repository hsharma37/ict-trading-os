import { getHistory } from '../../../../lib/yahoo-finance.js';
import { analyze } from '../../../../lib/ict-patterns.js';

export default async function handler(req, res) {
  const { symbol } = req.query;
  const timeframe = req.query.timeframe || '15m';

  if (!symbol) {
    return res.status(400).json({ error: 'Symbol is required' });
  }

  try {
    const candles = await getHistory(symbol, timeframe, 100);
    const analysis = analyze(candles, symbol, timeframe);
    return res.status(200).json(analysis);
  } catch (error) {
    return res.status(500).json({ error: error.message || 'ICT analysis failed' });
  }
}
