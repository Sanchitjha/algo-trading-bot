import logging
import requests
from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_telegram(message: str, parse_mode: str = 'Markdown') -> bool:
    """Send notification to Telegram. Returns True if successful."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram not configured — skipping notification")
        return False

    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id':    TELEGRAM_CHAT_ID,
        'text':       message,
        'parse_mode': parse_mode,
    }

    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code == 200:
            logging.info("Telegram notification sent")
            return True
        logging.error(f"Telegram API error: {resp.status_code} — {resp.text}")
        return False
    except Exception as e:
        logging.error(f"Telegram send failed: {e}")
        return False


def format_trade_message(
    action: str,
    symbol: str,
    lot: float,
    price: float,
    sl: float,
    tp: float,
    ticket: int,
    pnl: float | None = None,
) -> str:
    """Format a rich trade notification message."""
    emoji = "\U0001f7e2" if action == "buy" else "\U0001f534"  # green / red circle

    msg = (
        f"{emoji} *{action.upper()} {symbol}*\n"
        f"{'=' * 20}\n"
        f"Lot: `{lot}`\n"
        f"Price: `{price}`\n"
        f"Stop Loss: `{sl}`\n"
        f"Take Profit: `{tp}`\n"
        f"Ticket: `#{ticket}`\n"
    )

    if pnl is not None:
        pnl_emoji = "\u2705" if pnl >= 0 else "\u274c"
        msg += f"{pnl_emoji} P&L: `{pnl:+.2f}`\n"

    return msg


def send_startup_message() -> bool:
    """Notify that the bot has started."""
    return send_telegram(
        "\U0001f680 *Algo Trading Bot Online*\n"
        "Server started and ready to receive signals.",
        parse_mode='Markdown',
    )


def send_error_alert(error_msg: str) -> bool:
    """Send critical error alert."""
    return send_telegram(
        f"\U0001f6a8 *BOT ERROR*\n`{error_msg}`",
        parse_mode='Markdown',
    )
