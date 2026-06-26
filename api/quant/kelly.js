import { computeKelly } from '../../lib/quant-calculations.js';
import { getAllTrades } from '../../lib/database.js';

export default function handler(req, res) {
  const trades = getAllTrades().filter(t => t.status === 'CLOSED');
  const result = computeKelly(trades);
  if (!result) {
    return res.status(200).json({ error: 'Need at least 1 winning and 1 losing closed trade' });
  }
  return res.status(200).json(result);
}
