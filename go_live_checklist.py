"""
Phase 6 — Go-Live Checklist Runner
====================================
Automated verification of all pre-deployment requirements
from Section 15 of the documentation.

Run before switching from demo to live:
    python go_live_checklist.py
    python go_live_checklist.py --url https://your-bot.onrender.com
"""

import argparse
import sys
import os
import json
import logging

import requests

logging.basicConfig(level=logging.INFO, format='%(message)s')


class ChecklistRunner:
    """Runs all go-live verification checks."""

    def __init__(self, base_url: str = 'http://localhost:5000'):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0

    def check(self, name: str, condition: bool, detail: str = ''):
        """Record a check result."""
        status = "PASS" if condition else "FAIL"
        self.results.append({
            'name': name,
            'passed': condition,
            'detail': detail,
        })
        if condition:
            self.passed += 1
            logging.info(f"  [PASS] {name}")
        else:
            self.failed += 1
            logging.info(f"  [FAIL] {name} — {detail}")

    def run_all(self):
        """Execute all checklist categories."""
        logging.info("=" * 60)
        logging.info("  ALGO TRADING BOT — GO-LIVE CHECKLIST")
        logging.info("=" * 60)

        self._check_technical()
        self._check_infrastructure()
        self._check_monitoring()
        self._check_security()
        self._check_files()

        self._print_summary()

    def _check_technical(self):
        """Technical Setup checks."""
        logging.info("\n--- Technical Setup ---")

        # Health endpoint
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=10)
            health = resp.json()
            self.check("Health endpoint returns 200", resp.status_code == 200)
            self.check("MT5 connected", health.get('mt5_connected', False),
                       "MT5 terminal must be running and connected")
        except Exception as e:
            self.check("Server reachable", False, str(e))
            self.check("MT5 connected", False, "Cannot check — server unreachable")

        # Webhook test
        try:
            test_signal = {
                "action": "buy",
                "symbol": "INVALID_TEST",
                "sl": 1.0,
                "tp": 1.1,
            }
            resp = requests.post(f"{self.base_url}/webhook",
                                json=test_signal, timeout=10)
            # Should reject invalid symbol
            self.check("Webhook rejects invalid symbol", resp.status_code == 400,
                       f"Got {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            self.check("Webhook endpoint reachable", False, str(e))

        # Account info
        try:
            resp = requests.get(f"{self.base_url}/account", timeout=10)
            if resp.status_code == 200:
                acct = resp.json()
                self.check("Account balance > 0", acct.get('balance', 0) > 0,
                           f"Balance: {acct.get('balance', 0)}")
            else:
                self.check("Account endpoint works", False)
        except Exception as e:
            self.check("Account check", False, str(e))

    def _check_infrastructure(self):
        """Infrastructure checks."""
        logging.info("\n--- Infrastructure ---")

        # HTTPS check
        if self.base_url.startswith('https://'):
            self.check("Using HTTPS", True)
        elif 'localhost' in self.base_url or '127.0.0.1' in self.base_url:
            self.check("Using HTTPS", True, "Local development (OK)")
        else:
            self.check("Using HTTPS", False, "Production must use HTTPS")

        # Status endpoint
        try:
            resp = requests.get(f"{self.base_url}/status", timeout=10)
            if resp.status_code == 200:
                status = resp.json()
                self.check("Status endpoint works", True)
                self.check("Version reported", bool(status.get('version')),
                           f"v{status.get('version', 'unknown')}")
            else:
                self.check("Status endpoint", False)
        except Exception:
            self.check("Status endpoint", False, "Unreachable")

    def _check_monitoring(self):
        """Monitoring checks."""
        logging.info("\n--- Monitoring ---")

        # Check Telegram config
        try:
            from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
            self.check("Telegram token configured", bool(TELEGRAM_TOKEN),
                       "Set TELEGRAM_TOKEN in .env")
            self.check("Telegram chat ID configured", bool(TELEGRAM_CHAT_ID),
                       "Set TELEGRAM_CHAT_ID in .env")
        except ImportError:
            self.check("Config importable", False, "Cannot import config/settings.py")

    def _check_security(self):
        """Security checks."""
        logging.info("\n--- Security ---")

        # Check .env not in git
        gitignore_path = os.path.join(os.path.dirname(__file__), '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path) as f:
                content = f.read()
            self.check(".env in .gitignore", '.env' in content)
        else:
            self.check(".gitignore exists", False)

        # Check no .env committed
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            self.check(".env file exists (credentials set)", True)
        else:
            self.check(".env file exists", False, "Copy .env.example to .env and fill in values")

        # Check webhook secret
        try:
            from config.settings import WEBHOOK_SECRET
            self.check("Webhook secret configured", bool(WEBHOOK_SECRET),
                       "Set WEBHOOK_SECRET in .env for production")
        except ImportError:
            self.check("Webhook secret", False, "Cannot check")

    def _check_files(self):
        """Check required files exist."""
        logging.info("\n--- File Structure ---")

        required_files = [
            'app.py',
            'requirements.txt',
            'Procfile',
            '.gitignore',
            'bot/__init__.py',
            'bot/broker.py',
            'bot/risk.py',
            'bot/signals.py',
            'bot/telegram.py',
            'bot/trailing_stop.py',
            'bot/emergency.py',
            'config/settings.py',
            'config/strategy_rules.py',
        ]

        base_dir = os.path.dirname(os.path.abspath(__file__))
        for filepath in required_files:
            full = os.path.join(base_dir, filepath)
            self.check(f"File: {filepath}", os.path.exists(full))

    def _print_summary(self):
        """Print final summary."""
        total = self.passed + self.failed
        logging.info("\n" + "=" * 60)
        logging.info(f"  RESULTS: {self.passed}/{total} checks passed")
        logging.info("=" * 60)

        if self.failed == 0:
            logging.info("\n  ALL CHECKS PASSED — Ready to go live!")
            logging.info("  Remember: Run on demo account for 7+ days first.\n")
        else:
            logging.info(f"\n  {self.failed} check(s) FAILED — Fix before going live:")
            for r in self.results:
                if not r['passed']:
                    logging.info(f"    - {r['name']}: {r['detail']}")
            logging.info("")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Go-Live Checklist')
    parser.add_argument('--url', default='http://localhost:5000', help='Bot base URL')
    args = parser.parse_args()

    runner = ChecklistRunner(base_url=args.url)
    runner.run_all()

    sys.exit(0 if runner.failed == 0 else 1)
