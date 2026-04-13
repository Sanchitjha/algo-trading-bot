"""
Phase 6 — Trade Journal
=========================
Logs every trade to a CSV file for post-analysis.
Creates a persistent record beyond MT5 history.

Journal CSV columns:
    timestamp, ticket, symbol, action, lot, entry_price, sl, tp,
    exit_price, profit, pnl_pct, duration_minutes, comment
"""

import csv
import os
import logging
from datetime import datetime


JOURNAL_PATH = os.path.join('logs', 'trade_journal.csv')

HEADERS = [
    'timestamp', 'ticket', 'symbol', 'action', 'lot',
    'entry_price', 'sl', 'tp', 'exit_price',
    'profit', 'pnl_pct', 'duration_min', 'comment',
]


def _ensure_journal():
    """Create journal CSV with headers if it doesn't exist."""
    if not os.path.exists(JOURNAL_PATH):
        os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
        with open(JOURNAL_PATH, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)


def log_trade_open(
    ticket: int,
    symbol: str,
    action: str,
    lot: float,
    entry_price: float,
    sl: float,
    tp: float,
    comment: str = '',
):
    """Log a trade entry to the journal."""
    _ensure_journal()

    row = {
        'timestamp':    datetime.utcnow().isoformat(),
        'ticket':       ticket,
        'symbol':       symbol,
        'action':       action,
        'lot':          lot,
        'entry_price':  entry_price,
        'sl':           sl,
        'tp':           tp,
        'exit_price':   '',
        'profit':       '',
        'pnl_pct':      '',
        'duration_min': '',
        'comment':      comment,
    }

    with open(JOURNAL_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)

    logging.info(f"Journal: OPEN {action} {symbol} ticket={ticket}")


def log_trade_close(
    ticket: int,
    symbol: str,
    action: str,
    lot: float,
    entry_price: float,
    exit_price: float,
    profit: float,
    sl: float = 0,
    tp: float = 0,
    duration_minutes: float = 0,
    comment: str = '',
):
    """Log a trade exit to the journal."""
    _ensure_journal()

    pnl_pct = (profit / (entry_price * lot * 100000)) * 100 if entry_price > 0 else 0

    row = {
        'timestamp':    datetime.utcnow().isoformat(),
        'ticket':       ticket,
        'symbol':       symbol,
        'action':       f"close_{action}",
        'lot':          lot,
        'entry_price':  entry_price,
        'sl':           sl,
        'tp':           tp,
        'exit_price':   exit_price,
        'profit':       round(profit, 2),
        'pnl_pct':      round(pnl_pct, 4),
        'duration_min': round(duration_minutes, 1),
        'comment':      comment,
    }

    with open(JOURNAL_PATH, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)

    logging.info(f"Journal: CLOSE {symbol} ticket={ticket} P&L={profit:+.2f}")


def get_journal_stats() -> dict:
    """Read journal and compute summary statistics."""
    _ensure_journal()

    trades = []
    with open(JOURNAL_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('profit') and row['profit'] != '':
                trades.append({
                    'symbol':  row['symbol'],
                    'action':  row['action'],
                    'profit':  float(row['profit']),
                    'pnl_pct': float(row.get('pnl_pct', 0)),
                })

    if not trades:
        return {'total_trades': 0}

    profits = [t['profit'] for t in trades]
    winners = [p for p in profits if p > 0]
    losers  = [p for p in profits if p < 0]

    return {
        'total_trades':   len(trades),
        'total_pnl':      round(sum(profits), 2),
        'winning_trades': len(winners),
        'losing_trades':  len(losers),
        'win_rate':       round(len(winners) / len(trades) * 100, 1) if trades else 0,
        'avg_win':        round(sum(winners) / len(winners), 2) if winners else 0,
        'avg_loss':       round(sum(losers) / len(losers), 2) if losers else 0,
        'best_trade':     round(max(profits), 2),
        'worst_trade':    round(min(profits), 2),
        'profit_factor':  round(sum(winners) / abs(sum(losers)), 2) if losers else float('inf'),
    }
