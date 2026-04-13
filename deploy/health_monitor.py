"""
Phase 5 — Health Monitoring Script
====================================
Runs as a cron job to check bot health and alert if something is wrong.

Cron setup (check every 5 minutes):
    */5 * * * * /home/ubuntu/algo-trading-bot/venv/bin/python /home/ubuntu/algo-trading-bot/deploy/health_monitor.py

Usage:
    python deploy/health_monitor.py
    python deploy/health_monitor.py --url https://your-bot.onrender.com
"""

import argparse
import sys
import os

# Allow importing from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)


def check_health(base_url: str, timeout: int = 15) -> dict:
    """
    Check bot health and return status report.

    Returns:
        Dict with health check results
    """
    report = {
        'timestamp':    datetime.utcnow().isoformat(),
        'url':          base_url,
        'server_up':    False,
        'mt5_connected': False,
        'issues':       [],
    }

    # ── Check /health endpoint ──
    try:
        resp = requests.get(f"{base_url}/health", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            report['server_up']     = True
            report['mt5_connected'] = data.get('mt5_connected', False)
            report['version']       = data.get('version', 'unknown')
            report['open_positions'] = data.get('open_positions', 0)

            if not data.get('mt5_connected'):
                report['issues'].append("MT5 disconnected")
            if data.get('trading_halted'):
                report['issues'].append("Trading is halted")
        else:
            report['issues'].append(f"Health endpoint returned {resp.status_code}")
    except requests.ConnectionError:
        report['issues'].append("Server unreachable (connection refused)")
    except requests.Timeout:
        report['issues'].append(f"Server timeout after {timeout}s")
    except Exception as e:
        report['issues'].append(f"Health check error: {e}")

    # ── Check /status for detailed info ──
    if report['server_up']:
        try:
            resp = requests.get(f"{base_url}/status", timeout=timeout)
            if resp.status_code == 200:
                status = resp.json()
                report['daily_pnl']   = status.get('daily_pnl', 0)
                report['session']     = status.get('session_info', 'unknown')
                report['account']     = status.get('account', {})

                # Check daily loss limit
                balance = status.get('account', {}).get('balance', 0)
                pnl = status.get('daily_pnl', 0)
                if balance > 0 and pnl < 0:
                    loss_pct = abs(pnl / balance * 100)
                    if loss_pct > 3.0:
                        report['issues'].append(f"Daily loss warning: {loss_pct:.1f}%")
        except Exception:
            pass

    return report


def send_alert(report: dict):
    """Send alert via Telegram if there are issues."""
    from bot.telegram import send_telegram

    if not report['issues']:
        return

    msg = f"*BOT HEALTH ALERT*\n"
    msg += f"Time: {report['timestamp']}\n"
    msg += f"Server: {'UP' if report['server_up'] else 'DOWN'}\n"
    msg += f"MT5: {'Connected' if report['mt5_connected'] else 'DISCONNECTED'}\n"
    msg += f"\nIssues:\n"
    for issue in report['issues']:
        msg += f"  - {issue}\n"

    send_telegram(msg)
    logging.warning(f"Alert sent: {report['issues']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bot Health Monitor')
    parser.add_argument('--url', default='http://localhost:5000', help='Bot base URL')
    args = parser.parse_args()

    report = check_health(args.url)

    if report['issues']:
        logging.warning(f"Issues found: {report['issues']}")
        send_alert(report)
    else:
        logging.info("All systems OK")

    # Print report
    for key, value in report.items():
        logging.info(f"  {key}: {value}")
