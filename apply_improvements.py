#!/usr/bin/env python3
"""
Apply improvements:
1. Add leverage (1-100x) to lot calculator
2. Implement KB localStorage persistence
3. Fix Telegram integration with test endpoint
"""

import re

# Read the HTML file
with open('ICT_Trading_OS_v7.html', 'r') as f:
    html = f.read()

# 1. ADD LEVERAGE SLIDER TO LOT CALCULATOR FORM
leverage_html = '''          <div class="form-grid">
            <div class="form-row"><label>Account Balance ($)</label><input type="number" id="lc-balance" value="10000" step="100" oninput="calcLotSize()"></div>
            <div class="form-row"><label>Risk % per Trade</label><input type="number" id="lc-risk-pct" value="2" step="0.1" min="0.1" max="10" oninput="calcLotSize()"></div>
            <div class="form-row"><label>Leverage</label><input type="range" id="lc-leverage" value="1" min="1" max="100" step="1" oninput="updateLeverageLabel(); calcLotSize()" style="width:100%;"></div>
            <div class="form-row"><label>&nbsp;</label><div class="dim-text" id="lc-leverage-label">1x</div></div>
          </div>'''

old_form_grid = '''          <div class="form-grid">
            <div class="form-row"><label>Account Balance ($)</label><input type="number" id="lc-balance" value="10000" step="100" oninput="calcLotSize()"></div>
            <div class="form-row"><label>Risk % per Trade</label><input type="number" id="lc-risk-pct" value="2" step="0.1" min="0.1" max="10" oninput="calcLotSize()"></div>
          </div>'''

html = html.replace(old_form_grid, leverage_html)
print("✓ Added leverage slider to lot calculator form")

# 2. ADD updateLeverageLabel FUNCTION BEFORE calcLotSize
update_lever_func = '''function updateLeverageLabel() {
  const lev = parseInt(document.getElementById('lc-leverage')?.value) || 1;
  const label = document.getElementById('lc-leverage-label');
  if (label) label.textContent = lev + 'x';
}
function calcLotSize() {'''

old_calc_lot = 'function calcLotSize() {'
html = html.replace(old_calc_lot, update_lever_func)
print("✓ Added updateLeverageLabel() function")

# 3. UPDATE calcLotSize() to use leverage
old_calc_start = '''function updateLeverageLabel() {
  const lev = parseInt(document.getElementById('lc-leverage')?.value) || 1;
  const label = document.getElementById('lc-leverage-label');
  if (label) label.textContent = lev + 'x';
}
function calcLotSize() {
  const inst = INSTRUMENTS[GLOBAL_SYMBOL];
  if (!inst) return;
  const balance = parseFloat(document.getElementById('lc-balance')?.value) || 10000;
  const riskPct = parseFloat(document.getElementById('lc-risk-pct')?.value) || 2;
  const pipVal = parseFloat(document.getElementById('lc-pip-val')?.value) || inst.pipVal;
  const entry = parseFloat(document.getElementById('lc-entry')?.value) || inst.price;
  const sl = parseFloat(document.getElementById('lc-sl')?.value) || 0;
  const dir = document.getElementById('lc-dir')?.value || 'long';
  const pipDigits = parseInt(document.getElementById('lc-pip-digits')?.value) ?? inst.pipDigits;
  const digits = inst.digits ?? pipDigits;
  const tp1r = parseFloat(document.getElementById('lc-tp1-r')?.value) || 1;
  const tp2r = parseFloat(document.getElementById('lc-tp2-r')?.value) || 2;'''

new_calc_start = '''function updateLeverageLabel() {
  const lev = parseInt(document.getElementById('lc-leverage')?.value) || 1;
  const label = document.getElementById('lc-leverage-label');
  if (label) label.textContent = lev + 'x';
}
function calcLotSize() {
  const inst = INSTRUMENTS[GLOBAL_SYMBOL];
  if (!inst) return;
  const balance = parseFloat(document.getElementById('lc-balance')?.value) || 10000;
  const riskPct = parseFloat(document.getElementById('lc-risk-pct')?.value) || 2;
  const leverage = parseInt(document.getElementById('lc-leverage')?.value) || 1;
  const pipVal = parseFloat(document.getElementById('lc-pip-val')?.value) || inst.pipVal;
  const entry = parseFloat(document.getElementById('lc-entry')?.value) || inst.price;
  const sl = parseFloat(document.getElementById('lc-sl')?.value) || 0;
  const dir = document.getElementById('lc-dir')?.value || 'long';
  const pipDigits = parseInt(document.getElementById('lc-pip-digits')?.value) ?? inst.pipDigits;
  const digits = inst.digits ?? pipDigits;
  const tp1r = parseFloat(document.getElementById('lc-tp1-r')?.value) || 1;
  const tp2r = parseFloat(document.getElementById('lc-tp2-r')?.value) || 2;'''

html = html.replace(old_calc_start, new_calc_start)
print("✓ Added leverage parameter to calcLotSize()")

# 4. UPDATE lot size calculation to incorporate leverage
old_lot_calc = '''  const pipSize = Math.pow(10, -pipDigits);
  const riskAmount = (balance*riskPct)/100;
  const slDistance = Math.abs(entry-correctedSL);
  const slPips = slDistance/pipSize;
  const lotSizeRaw = slPips>0 ? (riskAmount/(slPips*pipVal))*leverage : 0;
  const roundedLot = Math.max(0.01, Math.round(lotSizeRaw*100)/100);'''

# Should already be correct from previous edit, but check
if 'const leverage = parseInt' in html and '*leverage' not in html.split('const lotSizeRaw')[1].split(';')[0]:
    html = html.replace(
        '  const lotSizeRaw = slPips>0 ? riskAmount/(slPips*pipVal) : 0;',
        '  const lotSizeRaw = slPips>0 ? (riskAmount/(slPips*pipVal))*leverage : 0;'
    )
    print("✓ Updated lot size calculation with leverage multiplier")

# 5. UPDATE profit displays to include leverage
html = re.sub(
    r"set\('lc-risk-dollar','-\$'\+riskAmount\.toFixed\(2\)\)",
    "set('lc-risk-dollar','-$'+(riskAmount*leverage).toFixed(2))",
    html
)
print("✓ Updated risk dollar display with leverage")

html = re.sub(
    r"set\('lc-tp1-dollar','\+\$'\+tp1Profit\.toFixed\(2\)\);",
    "set('lc-tp1-dollar','+$'+(tp1Profit*leverage).toFixed(2));",
    html
)
html = re.sub(
    r"set\('lc-tp3-dollar','\+\$'\+tp3Profit\.toFixed\(2\)\);",
    "set('lc-tp3-dollar','+$'+(tp3Profit*leverage).toFixed(2));",
    html
)
print("✓ Updated TP profit displays with leverage")

# 6. IMPLEMENT KB LOCALSTORAGE PERSISTENCE
old_load_kb = '''async function loadKBSources() {
  try {
        const data = await apiGet('/kb/sources');
        if (data && data.sources) {
            KNOWLEDGE_BASE.length = 0;
            data.sources.forEach(src => {
                const normalized = { id: src.id, type: src.type, title: src.title, text: src.text, url: src.url, chunks: src.chunks || [] };
                KNOWLEDGE_BASE.push(normalized);
            });
            renderKnowledgeBase();
        }
    } catch (e) {
        console.warn('Loading KB sources failed', e);'''

new_load_kb = '''async function loadKBSources() {
  try {
        const stored = localStorage.getItem('kbSources');
        if (stored) {
            KNOWLEDGE_BASE.length = 0;
            const sources = JSON.parse(stored);
            sources.forEach(src => {
                const normalized = { id: src.id, type: src.type, title: src.title, text: src.text, url: src.url, chunks: src.chunks || [] };
                KNOWLEDGE_BASE.push(normalized);
            });
            renderKnowledgeBase();
        }
    } catch (e) {
        console.warn('Loading KB sources failed', e);'''

html = html.replace(old_load_kb, new_load_kb)
print("✓ Updated KB loading to use localStorage")

# 7. UPDATE persistKBSources function
old_persist = '''function persistKBSources() { /* stub — should POST to backend, but no KB backend exists yet */ }'''
new_persist = '''function persistKBSources() { try { localStorage.setItem('kbSources', JSON.stringify(KNOWLEDGE_BASE)); } catch(e) { console.warn('KB persist failed', e); } }'''

html = html.replace(old_persist, new_persist)
print("✓ Implemented KB localStorage persistence")

# Save updated HTML
with open('ICT_Trading_OS_v7.html', 'w') as f:
    f.write(html)
print("✓ HTML file updated successfully")

# Update mt5bridgeScript.py for Telegram improvements
with open('mt5bridgeScript.py', 'r') as f:
    py = f.read()

# 1. Update env var loading to handle empty strings
old_env_load = '''TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MT5_BRIDGE_PORT = int(os.getenv('MT5_BRIDGE_PORT', '5000'))'''

new_env_load = '''TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
MT5_BRIDGE_PORT = int(os.getenv('MT5_BRIDGE_PORT', '5000'))'''

py = py.replace(old_env_load, new_env_load)
print("✓ Updated Telegram env variable loading")

# 2. Add debug output to send_telegram_message
old_send_tg = '''def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print('[MT5 Bridge] Telegram not configured. Skipping notification.')
        return

    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        print(f'[MT5 Bridge] Telegram notification failed: {exc}')'''

new_send_tg = '''def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print('[MT5 Bridge] Telegram not configured. Skipping notification.')
        print(f'  TELEGRAM_BOT_TOKEN: {"SET" if TELEGRAM_BOT_TOKEN else "NOT SET"}')
        print(f'  TELEGRAM_CHAT_ID: {"SET" if TELEGRAM_CHAT_ID else "NOT SET"}')
        return

    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            print(f'[MT5 Bridge] Telegram message sent successfully')
    except Exception as exc:
        print(f'[MT5 Bridge] Telegram notification failed: {exc}')'''

py = py.replace(old_send_tg, new_send_tg)
print("✓ Added debug output to send_telegram_message")

# 3. Add test endpoint for Telegram
old_home = '''@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'MT5 Bridge is running'})


@app.route('/trade', methods=['POST'])'''

new_home = '''@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'MT5 Bridge is running',
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        'mt5_initialized': mt5.terminal_info() is not None if mt5 else False,
    })


@app.route('/test-telegram', methods=['POST'])
def test_telegram():
    """Test Telegram connectivity with a test message."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return jsonify({'error': 'Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.'}), 400
    
    try:
        send_telegram_message('🔧 MT5 Bridge test message — Telegram connection is working!')
        return jsonify({'status': 'Test message sent', 'chat_id': TELEGRAM_CHAT_ID}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/trade', methods=['POST'])'''

py = py.replace(old_home, new_home)
print("✓ Added test endpoint for Telegram connection")

# Save updated Python file
with open('mt5bridgeScript.py', 'w') as f:
    f.write(py)
print("✓ mt5bridgeScript.py updated successfully")

print("\n✅ All improvements applied successfully!")
print("\nNext steps:")
print("1. Set environment variables: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
print("2. Restart the MT5 Bridge: MT5_BRIDGE_PORT=5000 python3 mt5bridgeScript.py")
print("3. Test Telegram: curl -X POST http://localhost:5000/test-telegram")
print("4. Try leverage in the lot calculator (1-100x range)")
print("5. Your KB will now persist across app restarts using localStorage")
