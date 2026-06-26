/**
 * ICT Trading OS - Frontend API Client
 * Connects your HTML frontend to the Vercel backend
 * 
 * Usage: Copy this into your HTML <script> or as a separate .js file
 */

const API_BASE = ''; // same origin backend

// ==================== MARKET DATA ====================

async function getPrice(symbol) {
    const res = await fetch(`${API_BASE}/market/price/${symbol}`);
    return res.json();
}

async function getPrices(symbols = ['NQ1!', 'ES1!', 'EURUSD', 'XAUUSD', 'BTCUSD']) {
    const res = await fetch(`${API_BASE}/market/prices?symbols=${symbols.join(',')}`);
    return res.json();
}

async function getHistory(symbol, timeframe = '1h', limit = 200) {
    const res = await fetch(`${API_BASE}/market/history/${symbol}?timeframe=${timeframe}&limit=${limit}`);
    return res.json();
}

// ==================== ICT ANALYSIS ====================

async function analyzeICT(symbol, timeframe = '15m') {
    const res = await fetch(`${API_BASE}/ict/analyze/${symbol}?timeframe=${timeframe}`);
    return res.json();
}

async function analyzeICTMulti(symbol) {
    const res = await fetch(`${API_BASE}/ict/analyze/multi/${symbol}`);
    return res.json();
}

async function getEntryZone(symbol, bias) {
    const res = await fetch(`${API_BASE}/ict/entry-zone/${symbol}?bias=${bias}`);
    return res.json();
}

// ==================== SIGNALS ====================

async function getSignal(symbol) {
    const res = await fetch(`${API_BASE}/signals/analyze/${symbol}`);
    return res.json();
}

async function getActiveSignals(symbol = null) {
    const url = symbol 
        ? `${API_BASE}/signals/active?symbol=${symbol}` 
        : `${API_BASE}/signals/active`;
    const res = await fetch(url);
    return res.json();
}

async function scanAllSignals() {
    const res = await fetch(`${API_BASE}/signals/scan`, { method: 'POST' });
    return res.json();
}

// ==================== TRADES ====================

async function createTrade(tradeData) {
    const res = await fetch(`${API_BASE}/trades/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tradeData)
    });
    return res.json();
}

async function getTrades(status = null, symbol = null) {
    let url = `${API_BASE}/trades/`;
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (symbol) params.append('symbol', symbol);
    if (params.toString()) url += '?' + params.toString();
    const res = await fetch(url);
    return res.json();
}

async function closeTrade(tradeId, exitPrice) {
    const res = await fetch(`${API_BASE}/trades/${tradeId}/close?exit_price=${exitPrice}`, {
        method: 'POST'
    });
    return res.json();
}

// ==================== QUANT LAB ====================

async function getQuantMetrics() {
    const res = await fetch(`${API_BASE}/quant/metrics`);
    return res.json();
}

async function getKelly() {
    const res = await fetch(`${API_BASE}/quant/kelly`);
    return res.json();
}

async function getCoach() {
    const res = await fetch(`${API_BASE}/quant/coach`);
    return res.json();
}

async function runMonteCarlo(nSimulations = 1000, nTrades = 100) {
    const res = await fetch(`${API_BASE}/quant/monte-carlo?n_simulations=${nSimulations}&n_trades=${nTrades}`, {
        method: 'POST'
    });
    return res.json();
}

// ==================== REAL-TIME POLLING ====================

class LiveDataPoller {
    constructor(symbol, intervalMs = 5000) {
        this.symbol = symbol;
        this.intervalMs = intervalMs;
        this.intervalId = null;
        this.onPrice = null;
        this.onSignal = null;
        this.onPattern = null;
    }

    start() {
        this.intervalId = setInterval(async () => {
            // Poll price
            const price = await getPrice(this.symbol);
            if (this.onPrice) this.onPrice(price);

            // Poll ICT analysis (every 3rd poll to save requests)
            if (Math.random() < 0.33) {
                const analysis = await analyzeICT(this.symbol, '5m');
                if (this.onPattern) this.onPattern(analysis);
            }

            // Poll signal (every 5th poll)
            if (Math.random() < 0.2) {
                const signal = await getSignal(this.symbol);
                if (this.onSignal && signal.signal) this.onSignal(signal);
            }
        }, this.intervalMs);
    }

    stop() {
        if (this.intervalId) clearInterval(this.intervalId);
    }
}

// ==================== EXAMPLE USAGE ====================

// Example: Initialize live polling for NQ1!
// const poller = new LiveDataPoller('NQ1!', 5000);
// poller.onPrice = (data) => console.log('Price:', data.price);
// poller.onSignal = (data) => console.log('Signal:', data.signal);
// poller.start();

// Example: Place a trade
// createTrade({
//     symbol: 'NQ1!',
//     side: 'BUY',
//     quantity: 1.0,
//     entry_price: 18450.0,
//     stop_loss: 18400.0,
//     take_profit_1: 18500.0,
//     strategy: 'MSS + FVG'
// }).then(console.log);
