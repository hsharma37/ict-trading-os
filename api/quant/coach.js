import { coach } from '../../lib/quant-calculations.js';
import { getAllTrades } from '../../lib/database.js';

export default function handler(req, res) {
  const trades = getAllTrades().filter(t => t.status === 'CLOSED');
  return res.status(200).json(coach(trades));
}
