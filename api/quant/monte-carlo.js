import { monteCarlo } from '../../lib/quant-calculations.js';
import { getAllTrades } from '../../lib/database.js';

export default function handler(req, res) {
  const n_simulations = Number(req.query.n_simulations || 1000);
  const n_trades = Number(req.query.n_trades || 100);
  const trades = getAllTrades().filter(t => t.status === 'CLOSED');
  return res.status(200).json(monteCarlo(trades, n_simulations, n_trades));
}
