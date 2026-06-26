import { getHistory } from '../../../lib/yahoo-finance.js';

export default async function handler(req, res) {
  const { symbol } = req.query;
  const timeframe = req.query.timeframe || '1h';
  const limit = Number(req.query.limit || 200);

  if (!symbol) {
    return res.status(400).json({ error: 'Symbol is required' });
  }

  try {
    const data = await getHistory(symbol, timeframe, limit);
    return res.status(200).json({ symbol, timeframe, candles: data });
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Unable to fetch history' });
  }
}
