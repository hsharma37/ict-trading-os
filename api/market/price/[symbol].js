import { getPrice } from '../../../lib/yahoo-finance.js';

export default async function handler(req, res) {
  const { symbol } = req.query;
  if (!symbol) {
    return res.status(400).json({ error: 'Symbol is required' });
  }

  try {
    const data = await getPrice(symbol);
    return res.status(200).json(data);
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Unable to fetch price' });
  }
}
