const globalDb = globalThis.__ICT_TRADING_OS_DB || { trades: [] };
if (!globalThis.__ICT_TRADING_OS_DB) {
  globalThis.__ICT_TRADING_OS_DB = globalDb;
}

function createId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `trade-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

export function getTrades({ status, symbol } = {}) {
  let trades = globalDb.trades;
  if (status) trades = trades.filter(t => t.status === status);
  if (symbol) trades = trades.filter(t => t.symbol === symbol);
  return [...trades].reverse();
}

export function createTrade(data) {
  const trade = {
    id: createId(),
    status: 'OPEN',
    realized_pnl: 0,
    created_at: new Date().toISOString(),
    ...data
  };
  globalDb.trades.push(trade);
  return trade;
}

export function getTradeById(tradeId) {
  return globalDb.trades.find(t => t.id === tradeId) || null;
}

export function closeTrade(tradeId, exitPrice) {
  const trade = getTradeById(tradeId);
  if (!trade) return null;
  const pnl = trade.side === 'BUY'
    ? (exitPrice - trade.entry_price) * trade.quantity
    : (trade.entry_price - exitPrice) * trade.quantity;
  trade.exit_price = exitPrice;
  trade.status = 'CLOSED';
  trade.realized_pnl = Number(pnl.toFixed(2));
  trade.closed_at = new Date().toISOString();
  return trade;
}

export function getAllTrades() {
  return globalDb.trades;
}
