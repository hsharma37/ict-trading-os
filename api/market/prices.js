import { getPrice } from '../../lib/yahoo-finance.js';

export default async function handler(req, res) {
  const { symbols = '' } = req.query;
  const list = symbols
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  const prices = {};
  for (const symbol of list) {
    try {
      prices[symbol] = await getPrice(symbol);
    } catch (error) {
      prices[symbol] = { error: error.message || 'Unable to fetch price' };
    }
  }

  return res.status(200).json({ prices });
}
