import { getHistory } from '../../../../lib/yahoo-finance.js';
import { analyze } from '../../../../lib/ict-patterns.js';

const TIMEFRAMES = ['1h', '15m', '5m'];

export default async function handler(req, res) {
  const { symbol } = req.query;
  if (!symbol) return res.status(400).json({ error: 'Symbol is required' });

  try {
    const result = { symbol, timeframes: {} };
    for (const timeframe of TIMEFRAMES) {
      const candles = await getHistory(symbol, timeframe, 100);
      result.timeframes[timeframe] = analyze(candles, symbol, timeframe);
    }

    const score = Object.values(result.timeframes).reduce((acc, tf) => acc + (tf.confluence_score || 0), 0);
    const bias = result.timeframes['1h']?.current_bias || 'NEUTRAL';
    let action = 'WAIT';
    let reason = 'No clear setup';
    if (bias === 'BULLISH' && score >= 8) {
      action = 'CONSIDER_LONG';
      reason = 'Strong bullish confluence';
    } else if (bias === 'BEARISH' && score >= 8) {
      action = 'CONSIDER_SHORT';
      reason = 'Strong bearish confluence';
    } else if (score >= 5) {
      action = 'WATCH';
      reason = 'Developing setup';
    }

    result.recommendation = { bias, total_confluence: score, action, reason };
    return res.status(200).json(result);
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Multi-timeframe analysis failed' });
  }
}
