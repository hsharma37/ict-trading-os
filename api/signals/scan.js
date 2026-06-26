import { getHistory } from '../../../lib/yahoo-finance.js';
import { analyze } from '../../../lib/ict-patterns.js';

const SYMBOLS = ['NQ1!', 'ES1!', 'EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'BTCUSD', 'CL1!'];

export default async function handler(req, res) {
  const results = [];
  for (const symbol of SYMBOLS) {
    const candles = await getHistory(symbol, '15m', 100);
    const analysis = analyze(candles, symbol, '15m');
    const signal = analysis.confluence_score >= 5 ? (analysis.current_bias === 'BULLISH' ? 'BUY' : analysis.current_bias === 'BEARISH' ? 'SELL' : 'NEUTRAL') : 'NEUTRAL';
    if (signal !== 'NEUTRAL') {
      results.push({ symbol, signal, score: analysis.confluence_score, bias: analysis.current_bias });
    }
  }
  return res.status(200).json({ scanned: SYMBOLS.length, signals_found: results.length, signals: results });
}
