import logging
from config.settings import ALLOWED_SYMBOLS

VALID_ACTIONS = {'buy', 'sell', 'closelong', 'closeshort', 'close_all'}

REQUIRED_FIELDS = {'action', 'symbol'}


def validate_signal(data: dict) -> tuple[bool, str]:
    """
    Validate incoming webhook signal structure and values.
    Returns (is_valid, error_message).
    """
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            return False, f"Missing required field: '{field}'"

    action = data['action'].lower().strip()
    symbol = data['symbol'].upper().strip()

    # Validate action
    if action not in VALID_ACTIONS:
        return False, f"Invalid action '{action}'. Must be one of: {VALID_ACTIONS}"

    # Validate symbol against whitelist
    if symbol not in [s.upper() for s in ALLOWED_SYMBOLS]:
        return False, f"Symbol '{symbol}' not in allowed list: {ALLOWED_SYMBOLS}"

    # For buy/sell orders, validate SL/TP if provided
    if action in ('buy', 'sell'):
        sl = data.get('sl')
        tp = data.get('tp')

        if sl is not None:
            try:
                sl = float(sl)
                if sl <= 0:
                    return False, "Stop loss must be a positive number"
            except (ValueError, TypeError):
                return False, f"Invalid stop loss value: {sl}"

        if tp is not None:
            try:
                tp = float(tp)
                if tp <= 0:
                    return False, "Take profit must be a positive number"
            except (ValueError, TypeError):
                return False, f"Invalid take profit value: {tp}"

        # Validate risk percentage if provided
        risk_pct = data.get('risk_pct')
        if risk_pct is not None:
            try:
                risk_pct = float(risk_pct)
                if not (0.1 <= risk_pct <= 10.0):
                    return False, f"Risk % must be between 0.1 and 10.0, got {risk_pct}"
            except (ValueError, TypeError):
                return False, f"Invalid risk_pct value: {risk_pct}"

    logging.info(f"Signal validated: action={action}, symbol={symbol}")
    return True, ""


def parse_signal(data: dict) -> dict:
    """
    Normalize and extract signal fields from raw webhook data.
    Call only after validate_signal() returns True.
    """
    return {
        'action':    data['action'].lower().strip(),
        'symbol':    data['symbol'].upper().strip(),
        'sl':        float(data['sl']) if data.get('sl') is not None else None,
        'tp':        float(data['tp']) if data.get('tp') is not None else None,
        'risk_pct':  float(data.get('risk_pct', 1.0)),
        'price':     float(data['price']) if data.get('price') else None,
        'timeframe': data.get('timeframe', ''),
        'comment':   data.get('comment', 'Algo Bot Signal'),
    }
