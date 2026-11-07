"""
RM Media | Result & Momentum - Telegram bot  (PHASE 1: secure core)

Scope of Phase 1: /start, /help, /terms, /deletemydata, basic menus, service & package
prices, language switch.  No orders / receipts / reviews / broadcast yet (Phase 2).

Safety design
  * Rate limiting   : per-user cooldown + sliding window + temporary mute, and a global
                      pacer (max updates/second).  Optional PTB AIORateLimiter on top
                      (needs:  pip install "python-telegram-bot[rate-limiter]").
  * Error handling  : every handler is wrapped (guarded) + one global error handler.
                      Flood-wait (RetryAfter), Conflict, network errors, "message is not
                      modified" and parse errors are handled without crashing.
  * Sanitization    : everything dynamic goes through html.escape; parse_mode is HTML only;
                      if Telegram still rejects an entity, the message is re-sent as plain text.
  * Secrets         : only os.getenv(); nothing sensitive is written in this file or logged.
  * Startup safety  : drop_pending_updates (no backlog flood after downtime) and a crash
                      back-off (no rapid restart loop against the Telegram API).
  * Copy            : no fake client counters, no fake scarcity.  A crossed-out price is shown
                      ONLY where you set a real regular list price ("old") in PACKAGES.

Required env vars (Render -> Environment):
  BOT_TOKEN, ADMIN_USER_ID   (comma separated if more than one admin)
Optional:
  CONTACT_USERNAME (without @), PORTFOLIO_URL (https://...), SUPPORT_PHONE,
  CBE_ACCOUNT, CBE_NAME, TELEBIRR_NUMBER, TELEBIRR_NAME   (payment screen appears only if all 4 set)
  TERMS_DELIVERY, TERMS_REVISIONS, TERMS_REFUND            (one line each, shown in /terms)
  DB_FILE, PORT, RENDER_EXTERNAL_URL (self-ping, every 10 min)

requirements.txt:
  python-telegram-bot[rate-limiter]>=20.7
  flask
"""

import asyncio
import html
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.request
from collections import deque
from contextlib import closing
from functools import wraps
from threading import Thread

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import (
    BadRequest,
    Conflict,
    Forbidden,
    InvalidToken,
    NetworkError,
    RetryAfter,
    TelegramError,
    TimedOut,
)
from telegram.ext import (
    AIORateLimiter,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Logging (token can leak through httpx request logs -> silence them)
# ---------------------------------------------------------------------------


class RedactingFormatter(logging.Formatter):
    """Masks anything that looks like a bot token in EVERY log line, including tracebacks."""

    _TOKEN = re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}")

    def format(self, record):
        text = super().format(record)
        token = os.getenv("BOT_TOKEN", "").strip()
        if token:
            text = text.replace(token, "<token>")
        return self._TOKEN.sub("<token>", text)


_handler = logging.StreamHandler()
_handler.setFormatter(RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
for _noisy in ("httpx", "httpcore", "telegram.ext.Application", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logger = logging.getLogger("rm_media_bot")


# ---------------------------------------------------------------------------
# Configuration - ONLY from environment variables
# ---------------------------------------------------------------------------
def env(name, default=""):
    return (os.getenv(name) or default).strip()


def parse_admin_ids(raw):
    ids = []
    for part in re.split(r"[,\s]+", raw or ""):
        if part.isdigit():
            ids.append(int(part))
    return ids


def safe_https_url(raw):
    raw = (raw or "").strip()
    return raw if re.fullmatch(r"https://[^\s<>\"']{4,300}", raw) else ""


BOT_TOKEN = env("BOT_TOKEN")
ADMIN_IDS = parse_admin_ids(env("ADMIN_USER_ID") or env("ADMIN_USER_IDS"))
DB_FILE = env("DB_FILE", "rm_media_advanced.db")
PORT = int(env("PORT", "8080") or 8080)

_contact = env("CONTACT_USERNAME").lstrip("@")
CONTACT_USERNAME = _contact if re.fullmatch(r"[A-Za-z0-9_]{4,32}", _contact) else ""
PORTFOLIO_URL = safe_https_url(env("PORTFOLIO_URL"))
SUPPORT_PHONE = re.sub(r"[^\d+ ]", "", env("SUPPORT_PHONE"))[:20]

CBE_ACCOUNT = env("CBE_ACCOUNT")
CBE_NAME = env("CBE_NAME")
TELEBIRR_NUMBER = env("TELEBIRR_NUMBER")
TELEBIRR_NAME = env("TELEBIRR_NAME")
PAYMENT_CONFIGURED = all([CBE_ACCOUNT, CBE_NAME, TELEBIRR_NUMBER, TELEBIRR_NAME])

TERMS_DELIVERY = env("TERMS_DELIVERY")[:300]
TERMS_REVISIONS = env("TERMS_REVISIONS")[:300]
TERMS_REFUND = env("TERMS_REFUND")[:300]
SELF_PING_URL = safe_https_url(env("RENDER_EXTERNAL_URL"))

BOT_TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}")


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069\u200e\u200f]")
_TAG_RE = re.compile(r"<[^>]+>")


def h(value):
    """HTML-escape any dynamic value (names, prices, env values...)."""
    return html.escape(str(value), quote=False)


def clean_name(name):
    name = _CONTROL_RE.sub("", name or "").strip()
    return (name or "Customer")[:64]


def strip_tags(text):
    return html.unescape(_TAG_RE.sub("", text))


def redact(text):
    """Never let the bot token appear in logs / admin alerts."""
    text = str(text)
    if BOT_TOKEN:
        text = text.replace(BOT_TOKEN, "<token>")
    return BOT_TOKEN_RE.sub("<token>", text)


def etb(n):
    return f"{int(n):,} ETB"


# ---------------------------------------------------------------------------
# Database (same schema as the full bot -> compatible with the existing DB)
# ---------------------------------------------------------------------------
def init_db():
    with closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone_number TEXT,
                language TEXT DEFAULT 'am',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                full_name TEXT,
                rating INTEGER,
                review_text TEXT,
                approved INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_name TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("PRAGMA table_info(users)")
        if "phone_number" not in [c[1] for c in cur.fetchall()]:
            cur.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
        conn.commit()


def db_register_user(user):
    try:
        with closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)",
                (user.id, clean_name(user.full_name)),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error("DB register failed: %s", e)


def db_get_lang(user_id):
    try:
        with closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            row = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row and row[0] in ("am", "en") else "am"
    except sqlite3.Error as e:
        logger.error("DB lang read failed: %s", e)
        return "am"


def db_set_lang(user, lang):
    if lang not in ("am", "en"):
        return
    try:
        with closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user.id, clean_name(user.full_name)))
            conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user.id))
            conn.commit()
    except sqlite3.Error as e:
        logger.error("DB lang write failed: %s", e)


def db_delete_user(user_id):
    try:
        with closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("DB delete failed: %s", e)
        return False


def db_stats():
    with closing(sqlite3.connect(DB_FILE, timeout=10)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        am = conn.execute("SELECT COUNT(*) FROM users WHERE language = 'am' OR language IS NULL").fetchone()[0]
        en = conn.execute("SELECT COUNT(*) FROM users WHERE language = 'en'").fetchone()[0]
    return total, am, en


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
class UserLimiter:
    """Per-user: minimum gap between actions + sliding window + temporary mute."""

    def __init__(self, min_interval=0.5, window=10.0, max_actions=12, mute_for=20.0, warn_every=20.0):
        self.min_interval = min_interval
        self.window = window
        self.max_actions = max_actions
        self.mute_for = mute_for
        self.warn_every = warn_every
        self._state = {}

    def _get(self, uid, now):
        st = self._state.get(uid)
        if st is None:
            if len(self._state) > 5000:
                self._purge(now)
            st = self._state[uid] = {"hits": deque(), "last": float("-inf"), "muted_until": 0.0, "last_warn": float("-inf")}
        return st

    def _purge(self, now):
        for uid in [u for u, s in self._state.items() if now - max(s["last"], 0.0) > 600 and now > s["muted_until"]]:
            self._state.pop(uid, None)

    def check(self, uid, now=None):
        """Return 'ok', 'slow' (too fast, drop) or 'muted' (temporarily blocked)."""
        now = time.monotonic() if now is None else now
        st = self._get(uid, now)
        if now < st["muted_until"]:
            return "muted"
        hits = st["hits"]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if now - st["last"] < self.min_interval:
            return "slow"
        if len(hits) >= self.max_actions:
            st["muted_until"] = now + self.mute_for
            hits.clear()
            return "muted"
        hits.append(now)
        st["last"] = now
        return "ok"

    def should_warn(self, uid, now=None):
        """True at most once per warn_every seconds (so warnings never become a flood)."""
        now = time.monotonic() if now is None else now
        st = self._get(uid, now)
        if now - st["last_warn"] >= self.warn_every:
            st["last_warn"] = now
            return True
        return False


class GlobalPacer:
    """Keeps the whole bot under a maximum number of handled updates per second."""

    def __init__(self, per_second=15):
        self.gap = 1.0 / per_second
        self._next = 0.0
        self._lock = None

    async def wait(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            if delay > 0:
                await asyncio.sleep(delay)
                now = time.monotonic()
            self._next = max(now, self._next) + self.gap


LIMITER = UserLimiter()
PACER = GlobalPacer(per_second=15)

# ---------------------------------------------------------------------------
# Safe sending helpers (parse-error fallback, flood-wait aware)
# ---------------------------------------------------------------------------
def _retry_seconds(exc):
    ra = getattr(exc, "retry_after", 5)
    try:
        ra = ra.total_seconds() if hasattr(ra, "total_seconds") else float(ra)
    except (TypeError, ValueError):
        ra = 5.0
    return min(max(ra, 1.0), 60.0)


def _is_parse_error(exc):
    m = str(exc).lower()
    return "parse entities" in m or "can't parse" in m or "unsupported start tag" in m


async def safe_edit(query, text, markup=None):
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    except BadRequest as e:
        m = str(e).lower()
        if "not modified" in m:
            return
        if _is_parse_error(e):
            logger.warning("HTML rejected by Telegram, resending as plain text: %s", redact(e))
            await query.edit_message_text(strip_tags(text), reply_markup=markup)
        elif "message to edit not found" in m or "can't be edited" in m:
            await query.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            raise
    except RetryAfter as e:
        await asyncio.sleep(_retry_seconds(e))
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")


async def safe_reply(update, text, markup=None):
    msg = update.effective_message
    if msg is None:
        return
    try:
        await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")
    except BadRequest as e:
        if _is_parse_error(e):
            logger.warning("HTML rejected by Telegram, resending as plain text: %s", redact(e))
            await msg.reply_text(strip_tags(text), reply_markup=markup)
        else:
            raise
    except RetryAfter as e:
        await asyncio.sleep(_retry_seconds(e))
        await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Global error handling
# ---------------------------------------------------------------------------
_last_admin_alert = float("-inf")
_last_user_notice = {}


async def handle_exception(update, context, exc):
    """Single place that decides what to do with ANY exception. Never raises."""
    global _last_admin_alert
    try:
        if isinstance(exc, RetryAfter):
            wait = _retry_seconds(exc)
            logger.warning("Telegram flood-wait: sleeping %.0fs", wait)
            await asyncio.sleep(wait)
            return
        if isinstance(exc, Conflict):
            logger.warning("Conflict: another instance is polling with this token (deploy overlap?).")
            return
        if isinstance(exc, (NetworkError, TimedOut)):
            logger.warning("Network problem (will retry automatically): %s", redact(exc))
            return
        if isinstance(exc, Forbidden):
            logger.info("User blocked the bot / no rights: %s", redact(exc))
            return
        if isinstance(exc, BadRequest) and "not modified" in str(exc).lower():
            return

        logger.error("Unhandled error: %s", redact(repr(exc)), exc_info=exc)

        now = time.monotonic()
        if ADMIN_IDS and context is not None and now - _last_admin_alert > 600:
            _last_admin_alert = now
            note = f"⚠️ Bot error: {type(exc).__name__}: {redact(str(exc))[:300]}"
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=note)
                except TelegramError:
                    pass

        if isinstance(update, Update) and update.effective_user and update.effective_chat:
            uid = update.effective_user.id
            if now - _last_user_notice.get(uid, -1e9) > 60:
                _last_user_notice[uid] = now
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="⚠️ ችግር ተፈጥሯል፤ እባክዎ ትንሽ ቆይተው ይሞክሩ። / Something went wrong, please try again shortly.",
                    )
                except TelegramError:
                    pass
    except Exception:  # the error handler itself must never crash
        logger.exception("error handler failed")


async def error_handler(update, context):
    await handle_exception(update, context, context.error)


def guarded(fn):
    """Rate-limit + global pacing + try/except around every handler."""

    @wraps(fn)
    async def wrapper(update, context):
        try:
            user = update.effective_user
            if user is None or user.is_bot:
                return
            if user.id not in ADMIN_IDS:
                verdict = LIMITER.check(user.id)
                if verdict != "ok":
                    if LIMITER.should_warn(user.id):
                        if update.callback_query:
                            await update.callback_query.answer("⏳ እባክዎ ትንሽ ቀስ ይበሉ / Please slow down", show_alert=False)
                        elif verdict == "muted" and update.effective_message:
                            await update.effective_message.reply_text("⏳ እባክዎ ትንሽ ቆይተው ይሞክሩ / Please wait a few seconds.")
                    return
            await PACER.wait()
            await fn(update, context)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await handle_exception(update, context, exc)

    return wrapper


# ---------------------------------------------------------------------------
# Content: texts and packages  (HTML, bilingual)
# ---------------------------------------------------------------------------
# old = regular list price shown crossed out.  Set old=None unless it is a REAL list price.
PACKAGES = {
    "design": {
        "emoji": "🖼",
        "title": {"am": "ዲዛይን እና ታምብሌን", "en": "Design & Thumbnails"},
        "tagline": {
            "am": "• የዩቲዩብ እና ቲክቶክ ታምብሌኖች\n• የፌስቡክ/ቴሌግራም ፖስተሮች",
            "en": "• YouTube & TikTok thumbnails\n• Facebook / Telegram posters",
        },
        "items": [
            {"key": "flyer", "emoji": "🎯", "name": "Single Flyer (Starter)", "price": 990, "old": None,
             "includes": {"am": "1 ፍላየር", "en": "1 flyer"}},
            {"key": "growth", "emoji": "🔥", "name": "Growth Starter Pack", "price": 1990, "old": 4000,
             "includes": {"am": "3 ፖስተሮች", "en": "3 posters"}},
            {"key": "pro", "emoji": "💎", "name": "Pro Business Bundle", "price": 2990, "old": 6500,
             "includes": {"am": "5 ፖስተሮች + 1 ሽፋን (Cover)", "en": "5 posters + 1 cover"}},
        ],
    },
    "video": {
        "emoji": "🎬",
        "title": {"am": "ቪዲዮ ፕሮዳክሽን", "en": "Video Production"},
        "tagline": {
            "am": "• የማስታወቂያ ቪዲዮዎች\n• የምረቃ እና የልደት ቪዲዮ ኤዲቲንግ",
            "en": "• Promo videos\n• Graduation & birthday video editing",
        },
        "items": [
            {"key": "reel", "emoji": "⚡", "name": "Promo Reel (30 sec)", "price": 2490, "old": 5000,
             "includes": {"am": "የ30 ሰከንድ የማስታወቂያ ሪል", "en": "30-second promo reel"}},
            {"key": "standard", "emoji": "🚀", "name": "Standard Video Edit", "price": 4490, "old": 8000,
             "includes": {"am": "ስታንዳርድ የቪዲዮ ኤዲቲንግ", "en": "Standard video edit"}},
        ],
    },
    "social": {
        "emoji": "📱",
        "title": {"am": "ሶሻል ሚዲያ ግብይት (SMM)", "en": "Social Media Marketing (SMM)"},
        "tagline": {
            "am": "• የገጽ አስተዳደር\n• የይዘት እቅድ",
            "en": "• Page management\n• Content planning",
        },
        "items": [
            {"key": "starter", "emoji": "⭐", "name": "SMM Starter Plan", "price": 4990, "old": 10000, "monthly": True,
             "includes": {"am": "የሶሻል ሚዲያ ጀማሪ እቅድ (በወር)", "en": "Social media starter plan (monthly)"}},
        ],
    },
}

T = {
    "am": {
        "welcome": ("👋 እንኳን ወደ <b>RM Media | Result &amp; Momentum</b> በደህና መጡ!\n\n"
                    "ግራፊክ ዲዛይን፣ ቪዲዮ ኤዲቲንግ እና ሶሻል ሚዲያ ግብይት አገልግሎቶችን እናቀርባለን። "
                    "ዋጋዎቻችን ከታች በግልጽ ተዘርዝረዋል።\n\n👇 ከታች ካሉት አማራጮች ይምረጡ፦"),
        "m_portfolio": "🎨 ፖርትፎሊዮ", "m_contact": "💬 ያነጋግሩን", "m_howto": "🧭 እንዴት ማዘዝ ይቻላል?",
        "m_pay": "💳 የክፍያ መረጃ", "m_terms": "📄 ደንቦች", "m_help": "❓ እገዛ", "m_lang": "🌐 ቋንቋ / Language",
        "back": "🔙 ወደ ዋናው ማውጫ", "back_pkgs": "🔙 ወደ ፓኬጆች", "order_chat": "💬 በቀጥታ ለማዘዝ ያነጋግሩን",
        "choose": "💎 ፓኬጅዎን ይምረጡ፦", "only": "ብቻ", "off": "ቅናሽ", "month": "/ በወር", "includes": "የሚያካትተው",
        "price_note": "ℹ️ ዋጋዎች በኢትዮጵያ ብር (ETB) ናቸው። የተሰረዘው ዋጋ መደበኛ የዋጋ ዝርዝራችን ነው።",
        "contact_us": "ለማዘዝ ወይም ለጥያቄ ያነጋግሩን",
        "howto": ("🧭 <b>እንዴት ማዘዝ ይቻላል?</b>\n\n"
                  "1️⃣ ከአገልግሎቶች ፓኬጅ ይምረጡ።\n"
                  "2️⃣ በቀጥታ መልእክት ያነጋግሩን።\n"
                  "3️⃣ የሥራውን ዝርዝር፣ የመጨረሻ ዋጋ እና የማስረከቢያ ጊዜ እናረጋግጣለን።\n"
                  "4️⃣ በኦፊሴላዊው የክፍያ መረጃ ብቻ ይክፈሉ።\n"
                  "5️⃣ ደረሰኙን በቀጥታ መልእክት ይላኩ፤ ክፍያውን አረጋግጠን ሥራ እንጀምራለን።"),
        "pay_title": "💳 <b>የክፍያ መረጃ</b>",
        "pay_warn": ("⚠️ ከመክፈልዎ በፊት የሥራው ዝርዝር እና የመጨረሻ ዋጋ ከእኛ ጋር መረጋገጡን፣ እንዲሁም የሒሳብ ስሙ ከታች ካለው ጋር መመሳሰሉን ያረጋግጡ። "
                     "ደረሰኙን በቀጥታ መልእክት ይላኩ።"),
        "lang_title": "🌐 ቋንቋ ይምረጡ / Choose your language", "lang_saved": "✅ ቋንቋ ተቀይሯል",
        "help": ("❓ <b>እገዛ</b>\n\n"
                 "/start — ዋና ማውጫ\n/help — ይህ መልእክት\n/terms — የአገልግሎት ደንቦች እና የግላዊነት መረጃ\n"
                 "/deletemydata — በቦቱ ውስጥ የተቀመጠውን መረጃዎን መሰረዝ\n\n"
                 "ለማዘዝ ወይም ለጥያቄ በ«ያነጋግሩን» ቁልፍ በቀጥታ ያግኙን።"),
        "unknown": "ይቅርታ፣ ይህን መልእክት አልተረዳሁም። ከታች ያለውን ማውጫ ይጠቀሙ ወይም /help ይላኩ።",
        "delete_ask": "🗑 በቦቱ ውስጥ የተቀመጠውን መረጃዎን (የቴሌግራም ID፣ ስም፣ ቋንቋ) እንሰርዝ?",
        "delete_yes": "✅ አዎ፣ ሰርዝ", "delete_no": "❌ አይ", "delete_done": "✅ መረጃዎ ተሰርዟል።", "delete_cancel": "ተሰርዟል፤ ምንም አልተቀየረም።",
        "delete_fail": "⚠️ አሁን መሰረዝ አልተቻለም፤ እባክዎ ቆይተው ይሞክሩ።",
        "terms_title": "📄 <b>የአገልግሎት ደንቦች እና ግላዊነት</b>",
        "terms_body": ("<b>1. አገልግሎት እና ዋጋ</b>\nዋጋዎች በቦቱ ውስጥ በኢትዮጵያ ብር (ETB) ይታያሉ። የተሰረዘ ዋጋ መደበኛ የዋጋ ዝርዝራችን ነው። "
                       "የሥራው ዝርዝር እና የመጨረሻ ዋጋ ከክፍያ በፊት ከእርስዎ ጋር ይረጋገጣል።\n\n"
                       "<b>2. ማዘዝ እና ክፍያ</b>\nትዕዛዞች በቀጥታ መልእክት ይቀበላሉ። ክፍያ በኦፊሴላዊው የክፍያ መረጃ ብቻ ይፈጸማል፤ ከመክፈልዎ በፊት የሒሳብ ስሙን ያረጋግጡ።\n\n"),
        "terms_default": "<b>3. ማስረከቢያ፣ ማሻሻያ እና ገንዘብ ተመላሽ</b>\nየማስረከቢያ ጊዜ፣ የማሻሻያ ብዛት እና የገንዘብ ተመላሽ ሁኔታዎች ከክፍያ በፊት በጽሑፍ ከእርስዎ ጋር ይስማማሉ።",
        "terms_custom": "<b>3. ማስረከቢያ፣ ማሻሻያ እና ገንዘብ ተመላሽ</b>",
        "t_delivery": "ማስረከቢያ", "t_revisions": "ማሻሻያ", "t_refund": "ተመላሽ",
        "terms_data": ("\n\n<b>4. የእርስዎ መረጃ</b>\nቦቱን ለማስኬድ የምናስቀምጠው የቴሌግራም ID፣ የሚታየው ስምዎ እና የቋንቋ ምርጫዎን ብቻ ነው። "
                       "መረጃዎን አንሸጥም ወይም ለሌላ አናካፍልም። በ /deletemydata መሰረዝ ይችላሉ (ለሂሳብ አያያዝ የሚያስፈልጉ የትዕዛዝ መዝገቦች ሊቆዩ ይችላሉ)።\n\n"
                       "<b>5. ቴሌግራም</b>\nየቦቱ አጠቃቀም የቴሌግራም የአገልግሎት ደንቦችንም ይከተላል።"),
    },
    "en": {
        "welcome": ("👋 Welcome to <b>RM Media | Result &amp; Momentum</b>!\n\n"
                    "We offer graphic design, video editing and social media marketing. "
                    "Our prices are listed openly below.\n\n👇 Choose an option:"),
        "m_portfolio": "🎨 Portfolio", "m_contact": "💬 Contact us", "m_howto": "🧭 How to order",
        "m_pay": "💳 Payment info", "m_terms": "📄 Terms", "m_help": "❓ Help", "m_lang": "🌐 Language / ቋንቋ",
        "back": "🔙 Main menu", "back_pkgs": "🔙 Back to packages", "order_chat": "💬 Order via direct chat",
        "choose": "💎 Choose your package:", "only": "only", "off": "OFF", "month": "/ Month", "includes": "Includes",
        "price_note": "ℹ️ Prices are in Ethiopian Birr (ETB). A crossed-out price is our regular list price.",
        "contact_us": "Contact us to order or ask a question",
        "howto": ("🧭 <b>How to order</b>\n\n"
                  "1️⃣ Pick a package from Services.\n"
                  "2️⃣ Message us directly.\n"
                  "3️⃣ We confirm the scope, final price and delivery time with you.\n"
                  "4️⃣ Pay using the official payment details only.\n"
                  "5️⃣ Send the receipt in the chat; we verify it and start the work."),
        "pay_title": "💳 <b>Payment info</b>",
        "pay_warn": ("⚠️ Before paying, make sure the scope and final price are confirmed with us, and that the account name matches the one below. "
                     "Send the receipt in our direct chat."),
        "lang_title": "🌐 Choose your language / ቋንቋ ይምረጡ", "lang_saved": "✅ Language updated",
        "help": ("❓ <b>Help</b>\n\n"
                 "/start — main menu\n/help — this message\n/terms — service terms and privacy\n"
                 "/deletemydata — delete the data this bot stores about you\n\n"
                 "To order or ask a question, use the “Contact us” button."),
        "unknown": "Sorry, I didn't understand that. Use the menu below or send /help.",
        "delete_ask": "🗑 Delete the data this bot stores about you (Telegram ID, name, language)?",
        "delete_yes": "✅ Yes, delete", "delete_no": "❌ No", "delete_done": "✅ Your data has been deleted.", "delete_cancel": "Cancelled, nothing changed.",
        "delete_fail": "⚠️ Could not delete right now, please try again later.",
        "terms_title": "📄 <b>Service terms &amp; privacy</b>",
        "terms_body": ("<b>1. Services and prices</b>\nPrices are shown in the bot in Ethiopian Birr (ETB). A crossed-out price is our regular list price. "
                       "The scope and final price are confirmed with you before you pay.\n\n"
                       "<b>2. Ordering and payment</b>\nOrders are taken in the direct chat. Pay only to the official payment details and check the account name first.\n\n"),
        "terms_default": "<b>3. Delivery, revisions and refunds</b>\nDelivery time, number of revisions and refund conditions are agreed with you in writing before payment.",
        "terms_custom": "<b>3. Delivery, revisions and refunds</b>",
        "t_delivery": "Delivery", "t_revisions": "Revisions", "t_refund": "Refunds",
        "terms_data": ("\n\n<b>4. Your data</b>\nTo run the bot we store only your Telegram ID, display name and language choice. "
                       "We do not sell or share it. You can delete it with /deletemydata (order records needed for bookkeeping may be kept).\n\n"
                       "<b>5. Telegram</b>\nUse of this bot is also subject to Telegram's own terms."),
    },
}


def L(lang):
    return lang if lang in ("am", "en") else "am"


def find_package(service, key):
    svc = PACKAGES.get(service)
    if not svc:
        return None
    for p in svc["items"]:
        if p["key"] == key:
            return svc, p
    return None


def discount_pct(p):
    return int(round((p["old"] - p["price"]) * 100 / p["old"])) if p.get("old") else 0


def price_line(p, t):
    period = f" {h(t['month'])}" if p.get("monthly") else ""
    if p.get("old"):
        return f"<s>{etb(p['old'])}</s> → <b>{etb(p['price'])}{period}</b> {h(t['only'])}"
    return f"<b>{etb(p['price'])}{period}</b>"


def discount_line(p, t):
    pct = discount_pct(p)
    return f"🎁 <b>{pct}% {h(t['off'])}</b>" if pct else ""


def from_price(service):
    return f"{min(p['price'] for p in PACKAGES[service]['items']):,}"


def contact_button(t, text=None):
    if not CONTACT_USERNAME:
        return None
    return InlineKeyboardButton(text or t["m_contact"], url=f"https://t.me/{CONTACT_USERNAME}")


def main_menu(lang):
    lang = L(lang)
    t = T[lang]
    rows = []
    for service, svc in PACKAGES.items():
        label = f"{svc['emoji']} {svc['title'][lang]} ({'ከ' if lang == 'am' else 'from'} {from_price(service)} ETB)"
        rows.append([InlineKeyboardButton(label, callback_data=f"svc_{service}")])
    if PORTFOLIO_URL:
        rows.append([InlineKeyboardButton(t["m_portfolio"], url=PORTFOLIO_URL)])
    cb = contact_button(t)
    if cb:
        rows.append([cb])
    row = [InlineKeyboardButton(t["m_howto"], callback_data="howto")]
    if PAYMENT_CONFIGURED:
        row.append(InlineKeyboardButton(t["m_pay"], callback_data="pay"))
    rows.append(row)
    rows.append([InlineKeyboardButton(t["m_terms"], callback_data="terms"), InlineKeyboardButton(t["m_help"], callback_data="help")])
    rows.append([InlineKeyboardButton(t["m_lang"], callback_data="lang")])
    return InlineKeyboardMarkup(rows)


def back_menu(lang, extra_rows=None):
    rows = list(extra_rows or [])
    rows.append([InlineKeyboardButton(T[L(lang)]["back"], callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def welcome_page(lang):
    return T[L(lang)]["welcome"], main_menu(lang)


def service_page(service, lang):
    lang = L(lang)
    t = T[lang]
    svc = PACKAGES[service]
    lines = [f"{svc['emoji']} <b>{h(svc['title'][lang])}</b>", "", h(svc["tagline"][lang]), "", h(t["choose"]), ""]
    rows = []
    for p in svc["items"]:
        lines.append(f"{p['emoji']} <b>{h(p['name'])}</b>")
        lines.append(f"   {h(p['includes'][lang])}")
        disc = discount_line(p, t)
        lines.append(f"   {price_line(p, t)}" + (f"  {disc}" if disc else ""))
        lines.append("")
        rows.append([InlineKeyboardButton(f"{p['emoji']} {p['name']} · {etb(p['price'])}", callback_data=f"pkg_{service}_{p['key']}")])
    lines.append(h(t["price_note"]))
    return "\n".join(lines), back_menu(lang, rows)


def package_page(service, key, lang):
    found = find_package(service, key)
    if not found:
        return None
    lang = L(lang)
    t = T[lang]
    svc, p = found
    lines = [f"{p['emoji']} <b>{h(p['name'])}</b>", "", f"📦 {h(t['includes'])}: {h(p['includes'][lang])}", f"💰 {price_line(p, t)}"]
    disc = discount_line(p, t)
    if disc:
        lines.append(disc)
    lines += ["", h(t["price_note"])]
    rows = []
    cb = contact_button(t, t["order_chat"])
    if cb:
        rows.append([cb])
    rows.append([InlineKeyboardButton(t["back_pkgs"], callback_data=f"svc_{service}")])
    return "\n".join(lines), back_menu(lang, rows)


def payment_page(lang):
    t = T[L(lang)]
    text = (
        f"{t['pay_title']}\n\n"
        f"🔹 <b>CBE</b>: <code>{h(CBE_ACCOUNT)}</code>\n👤 {h(CBE_NAME)}\n\n"
        f"🔹 <b>Telebirr</b>: <code>{h(TELEBIRR_NUMBER)}</code>\n👤 {h(TELEBIRR_NAME)}\n\n"
        f"{h(t['pay_warn'])}"
    )
    rows = []
    cb = contact_button(t)
    if cb:
        rows.append([cb])
    return text, back_menu(lang, rows)


def terms_page(lang):
    lang = L(lang)
    t = T[lang]
    custom = [(t["t_delivery"], TERMS_DELIVERY), (t["t_revisions"], TERMS_REVISIONS), (t["t_refund"], TERMS_REFUND)]
    custom = [(label, value) for label, value in custom if value]
    if custom:
        section = t["terms_custom"] + "\n" + "\n".join(f"• {h(label)}: {h(value)}" for label, value in custom)
    else:
        section = t["terms_default"]
    text = f"{t['terms_title']}\n\n{t['terms_body']}{section}{t['terms_data']}"
    rows = []
    cb = contact_button(t)
    if cb:
        rows.append([cb])
    return text, back_menu(lang, rows)


def help_page(lang):
    t = T[L(lang)]
    rows = []
    cb = contact_button(t)
    if cb:
        rows.append([cb])
    return t["help"], back_menu(lang, rows)


def howto_page(lang):
    t = T[L(lang)]
    rows = []
    cb = contact_button(t, t["order_chat"])
    if cb:
        rows.append([cb])
    return t["howto"], back_menu(lang, rows)


def lang_page(lang):
    t = T[L(lang)]
    rows = [[InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="setlang_am"), InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
            [InlineKeyboardButton(t["back"], callback_data="menu")]]
    return t["lang_title"], InlineKeyboardMarkup(rows)


def delete_page(lang):
    t = T[L(lang)]
    rows = [[InlineKeyboardButton(t["delete_yes"], callback_data="del_yes"), InlineKeyboardButton(t["delete_no"], callback_data="del_no")]]
    return t["delete_ask"], InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
@guarded
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_register_user(user)
    text, markup = welcome_page(db_get_lang(user.id))
    await safe_reply(update, text, markup)


@guarded
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, markup = help_page(db_get_lang(update.effective_user.id))
    await safe_reply(update, text, markup)


@guarded
async def cmd_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, markup = terms_page(db_get_lang(update.effective_user.id))
    await safe_reply(update, text, markup)


@guarded
async def cmd_deletemydata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, markup = delete_page(db_get_lang(update.effective_user.id))
    await safe_reply(update, text, markup)


@guarded
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return  # silent for everyone else
    try:
        total, am, en = db_stats()
    except sqlite3.Error as e:
        logger.error("stats failed: %s", e)
        await update.effective_message.reply_text("DB error, see logs.")
        return
    await update.effective_message.reply_text(f"📊 Users: {total}\n🇪🇹 am: {am}\n🇬🇧 en: {en}")


@guarded
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db_get_lang(update.effective_user.id)
    await safe_reply(update, T[L(lang)]["unknown"], main_menu(lang))


_CALLBACK_RE = re.compile(r"^[a-z0-9_]{1,40}$")


@guarded
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""
    try:
        await query.answer()
    except BadRequest:
        pass  # old / already answered query
    if not _CALLBACK_RE.match(data):
        return

    lang = db_get_lang(user.id)
    t = T[L(lang)]

    if data == "menu":
        text, markup = welcome_page(lang)
    elif data.startswith("svc_") and data[4:] in PACKAGES:
        text, markup = service_page(data[4:], lang)
    elif data.startswith("pkg_"):
        parts = data.split("_")
        page = package_page(parts[1], parts[2], lang) if len(parts) == 3 else None
        text, markup = page if page else welcome_page(lang)
    elif data == "howto":
        text, markup = howto_page(lang)
    elif data == "pay" and PAYMENT_CONFIGURED:
        text, markup = payment_page(lang)
    elif data == "terms":
        text, markup = terms_page(lang)
    elif data == "help":
        text, markup = help_page(lang)
    elif data == "lang":
        text, markup = lang_page(lang)
    elif data in ("setlang_am", "setlang_en"):
        db_set_lang(user, data[-2:])
        lang = db_get_lang(user.id)
        text, markup = T[lang]["lang_saved"] + "\n\n" + T[lang]["welcome"], main_menu(lang)
    elif data == "del_yes":
        ok = db_delete_user(user.id)
        text = t["delete_done"] if ok else t["delete_fail"]
        markup = None
    elif data == "del_no":
        text, markup = t["delete_cancel"], None
    else:
        text, markup = welcome_page(lang)

    await safe_edit(query, text, markup)


# ---------------------------------------------------------------------------
# Keep-alive web server (Render) + optional self-ping
# ---------------------------------------------------------------------------
web = Flask(__name__)


@web.route("/")
def home():
    return "OK", 200


def run_web():
    web.run(host="0.0.0.0", port=PORT)


def self_ping_loop():
    while True:
        time.sleep(600)
        try:
            urllib.request.urlopen(SELF_PING_URL, timeout=10).read(16)
        except Exception as e:  # never crash the thread
            logger.warning("self-ping failed: %s", redact(e))


def start_background_threads():
    Thread(target=run_web, daemon=True).start()
    if SELF_PING_URL:
        Thread(target=self_ping_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def validate_config():
    problems = []
    if not BOT_TOKEN_RE.fullmatch(BOT_TOKEN or ""):
        problems.append("BOT_TOKEN is missing or malformed")
    if not ADMIN_IDS:
        problems.append("ADMIN_USER_ID is missing (numeric Telegram ID)")
    return problems


def build_application():
    builder = ApplicationBuilder().token(BOT_TOKEN)
    try:  # extra layer: PTB's own flood-aware limiter (needs the [rate-limiter] extra)
        builder = builder.rate_limiter(AIORateLimiter(overall_max_rate=20, max_retries=2))
    except Exception as e:
        logger.warning("AIORateLimiter not active (%s). Install python-telegram-bot[rate-limiter].", type(e).__name__)
    app = builder.build()

    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", cmd_start, filters=private))
    app.add_handler(CommandHandler("help", cmd_help, filters=private))
    app.add_handler(CommandHandler("terms", cmd_terms, filters=private))
    app.add_handler(CommandHandler("deletemydata", cmd_deletemydata, filters=private))
    app.add_handler(CommandHandler("stats", cmd_stats, filters=private))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(error_handler)
    return app


def main():
    problems = validate_config()
    if problems:
        for p in problems:
            logger.error("CONFIG ERROR: %s", p)
        raise SystemExit(2)

    init_db()
    logger.info(
        "Config OK | admins=%d | contact=%s | portfolio=%s | payment=%s",
        len(ADMIN_IDS), bool(CONTACT_USERNAME), bool(PORTFOLIO_URL), PAYMENT_CONFIGURED,
    )
    start_background_threads()
    app = build_application()
    logger.info("RM Media bot (Phase 1) is running.")
    # drop_pending_updates: after a restart do not replay a backlog (avoids a burst of replies)
    app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        time.sleep(30)  # config error: wait so a restart loop cannot hammer anything
        raise
    except InvalidToken:
        logger.error("Telegram rejected the token. Check BOT_TOKEN. Sleeping before exit.")
        time.sleep(300)
        sys.exit(1)
    except Exception:
        logger.exception("Fatal crash - backing off 60s before exit to avoid a rapid restart loop")
        time.sleep(60)
        sys.exit(1)
