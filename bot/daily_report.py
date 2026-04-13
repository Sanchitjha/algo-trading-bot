"""
Phase 6 — Daily P&L Summary Reporter
======================================
Generates and sends a daily trading summary via Telegram.
Can be run via cron or called from the bot.

Cron setup (run at 23:55 UTC every day):
    55 23 * * * /path/to/venv/bin/python -c "from bot.daily_report import send_daily_report; send_daily_report()"
"""

import logging
from datetime import datetime, timedelta

import MetaTrader5 as mt5

from bot.telegram import send_telegram


def get_daily_trades() -> list[dict]:
    """Get all trades closed today."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    deals = mt5.history_deals_get(today_start, datetime.now())
    if not deals:
        return []

    trades = []
    for deal in deals:
        if deal.entry == 1:  # Only closing deals (entry=1 means exit)
            trades.append({
                'ticket':  deal.order,
                'symbol':  deal.symbol,
                'type':    'buy' if deal.type == 0 else 'sell',
                'volume':  deal.volume,
                'price':   deal.price,
                'profit':  deal.profit,
                'swap':    deal.swap,
                'commission': deal.commission,
                'time':    datetime.fromtimestamp(deal.time),
            })

    return trades


def generate_daily_report() -> str:
    """Generate formatted daily P&L report."""
    trades = get_daily_trades()
    account = mt5.account_info()
    positions = mt5.positions_get()

    # Calculate metrics
    total_trades   = len(trades)
    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades  = [t for t in trades if t['profit'] < 0]

    total_profit = sum(t['profit'] for t in trades)
    total_swap   = sum(t['swap'] for t in trades)
    total_comm   = sum(t['commission'] for t in trades)
    net_pnl      = total_profit + total_swap + total_comm

    gross_profit = sum(t['profit'] for t in winning_trades) if winning_trades else 0
    gross_loss   = abs(sum(t['profit'] for t in losing_trades)) if losing_trades else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

    best_trade  = max(trades, key=lambda t: t['profit']) if trades else None
    worst_trade = min(trades, key=lambda t: t['profit']) if trades else None

    open_count = len(positions) if positions else 0
    open_pnl   = sum(p.profit for p in positions) if positions else 0

    # Format report
    date_str = datetime.now().strftime('%Y-%m-%d')
    pnl_emoji = "\u2705" if net_pnl >= 0 else "\u274c"

    report = (
        f"*DAILY REPORT — {date_str}*\n"
        f"{'=' * 30}\n\n"
        f"{pnl_emoji} *Net P&L: `{net_pnl:+.2f} {account.currency}`*\n\n"
        f"*Trades:*\n"
        f"  Total: {total_trades}\n"
        f"  Wins:  {len(winning_trades)} | Losses: {len(losing_trades)}\n"
        f"  Win Rate: {win_rate:.0f}%\n"
        f"  Profit Factor: {profit_factor:.2f}\n\n"
        f"*Breakdown:*\n"
        f"  Gross Profit: +{gross_profit:.2f}\n"
        f"  Gross Loss:   -{gross_loss:.2f}\n"
        f"  Swap:         {total_swap:+.2f}\n"
        f"  Commission:   {total_comm:+.2f}\n\n"
    )

    if best_trade:
        report += (
            f"*Best Trade:*  {best_trade['symbol']} "
            f"{best_trade['type'].upper()} → +{best_trade['profit']:.2f}\n"
        )
    if worst_trade and worst_trade['profit'] < 0:
        report += (
            f"*Worst Trade:* {worst_trade['symbol']} "
            f"{worst_trade['type'].upper()} → {worst_trade['profit']:.2f}\n"
        )

    report += (
        f"\n*Account:*\n"
        f"  Balance: {account.balance:.2f} {account.currency}\n"
        f"  Equity:  {account.equity:.2f}\n"
        f"  Open Positions: {open_count} (PnL: {open_pnl:+.2f})\n"
    )

    return report


def send_daily_report() -> bool:
    """Generate and send the daily report via Telegram."""
    try:
        report = generate_daily_report()
        logging.info("Daily report generated")
        return send_telegram(report)
    except Exception as e:
        logging.error(f"Failed to generate daily report: {e}")
        return False
