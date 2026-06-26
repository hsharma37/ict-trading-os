function sum(values) {
  return values.reduce((acc, value) => acc + value, 0);
}

function mean(values) {
  return values.length ? sum(values) / values.length : 0;
}

function standardDeviation(values) {
  const avg = mean(values);
  const variance = values.reduce((acc, value) => acc + (value - avg) ** 2, 0) / Math.max(values.length, 1);
  return Math.sqrt(variance);
}

function downsideDeviation(values) {
  const target = 0;
  const downside = values.filter(r => r < target).map(r => (r - target) ** 2);
  return Math.sqrt(sum(downside) / Math.max(downside.length, 1));
}

function maxDrawdown(values) {
  let peak = -Infinity;
  let drawdown = 0;
  let maxDD = 0;
  values.forEach(value => {
    if (value > peak) peak = value;
    drawdown = (peak - value) / Math.max(peak, 1);
    maxDD = Math.max(maxDD, drawdown);
  });
  return maxDD;
}

export function computeMetrics(trades) {
  const returns = trades.map(t => Number(t.realized_pnl ?? 0));
  const avg = mean(returns);
  const sd = standardDeviation(returns);
  const downside = downsideDeviation(returns);
  const sharpe = sd ? avg / sd : 0;
  const sortino = downside ? avg / downside : 0;
  const cagr = trades.length ? avg / Math.max(1, trades.length) : 0;
  const maxDD = maxDrawdown(returns);
  const var95 = returns.length ? returns.sort((a, b) => a - b)[Math.max(0, Math.floor(returns.length * 0.05) - 1)] : 0;
  const cvar95 = returns.filter(r => r <= var95).reduce((acc, value) => acc + value, 0) / Math.max(returns.filter(r => r <= var95).length, 1);

  return {
    sharpe: Number(sharpe.toFixed(3)),
    sortino: Number(sortino.toFixed(3)),
    calmar: maxDD ? Number((cagr / maxDD).toFixed(3)) : 0,
    maxDrawdown: Number(maxDD.toFixed(3)),
    var: Number(var95.toFixed(3)),
    cvar: Number(cvar95.toFixed(3))
  };
}

export function computeKelly(trades) {
  const returns = trades.map(t => Number(t.realized_pnl ?? 0));
  const wins = returns.filter(r => r > 0);
  const losses = returns.filter(r => r <= 0);
  if (!wins.length || !losses.length) return null;

  const winRate = wins.length / returns.length;
  const avgWin = mean(wins);
  const avgLoss = Math.abs(mean(losses));
  const ratio = avgLoss ? avgWin / avgLoss : 0;
  const kelly = winRate - (1 - winRate) / Math.max(ratio, 0.0001);

  return { winRate: Number(winRate.toFixed(3)), ratio: Number(ratio.toFixed(3)), kelly: Number(kelly.toFixed(3)) };
}

export function monteCarlo(trades, nSimulations = 1000, nTrades = 100) {
  const returns = trades.map(t => Number(t.realized_pnl ?? 0));
  if (!returns.length) return { simulations: [], summary: 'No closed trades' };

  const results = [];
  for (let i = 0; i < nSimulations; i += 1) {
    let equity = 0;
    for (let j = 0; j < nTrades; j += 1) {
      const randomReturn = returns[Math.floor(Math.random() * returns.length)];
      equity += randomReturn;
    }
    results.push(equity);
  }

  const sorted = results.slice().sort((a, b) => a - b);
  return {
    simulations: results,
    summary: {
      mean: Number(mean(results).toFixed(2)),
      median: Number(sorted[Math.floor(sorted.length / 2)].toFixed(2)),
      worst: Number(sorted[0].toFixed(2)),
      best: Number(sorted[sorted.length - 1].toFixed(2)),
      pct5: Number(sorted[Math.floor(sorted.length * 0.05)].toFixed(2)),
      pct95: Number(sorted[Math.floor(sorted.length * 0.95)].toFixed(2))
    }
  };
}

export function coach(trades) {
  const wins = trades.filter(t => t.realized_pnl > 0).length;
  const losses = trades.filter(t => t.realized_pnl <= 0).length;
  const total = trades.length;
  const winRate = total ? Number((wins / total).toFixed(3)) : 0;
  const avgPnl = total ? Number((sum(trades.map(t => Number(t.realized_pnl ?? 0))) / total).toFixed(2)) : 0;

  return {
    recommendation: winRate > 0.55 ? 'Stay the course and scale carefully.' : 'Review entry rules and risk sizing before adding new trades.',
    winRate,
    averagePnl: avgPnl,
    summary: `Closed ${total} trades: ${wins} winners, ${losses} losers.`
  };
}
