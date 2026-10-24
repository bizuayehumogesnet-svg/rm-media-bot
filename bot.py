"""
RM Media | Result & Momentum - Telegram bot (v3)

New in v3:
  * Price packages (Basic / Standard / Premium) for every service  -> edit PACKAGES below
  * Every order stores package + exact price; checkout shows the exact amount
  * Automatic database backup sent to the admin (every 6h + after each confirmed order)
    and /restore (send the backup file back with caption /restore) -> data survives Render restarts
  * Duplicate receipt detection (same reference text / same image) flagged to the admin
  * /done <order id>  -> marks delivered and asks the customer for a review
  * "My orders" button for customers
  * Live counter of confirmed orders on the welcome screen (shown only when >= SOCIAL_PROOF_MIN)
  * Render self-ping (keeps the free instance awake) when RENDER_EXTERNAL_URL is set
  * Reviews show first name only; optional Binance Pay line for international clients

Required env vars (Render -> Environment):
  BOT_TOKEN, CBE_ACCOUNT, CBE_NAME, TELEBIRR_NUMBER, TELEBIRR_NAME
Optional:
  ADMIN_USER_ID, DB_FILE, PORT, BINANCE_PAY_ID, SOCIAL_PROOF_MIN (default 10)
"""

import asyncio
import logging
import os
import sqlite3
import tempfile
import urllib.request
from contextlib import closing
from datetime import datetime
from threading import Thread

from flask import Flask
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
