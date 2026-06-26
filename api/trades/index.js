import { getTrades, createTrade, closeTrade } from '../../lib/database.js';

export default async function handler(req, res) {
  if (req.method === 'GET') {
    const { status, symbol } = req.query;
    return res.status(200).json(getTrades({ status, symbol }));
  }

  if (req.method === 'POST') {
    const data = req.body;
    if (!data || !data.symbol || !data.side || !data.quantity || !data.entry_price) {
      return res.status(400).json({ error: 'symbol, side, quantity and entry_price are required' });
    }
    const trade = createTrade(data);
    return res.status(201).json(trade);
  }

  if (req.method === 'DELETE') {
    return res.status(405).json({ error: 'DELETE not supported here' });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
