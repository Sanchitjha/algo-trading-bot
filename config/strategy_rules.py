"""
Phase 1 — Strategy & Requirements Configuration
=================================================
Every trading rule is defined here BEFORE any code runs.
Modify these to change strategy behavior without touching core logic.
"""

# ─── STRATEGY PARAMETERS ────────────────────────────────────
STRATEGY = {
    'name': 'RSI_MACD_EMA_Confluence',
    'version': '1.0',
    'description': 'Triple-confirmation trend-following strategy with ATR risk management',
}

# ─── INDICATOR SETTINGS ────────────────────────────────────
INDICATORS = {
    'ema_fast':     9,
    'ema_slow':     21,
    'rsi_period':   14,
    'rsi_overbought': 70,
    'rsi_oversold':   30,
    'macd_fast':    12,
    'macd_slow':    26,
    'macd_signal':  9,
    'atr_period':   14,
    'atr_multiplier': 1.5,
}

# ─── ENTRY CONDITIONS ──────────────────────────────────────
# BUY requires ALL of:
#   1. EMA 9 > EMA 21 (bullish trend)
#   2. RSI crosses above 30 (oversold bounce) OR MACD bullish crossover
#   3. No existing open position on same symbol
#
# SELL requires ALL of:
#   1. EMA 9 < EMA 21 (bearish trend)
#   2. RSI crosses below 70 (overbought rejection) OR MACD bearish crossunder
#   3. No existing open position on same symbol

# ─── EXIT RULES ────────────────────────────────────────────
EXIT_RULES = {
    'sl_type':           'atr',       # 'atr', 'fixed_pips', 'structure'
    'sl_atr_multiplier': 1.5,         # SL = entry ± (ATR × this)
    'tp_rr_ratio':       2.0,         # TP = SL distance × this (min 1:2 R:R)
    'trailing_stop':     True,        # Move SL to breakeven at +1R
    'trailing_trigger':  1.0,         # R-multiples before trailing activates
    'partial_close':     False,       # Close 50% at +1R (advanced)
    'partial_close_pct': 50,
}

# ─── TRADING PAIRS ─────────────────────────────────────────
FOREX_PAIRS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
CRYPTO_PAIRS = ['BTCUSD', 'ETHUSD']
METALS = ['XAUUSD']  # Gold

ALL_SYMBOLS = FOREX_PAIRS + CRYPTO_PAIRS + METALS

# ─── TIMEFRAMES ────────────────────────────────────────────
TIMEFRAMES = {
    'scalping':  '5m',    # Quick entries, requires tight spread
    'swing':     '1h',    # Balanced — recommended starting timeframe
    'position':  '4h',    # Fewer trades, higher quality
    'daily':     '1d',    # Long term trend following
}

DEFAULT_TIMEFRAME = '1h'

# ─── SESSION FILTERS ───────────────────────────────────────
# Only trade during high-liquidity sessions (UTC times)
SESSION_FILTERS = {
    'enabled':          True,
    'london_open':      '08:00',
    'london_close':     '16:00',
    'ny_open':          '13:00',
    'ny_close':         '21:00',
    'asian_open':       '00:00',
    'asian_close':      '08:00',
    'allowed_sessions': ['london', 'ny_overlap'],  # Trade only these
    'ny_overlap_start': '13:00',  # London + NY overlap = highest volume
    'ny_overlap_end':   '17:00',
}

# ─── NEWS FILTER ───────────────────────────────────────────
NEWS_FILTER = {
    'enabled':              True,
    'pause_minutes_before': 30,     # Stop trading 30 min before high-impact news
    'pause_minutes_after':  15,     # Resume 15 min after news
    'impact_levels':        ['high'],  # Only filter high-impact events
    # Sources: ForexFactory, Investing.com calendar
}

# ─── DAY FILTERS ───────────────────────────────────────────
DAY_FILTERS = {
    'skip_friday_after':  '18:00',  # No new trades Friday evening (gap risk)
    'skip_sunday_before': '22:00',  # No Sunday open gap trades
    'skip_holidays':      True,      # Skip known market holidays
}

# ─── RISK PARAMETERS (per trade) ──────────────────────────
RISK = {
    'risk_pct':           1.0,      # Risk 1% of balance per trade
    'max_risk_pct':       2.0,      # Hard ceiling
    'max_daily_loss_pct': 5.0,      # Halt trading if daily loss exceeds this
    'max_weekly_dd_pct':  10.0,     # Reduce size by 50% if weekly DD exceeds this
    'max_open_positions': 5,
    'max_correlated':     2,        # Max positions in correlated pairs (EUR/GBP)
    'min_rr_ratio':       2.0,      # Minimum risk:reward to accept a trade
}

# ─── CORRELATED PAIRS MAP ─────────────────────────────────
# If we have a position in key, count value pairs as correlated
CORRELATION_MAP = {
    'EURUSD': ['GBPUSD', 'AUDUSD'],
    'GBPUSD': ['EURUSD'],
    'USDJPY': ['USDCAD'],
    'BTCUSD': ['ETHUSD'],
}

# ─── POSITION SIZING TABLE ────────────────────────────────
# Account size tiers → risk adjustment
POSITION_TIERS = {
    500:   {'risk_pct': 0.5, 'max_positions': 2},   # Micro account
    1000:  {'risk_pct': 1.0, 'max_positions': 3},
    5000:  {'risk_pct': 1.0, 'max_positions': 5},
    10000: {'risk_pct': 1.5, 'max_positions': 5},
    50000: {'risk_pct': 2.0, 'max_positions': 8},
}


def get_tier_settings(balance: float) -> dict:
    """Return risk settings based on account balance tier."""
    tier = POSITION_TIERS[500]  # Default to smallest
    for threshold, settings in sorted(POSITION_TIERS.items()):
        if balance >= threshold:
            tier = settings
    return tier
