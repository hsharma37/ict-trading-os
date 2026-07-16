"""Telegram service — polling and signal parsing for ICT Trading OS."""
import html as html_lib
import re
import httpx
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.core.database import db
from app.core.config import settings
from app.services.trade_lifecycle_service import trade_lifecycle_service


class TelegramService:
    """Fetch messages from Telegram channel, parse trading signals, store in DB."""

    def __init__(self):
        self.base_url = "https://api.telegram.org/bot"
        self._last_poll_time: Optional[str] = None
        self._offset = 0

    @property
    def token(self) -> str:
        return getattr(settings, "TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def channel_id(self) -> str:
        return getattr(settings, "TELEGRAM_CHANNEL_ID", "") or os.getenv("TELEGRAM_CHANNEL_ID", "")

    @property
    def source_channel(self) -> str:
        """Public channel username to poll via web preview (no bot needed)."""
        return (getattr(settings, "TELEGRAM_SOURCE_CHANNEL", "") or os.getenv("TELEGRAM_SOURCE_CHANNEL", "")).lstrip("@")

    @property
    def is_configured(self) -> bool:
        return bool(self.token) and bool(self.channel_id)

    def _api(self, method: str, **params) -> Dict:
        """Call Telegram Bot API method via httpx."""
        if not self.token:
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}
        url = f"{self.base_url}{self.token}/{method}"
        try:
            r = httpx.get(url, params=params, timeout=30.0)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            return {"ok": False, "error": f"HTTP error: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_updates(self) -> List[Dict]:
        """Poll Telegram for new channel messages."""
        data = self._api("getUpdates", offset=self._offset + 1, limit=100)
        if not data.get("ok"):
            return []
        updates = data.get("result", [])
        for u in updates:
            self._offset = max(self._offset, u.get("update_id", 0))
        return updates

    def _channel_matches(self, chat_id) -> bool:
        cid = str(chat_id) if chat_id is not None else ""
        target = str(self.channel_id).strip()
        # Accept both -100 prefixed and plain numeric IDs
        if target.startswith("-"):
            return cid == target
        return cid == target or cid == f"-{target}" or cid == f"-100{target}"

    def _extract_prices(self, text: str) -> List[float]:
        """Extract potential price levels from text."""
        # Match decimal numbers with 2-6 decimal places, avoiding counts/percentages
        prices = []
        # Simple price regex: digits optionally followed by decimal
        matches = re.findall(r'\b\d{1,5}(?:\.\d{2,6})\b', text)
        for m in matches:
            try:
                prices.append(float(m))
            except ValueError:
                continue
        return prices

    def _extract_integers(self, text: str) -> List[int]:
        matches = re.findall(r'\b\d{3,6}\b', text)
        return [int(m) for m in matches]

    def _parse_signal(self, text: str) -> Dict[str, Any]:
        """Parse raw Telegram message text into structured signal fields."""
        t = text.upper()
        parsed = {
            "symbol": None,
            "side": None,
            "entry_prices": [],
            "stop_loss": None,
            "take_profits": [],
            "strategy": None,
            "confidence": "low",
        }

        # Symbol detection
        symbols = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
            "NZDUSD", "XAUUSD", "XAGUSD", "US30", "US100", "NAS100",
            "NQ", "ES", "NQ1!", "ES1!", "CL1!", "BTCUSD", "ETHUSD",
            "GER30", "UK100", "JP225", "EURJPY", "GBPJPY", "AUDJPY",
            "EURAUD", "GBPAUD", "EURGBP", "EURNZD", "GBPNZD", "CHFJPY",
            "CADJPY", "AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "EURNOK",
            "EURSEK", "EURTRY", "USDCNH", "USDNOK", "USDSEK", "USDTRY",
            "USDMXN", "USDZAR", "XTIUSD", "XBRUSD", "SPX500", "SPX",
        ]
        for sym in symbols:
            if sym in t:
                parsed["symbol"] = sym
                break
        # Fallback: any pair-like pattern
        if not parsed["symbol"]:
            m = re.search(r'\b([A-Z]{3,6})\s?[/\\]?\s?([A-Z]{3,6})\b', text)
            if m:
                parsed["symbol"] = m.group(1) + m.group(2)

        # Side detection
        if re.search(r'\b(BUY|LONG|BOUGHT|BULLISH|CALL)\b', t):
            parsed["side"] = "BUY"
        elif re.search(r'\b(SELL|SHORT|SOLD|BEARISH|PUT)\b', t):
            parsed["side"] = "SELL"

        # Extract prices
        all_prices = self._extract_prices(text)

        # Entry detection
        entry_patterns = [
            r'ENTRY[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'ENTRY\s*PRICE[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'AT[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'@\s*(\d+\.\d+)',
        ]
        for pat in entry_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    parsed["entry_prices"].append(float(m.group(1)))
                except ValueError:
                    pass
        # If no entry extracted, use first price as potential entry if side found
        if not parsed["entry_prices"] and all_prices and parsed["side"]:
            parsed["entry_prices"] = [all_prices[0]]

        # Stop loss detection
        sl_patterns = [
            r'SL[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'STOP\s*LOSS[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'S/L[@\s]*[:\-]?\s*(\d+\.\d+)',
        ]
        for pat in sl_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    parsed["stop_loss"] = float(m.group(1))
                except ValueError:
                    pass
                break
        # If no SL found and we have multiple prices, try heuristics — but FLAG it.
        # A stop guessed from arbitrary numbers in the text is NOT a real stop and
        # must never silently drive a live order (auto_trade refuses on this flag).
        if parsed["stop_loss"] is None and len(all_prices) >= 2 and parsed["side"] and parsed["entry_prices"]:
            entry = parsed["entry_prices"][0]
            if parsed["side"] == "BUY":
                # SL is lowest price below entry
                candidates = [p for p in all_prices if p < entry]
                if candidates:
                    parsed["stop_loss"] = min(candidates)
                    parsed["sl_inferred"] = True
            else:
                candidates = [p for p in all_prices if p > entry]
                if candidates:
                    parsed["stop_loss"] = max(candidates)
                    parsed["sl_inferred"] = True

        # Take profit detection
        tp_patterns = [
            r'TP[1-3]?[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'TAKE\s*PROFIT[1-3]?[@\s]*[:\-]?\s*(\d+\.\d+)',
            r'T/P[1-3]?[@\s]*[:\-]?\s*(\d+\.\d+)',
        ]
        tps = []
        for pat in tp_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                try:
                    tps.append(float(m.group(1)))
                except ValueError:
                    pass
        if tps:
            parsed["take_profits"] = tps
        elif len(all_prices) >= 2 and parsed["entry_prices"] and parsed["stop_loss"]:
            # Remaining prices that are not entry or SL are potential TPs — inferred,
            # so flag it (never auto-traded blindly).
            remaining = [p for p in all_prices if p not in parsed["entry_prices"] and p != parsed["stop_loss"]]
            if remaining:
                parsed["take_profits"] = remaining[:3]
                parsed["tp_inferred"] = True

        # Strategy detection
        strategies = ["FVG", "OB", "ORDER BLOCK", "MSS", "CHOCH", "BOS",
                      "LIQUIDITY", "INDUCEMENT", "ICT", "SMART MONEY", "SMT",
                      "DISPLACEMENT", "MITIGATION", "EQUAL HIGHS", "EQUAL LOWS",
                      "VOLUME IMBALANCE", "BPR", "BRKR", "NWOG", "KILLZONE",
                      "ICT SILVER BULLET", "ICT MIDLNGHT", "ICT NEW YORK OPEN",
                      "ICT LONDON OPEN", "LOKZ", "NYKZ", "TOKZ", "PD ARRAY",
                      "OTE", "OPTIMAL TRADE ENTRY", "IPDA", "STD", "MARKET STRUCTURE"]
        found_strats = []
        for s in strategies:
            if s in t:
                found_strats.append(s)
        if found_strats:
            parsed["strategy"] = ", ".join(found_strats[:3])

        # PARSE COMPLETENESS (not signal quality). This measures how many fields we
        # could extract from the message — it says nothing about whether the trade
        # is good. Inferred (guessed) SL/TP do NOT count, so a message that only
        # looked complete because we filled blanks doesn't read as "high".
        score = 0
        if parsed["symbol"]:
            score += 1
        if parsed["side"]:
            score += 1
        if parsed["entry_prices"]:
            score += 1
        if parsed["stop_loss"] is not None and not parsed.get("sl_inferred"):
            score += 1
        if parsed["take_profits"] and not parsed.get("tp_inferred"):
            score += 1
        if parsed["strategy"]:
            score += 1
        # `confidence` is retained for backward compat but is really parse
        # completeness; the UI/consumer should read it as such.
        if score >= 5:
            parsed["confidence"] = "high"
        elif score >= 3:
            parsed["confidence"] = "medium"
        else:
            parsed["confidence"] = "low"
        parsed["completeness"] = parsed["confidence"]
        parsed["completeness_score"] = score

        return parsed

    # ── Public channel polling (web preview, no bot membership needed) ──

    @staticmethod
    def _html_to_text(fragment: str) -> str:
        """Turn a Telegram message-text HTML fragment into plain text."""
        fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"</p\s*>", "\n", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"<[^>]+>", "", fragment)
        return html_lib.unescape(fragment).strip()

    def _parse_channel_html(self, page: str) -> List[Dict[str, Any]]:
        """Extract messages from a t.me/s/<channel> preview page."""
        messages: List[Dict[str, Any]] = []
        # Each message is a block starting at `<div class="tgme_widget_message ...">`.
        blocks = re.split(r'(?=<div class="tgme_widget_message[ "])', page)
        for block in blocks:
            post = re.search(r'data-post="([^"]+)"', block)
            if not post:
                continue
            text_m = re.search(
                r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>\s*(?:<div class="tgme_widget_message_(?:footer|reply|inline)|<time)',
                block,
                re.DOTALL,
            )
            if not text_m:
                text_m = re.search(
                    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                    block,
                    re.DOTALL,
                )
            if not text_m:
                continue
            text = self._html_to_text(text_m.group(1))
            time_m = re.search(r'<time[^>]*datetime="([^"]+)"', block)
            # Chart images: Telegram serves message photos from telesco.pe as
            # CSS background-image (emoji come from telegram.org — excluded).
            images = [u for u in re.findall(r"background-image:url\('(https://[^']+)'\)", block)
                      if "telesco.pe" in u or "/file/" in u]
            # Keep an image-only post (chart with no caption) — the user wants to analyse it.
            if not text and not images:
                continue
            messages.append({
                "post": post.group(1),          # e.g. "xxictxx/1234"
                "text": text,
                "images": images[:4],
                "datetime": time_m.group(1) if time_m else None,
            })
        return messages

    def _prune_low_conf(self) -> int:
        """Remove already-stored low-confidence, image-less, un-actioned signals so
        the feed doesn't pile up with noise (respects 'reject all low confidence')."""
        removed = 0
        for s in db.get_collection("telegram_signals"):
            if (s.get("confidence") == "low" and not s.get("has_image")
                    and not s.get("acknowledged") and not s.get("planned") and not s.get("auto_traded")):
                if db.delete("telegram_signals", s["id"]):
                    removed += 1
        return removed

    def poll_source_channel(self, channel: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Fetch a public channel's recent posts via its web preview, parse them
        into signals, and store new ones. Works without a bot token/membership."""
        channel = (channel or self.source_channel or "").lstrip("@")
        if not channel:
            return {"ok": False, "error": "No source channel configured", "new_signals": 0}

        url = f"https://t.me/s/{channel}"
        try:
            r = httpx.get(url, timeout=30.0, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; ICTradingOS/1.0)"})
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Fetch failed: {e}", "new_signals": 0}

        pruned = self._prune_low_conf()
        messages = self._parse_channel_html(r.text)[-limit:]
        new_signals = []
        rejected = 0
        for m in messages:
            msg_id = m["post"]  # channel/msgid — globally unique, stable
            if db.find_one("telegram_signals", msg_id):
                continue
            text = m["text"]
            images = m.get("images", [])
            parsed = self._parse_signal(text)
            # Reject low-confidence noise — unless the post carries a chart image
            # (which is worth analysing even with little text).
            if parsed["confidence"] == "low" and not images:
                rejected += 1
                continue
            signal = {
                "id": msg_id,
                "source_channel": channel,
                "source": "web_preview",
                "raw_text": text,
                "images": images,
                "has_image": bool(images),
                "parsed": parsed["symbol"] is not None and parsed["side"] is not None,
                "symbol": parsed["symbol"],
                "side": parsed["side"],
                "entry_prices": parsed["entry_prices"],
                "stop_loss": parsed["stop_loss"],
                "take_profits": parsed["take_profits"],
                "strategy": parsed["strategy"],
                "confidence": parsed["confidence"],
                "completeness": parsed.get("completeness", parsed["confidence"]),
                "sl_inferred": parsed.get("sl_inferred", False),
                "tp_inferred": parsed.get("tp_inferred", False),
                "acknowledged": False,
                "auto_traded": False,
                "planned": False,
                "trade_id": None,
                "message_time": m.get("datetime"),
                "created_at": m.get("datetime") or datetime.utcnow().isoformat(),
                "parsed_at": datetime.utcnow().isoformat(),
            }
            db.insert("telegram_signals", signal)
            new_signals.append(signal)

        self._last_poll_time = datetime.utcnow().isoformat()
        return {"ok": True, "channel": channel, "scanned": len(messages),
                "new_signals": len(new_signals), "rejected_low_conf": rejected,
                "pruned": pruned, "signals": new_signals}

    def poll_all(self) -> Dict[str, Any]:
        """Poll both the bot updates (if configured) and the public source
        channel. Used by the manual 'Poll now' button."""
        source = self.poll_source_channel()
        bot = self.poll() if self.is_configured else {"ok": False, "new_signals": 0, "skipped": "bot not configured"}
        return {
            "ok": source.get("ok") or bot.get("ok"),
            "new_signals": (source.get("new_signals", 0) + bot.get("new_signals", 0)),
            "source": source,
            "bot": bot,
        }

    def poll(self) -> Dict[str, Any]:
        """Poll Telegram for new messages, parse signals, and store them."""
        if not self.is_configured:
            return {"ok": False, "error": "Telegram not configured", "new_signals": 0}

        updates = self._get_updates()
        new_signals = []
        for u in updates:
            msg = u.get("message", {})
            chat = msg.get("chat", {})
            if not self._channel_matches(chat.get("id")):
                continue
            text = msg.get("text", "")
            if not text:
                continue
            msg_id = str(msg.get("message_id", ""))
            # Skip duplicates
            existing = db.find_one("telegram_signals", msg_id)
            if existing:
                continue
            parsed = self._parse_signal(text)
            signal = {
                "id": msg_id,
                "source_channel": str(chat.get("title", chat.get("username", self.channel_id))),
                "raw_text": text,
                "parsed": parsed["symbol"] is not None and parsed["side"] is not None,
                "symbol": parsed["symbol"],
                "side": parsed["side"],
                "entry_prices": parsed["entry_prices"],
                "stop_loss": parsed["stop_loss"],
                "take_profits": parsed["take_profits"],
                "strategy": parsed["strategy"],
                "confidence": parsed["confidence"],
                "completeness": parsed.get("completeness", parsed["confidence"]),
                "sl_inferred": parsed.get("sl_inferred", False),
                "tp_inferred": parsed.get("tp_inferred", False),
                "acknowledged": False,
                "auto_traded": False,
                "trade_id": None,
                "created_at": datetime.utcnow().isoformat(),
                "parsed_at": datetime.utcnow().isoformat(),
            }
            db.insert("telegram_signals", signal)
            new_signals.append(signal)

        self._last_poll_time = datetime.utcnow().isoformat()
        return {"ok": True, "new_signals": len(new_signals), "signals": new_signals}

    def acknowledge(self, signal_id: str) -> Dict[str, Any]:
        """Mark a signal as acknowledged."""
        signal = db.find_one("telegram_signals", signal_id)
        if not signal:
            return {"error": "Signal not found"}
        signal["acknowledged"] = True
        signal["acknowledged_at"] = datetime.utcnow().isoformat()
        db.update("telegram_signals", signal_id, signal)
        return signal

    def auto_trade(self, signal_id: str, account_balance: float = 10000.0, risk_pct: float = 1.0) -> Dict[str, Any]:
        """Create a trade from a parsed signal if valid and not already traded."""
        signal = db.find_one("telegram_signals", signal_id)
        if not signal:
            return {"error": "Signal not found"}
        if signal.get("auto_traded"):
            return {"error": "Signal already auto-traded", "trade_id": signal.get("trade_id")}
        if not signal.get("parsed"):
            return {"error": "Signal not parsed / missing fields"}
        if not signal.get("symbol") or not signal.get("side"):
            return {"error": "Missing symbol or side"}
        if not signal.get("entry_prices"):
            return {"error": "Missing entry prices"}
        if signal.get("stop_loss") is None:
            return {"error": "Missing stop loss"}
        # SAFETY: never auto-place an order on a stop-loss we GUESSED from stray
        # numbers in the message. A wrong stop = wrong risk and wrong position
        # size. Require an explicitly-stated SL; the user can still trade it
        # manually from the Execute page after reviewing.
        if signal.get("sl_inferred"):
            return {"error": "Stop-loss was inferred, not stated in the signal — auto-trade blocked. "
                             "Review and place manually if the inferred SL is correct."}

        entry_price = signal["entry_prices"][0]
        stop_loss = signal["stop_loss"]
        take_profits = signal.get("take_profits", [])
        tp1 = take_profits[0] if len(take_profits) > 0 else None
        tp2 = take_profits[1] if len(take_profits) > 1 else None
        tp3 = take_profits[2] if len(take_profits) > 2 else None

        trade = trade_lifecycle_service.create_trade(
            symbol=signal["symbol"],
            side=signal["side"],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            account_balance=account_balance,
            risk_pct=risk_pct,
            strategy=signal.get("strategy", "Telegram Signal"),
            notes=signal.get("raw_text", "")[:500],
        )
        if trade.get("error"):
            return {"error": trade["error"], "trade": trade}

        signal["auto_traded"] = True
        signal["trade_id"] = trade.get("id")
        signal["auto_traded_at"] = datetime.utcnow().isoformat()
        db.update("telegram_signals", signal_id, signal)
        return {"signal_id": signal_id, "trade_id": trade.get("id"), "trade": trade}

    def discard(self, signal_id: str) -> Dict[str, Any]:
        """Hide an unnecessary post from the feed (kept in the DB so polling won't
        re-add it, but excluded from the default list). Reversible via restore()."""
        signal = db.find_one("telegram_signals", signal_id)
        if not signal:
            return {"error": "Signal not found"}
        db.update("telegram_signals", signal_id, {"discarded": True,
                                                  "discarded_at": datetime.utcnow().isoformat()})
        return {"ok": True, "id": signal_id, "discarded": True}

    def restore(self, signal_id: str) -> Dict[str, Any]:
        """Un-discard a signal (bring it back into the feed)."""
        signal = db.find_one("telegram_signals", signal_id)
        if not signal:
            return {"error": "Signal not found"}
        db.update("telegram_signals", signal_id, {"discarded": False})
        return {"ok": True, "id": signal_id, "discarded": False}

    def get_signals(self, limit: int = 50, acknowledged: Optional[bool] = None,
                    auto_traded: Optional[bool] = None, include_discarded: bool = False) -> List[Dict[str, Any]]:
        """List signals with optional filters. Discarded posts are hidden unless
        include_discarded=True (so the 'kept' feed stays clean)."""
        signals = db.get_collection("telegram_signals")
        if not include_discarded:
            signals = [s for s in signals if not s.get("discarded")]
        if acknowledged is not None:
            signals = [s for s in signals if s.get("acknowledged") == acknowledged]
        if auto_traded is not None:
            signals = [s for s in signals if s.get("auto_traded") == auto_traded]
        # Sort by created_at descending
        signals = sorted(signals, key=lambda x: x.get("created_at", ""), reverse=True)
        return signals[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregated statistics about signals."""
        signals = db.get_collection("telegram_signals")
        total = len(signals)
        parsed = len([s for s in signals if s.get("parsed")])
        acknowledged = len([s for s in signals if s.get("acknowledged")])
        auto_traded = len([s for s in signals if s.get("auto_traded")])
        return {
            "total": total,
            "parsed": parsed,
            "acknowledged": acknowledged,
            "auto_traded": auto_traded,
            "configured": self.is_configured,
            "channel_id": self.channel_id,
            "source_channel": self.source_channel,
            "source_poll_available": bool(self.source_channel),
            "last_poll_time": self._last_poll_time,
        }

    def configure(self, token: str, channel_id: str) -> Dict[str, Any]:
        """Set runtime Telegram credentials."""
        settings.TELEGRAM_BOT_TOKEN = token
        settings.TELEGRAM_CHANNEL_ID = channel_id
        os.environ["TELEGRAM_BOT_TOKEN"] = token
        os.environ["TELEGRAM_CHANNEL_ID"] = channel_id
        return {"configured": self.is_configured, "channel_id": channel_id}


telegram_service = TelegramService()
