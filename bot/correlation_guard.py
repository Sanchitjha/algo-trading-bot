"""
Correlation guard — prevents overexposure to correlated pairs.
E.g., don't hold both EURUSD long and GBPUSD long simultaneously.
"""

import MetaTrader5 as mt5
from config.strategy_rules import CORRELATION_MAP, RISK


def get_correlated_symbols(symbol: str) -> list[str]:
    """Return list of symbols correlated with the given symbol."""
    return CORRELATION_MAP.get(symbol, [])


def check_correlation_limit(symbol: str, action: str) -> tuple[bool, str]:
    """
    Check if opening a position on this symbol would violate
    the correlation limit. Returns (allowed, reason).
    """
    correlated = get_correlated_symbols(symbol)
    if not correlated:
        return True, "No correlated pairs defined"

    positions = mt5.positions_get()
    if not positions:
        return True, "No open positions"

    # Count positions in correlated pairs with same direction
    correlated_count = 0
    for pos in positions:
        pos_symbol = pos.symbol
        pos_direction = 'buy' if pos.type == 0 else 'sell'

        if pos_symbol in correlated and pos_direction == action:
            correlated_count += 1

    max_correlated = RISK.get('max_correlated', 2)

    if correlated_count >= max_correlated:
        return False, (
            f"Correlation limit: {correlated_count} correlated positions "
            f"already open ({', '.join(correlated)}). Max: {max_correlated}"
        )

    return True, "OK"
