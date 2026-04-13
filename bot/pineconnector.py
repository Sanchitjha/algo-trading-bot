"""
Phase 4 — PineConnector Bridge Handler (Route A)
==================================================
Handles PineConnector-format alert messages.
Converts between PineConnector syntax and internal signal format.

PineConnector syntax:
    LICENSE_ID,buy,EURUSD,vol_pct_bal_loss=1,sl_pips=50,tp_pips=100
    LICENSE_ID,sell,GBPUSD,vol_pct_bal_loss=1,sl=1.2500,tp=1.2600
    LICENSE_ID,closelong,EURUSD
    LICENSE_ID,closeshort,EURUSD
"""

import logging
import os

PINECONNECTOR_LICENSE = os.environ.get('PINECONNECTOR_LICENSE', '')


def parse_pineconnector_alert(raw_text: str) -> dict | None:
    """
    Parse a PineConnector-format alert string into an internal signal dict.

    Args:
        raw_text: Raw alert text from TradingView (comma-separated)

    Returns:
        Signal dict compatible with bot.signals.parse_signal() output,
        or None if parsing fails
    """
    parts = [p.strip() for p in raw_text.strip().split(',')]

    if len(parts) < 3:
        logging.error(f"PineConnector alert too short: {raw_text}")
        return None

    license_id = parts[0]
    action     = parts[1].lower()
    symbol     = parts[2].upper()

    # Validate license
    if PINECONNECTOR_LICENSE and license_id != PINECONNECTOR_LICENSE:
        logging.warning(f"Invalid PineConnector license: {license_id}")
        return None

    signal = {
        'action':   action,
        'symbol':   symbol,
        'sl':       None,
        'tp':       None,
        'risk_pct': 1.0,
        'comment':  'PineConnector',
    }

    # Parse optional key=value parameters
    for part in parts[3:]:
        if '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip().lower()
        value = value.strip()

        if key == 'vol_pct_bal_loss':
            signal['risk_pct'] = float(value)
        elif key == 'sl_pips':
            signal['sl_pips'] = float(value)
        elif key == 'tp_pips':
            signal['tp_pips'] = float(value)
        elif key == 'sl':
            signal['sl'] = float(value)
        elif key == 'tp':
            signal['tp'] = float(value)
        elif key == 'risk':
            signal['risk_pct'] = float(value)
        elif key == 'comment':
            signal['comment'] = value

    return signal


def format_pineconnector_alert(
    action: str,
    symbol: str,
    risk_pct: float = 1.0,
    sl_pips: float | None = None,
    tp_pips: float | None = None,
    sl_price: float | None = None,
    tp_price: float | None = None,
) -> str:
    """
    Generate a PineConnector-format alert string for TradingView.

    Useful for generating alert message templates.
    """
    parts = [PINECONNECTOR_LICENSE or 'YOUR_LICENSE_ID', action.lower(), symbol.upper()]

    parts.append(f"vol_pct_bal_loss={risk_pct}")

    if sl_pips is not None:
        parts.append(f"sl_pips={sl_pips}")
    elif sl_price is not None:
        parts.append(f"sl={sl_price}")

    if tp_pips is not None:
        parts.append(f"tp_pips={tp_pips}")
    elif tp_price is not None:
        parts.append(f"tp={tp_price}")

    return ','.join(parts)
