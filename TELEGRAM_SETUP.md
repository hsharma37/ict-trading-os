# Telegram Integration Guide for MT5 Bridge

## How to Set Up Telegram Notifications

### Step 1: Create a Bot with BotFather
1. Open Telegram and search for **@BotFather**
2. Send the command `/start`
3. Send `/newbot`
4. Give your bot a name (e.g., "MT5 Trading Bot")
5. Give your bot a username (e.g., "my_mt5_trading_bot")
6. BotFather will send you a **Bot Token** (looks like: `123456789:ABCdEfGhIjklmnOpqrStUvwxyz`)
7. **Copy and save this token** — you'll need it in the next step

### Step 2: Get Your Chat ID
There are two ways to receive notifications:

#### Option A: Direct to Your Personal Chat (Recommended for testing)
1. Search for **@userinfobot** in Telegram
2. Send `/start`
3. It will reply with your **User ID** (a number like `123456789`)
4. This is your `TELEGRAM_CHAT_ID`

#### Option B: Create a Channel or Group
1. Create a new Telegram channel (e.g., "MT5 Trading Alerts")
2. Add your bot to the channel as an admin
3. Send a message to the channel
4. Go to: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Replace `<YOUR_BOT_TOKEN>` with your actual token from Step 1
6. Look for `"chat":{"id": -123456789}` — the negative number is your `TELEGRAM_CHAT_ID`

### Step 3: Configure Environment Variables
1. Copy `.env.example` to `.env`
2. Fill in the two values:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

### Step 4: Test the Connection
1. Start the MT5 Bridge:
   ```bash
   MT5_BRIDGE_PORT=5000 python3 mt5bridgeScript.py
   ```
2. Run the test endpoint:
   ```bash
   curl -X POST http://localhost:5000/test-telegram
   ```
3. You should receive a test message on Telegram saying:
   > 🔧 MT5 Bridge test message — Telegram connection is working!

### Step 5: Verify the Bridge is Running
The bridge should output:
```
Server listening on http://localhost:5000
[MT5 Bridge] Telegram message sent successfully
```

If you see `[MT5 Bridge] Telegram not configured`, double-check your `.env` file.

## Troubleshooting

### "Telegram not configured" error
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`
- Make sure there are no extra spaces or newlines in the values
- Restart the bridge after changing `.env`

### "Telegram notification failed"
- Check that your bot token is correct (starts with numbers, contains `:`)
- Verify your Chat ID is a valid number (personal) or negative number (channel)
- Ensure your internet connection is working
- Check if your bot is still active (test with @userinfobot)

### Can't find your Chat ID?
- Try sending any message to your bot directly
- Run: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
- Look for the latest `"chat":{"id": ...}` entry

## How It Works

When a trade signal or notification occurs, the MT5 Bridge:
1. Detects the event (e.g., trade opened, target hit, SL hit)
2. Calls `send_telegram_message()` with formatted text
3. Makes an HTTP POST to Telegram's API
4. Sends the message to your configured chat/channel

## Note

- Messages are sent via Telegram's official Bot API
- Your bot token should be kept private (add `.env` to `.gitignore`)
- The bridge retries with a 15-second timeout for each message
- If the bridge crashes, telegram notifications won't work — keep it running
