import os
from dotenv import load_dotenv

load_dotenv()


# ─── MT5 BROKER ──────────────────────────────────────────────
MT5_ACCOUNT  = int(os.environ.get('MT5_ACCOUNT', '0'))
MT5_PASSWORD = os.environ.get('MT5_PASSWORD', '')
MT5_SERVER   = os.environ.get('MT5_SERVER', '')  # e.g. "VantageInternational-Demo"

# ─── WEBHOOK SECURITY ────────────────────────────────────────
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# ─── TELEGRAM ────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# ─── RISK MANAGEMENT ────────────────────────────────────────
MAX_RISK_PER_TRADE  = float(os.environ.get('MAX_RISK_PER_TRADE', '2.0'))
MAX_DAILY_LOSS_PCT  = float(os.environ.get('MAX_DAILY_LOSS_PCT', '5.0'))
MAX_OPEN_POSITIONS  = int(os.environ.get('MAX_OPEN_POSITIONS', '5'))
DEFAULT_RISK_PCT    = float(os.environ.get('DEFAULT_RISK_PCT', '1.0'))
RR_RATIO            = float(os.environ.get('RR_RATIO', '2.0'))
ATR_MULTIPLIER      = float(os.environ.get('ATR_MULTIPLIER', '1.5'))

# ─── TRADING RULES ──────────────────────────────────────────
ALLOWED_SYMBOLS = os.environ.get(
    'ALLOWED_SYMBOLS',
    'EURUSD,GBPUSD,XAUUSD,USDJPY,BTCUSD'
).split(',')

# ─── SERVER ─────────────────────────────────────────────────
PORT       = int(os.environ.get('PORT', '5000'))
LOG_LEVEL  = os.environ.get('LOG_LEVEL', 'INFO')
BOT_VERSION = '1.0.0'
