"""
Phase 6 — Demo Account Testing Tool
=====================================
Sends test signals to the bot to verify the full pipeline works
on a demo account before going live.

Usage:
    python demo_test.py                                    # Run all tests
    python demo_test.py --url https://your-bot.com         # Custom URL
    python demo_test.py --test buy_eurusd                  # Single test
"""

import argparse
import json
import time
import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class DemoTester:
    """Sends test signals and verifies bot behavior on demo account."""

    def __init__(self, base_url: str = 'http://localhost:5000'):
        self.base_url = base_url
        self.results = []

    def send_signal(self, signal: dict, endpoint: str = '/webhook') -> dict:
        """Send a signal and return the response."""
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                json=signal,
                timeout=30,
            )
            return {
                'status_code': resp.status_code,
                'body': resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text,
            }
        except Exception as e:
            return {'status_code': 0, 'body': str(e)}

    def test(self, name: str, signal: dict, expect_status: int = 200,
             expect_field: str = None, expect_value: str = None,
             endpoint: str = '/webhook'):
        """Run a single test case."""
        logging.info(f"\nTest: {name}")
        logging.info(f"  Signal: {json.dumps(signal)}")

        result = self.send_signal(signal, endpoint)
        passed = result['status_code'] == expect_status

        if expect_field and expect_value and isinstance(result['body'], dict):
            actual = str(result['body'].get(expect_field, ''))
            if actual != expect_value:
                passed = False
                logging.info(f"  Expected {expect_field}={expect_value}, got {actual}")

        status = "PASS" if passed else "FAIL"
        logging.info(f"  Response: {result['status_code']} — {result['body']}")
        logging.info(f"  [{status}]")

        self.results.append({'name': name, 'passed': passed, 'response': result})
        return passed

    def run_all_tests(self):
        """Run the complete test suite."""
        logging.info("=" * 60)
        logging.info("  DEMO ACCOUNT TEST SUITE")
        logging.info("=" * 60)

        # ── 1. Health check ──
        logging.info("\n--- Health & Connectivity ---")
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=10)
            health = resp.json()
            self.results.append({
                'name': 'Health check',
                'passed': resp.status_code == 200 and health.get('mt5_connected'),
                'response': health,
            })
            if not health.get('mt5_connected'):
                logging.error("MT5 not connected — cannot proceed with trade tests")
                return
        except Exception as e:
            logging.error(f"Server unreachable: {e}")
            return

        # ── 2. Invalid signal tests ──
        logging.info("\n--- Validation Tests ---")

        self.test("Reject missing action", {
            "symbol": "EURUSD", "sl": 1.08, "tp": 1.09,
        }, expect_status=400)

        self.test("Reject missing symbol", {
            "action": "buy", "sl": 1.08, "tp": 1.09,
        }, expect_status=400)

        self.test("Reject invalid symbol", {
            "action": "buy", "symbol": "FAKEPAIR", "sl": 1.08, "tp": 1.09,
        }, expect_status=400)

        self.test("Reject invalid action", {
            "action": "invalid", "symbol": "EURUSD",
        }, expect_status=400)

        self.test("Reject missing SL", {
            "action": "buy", "symbol": "EURUSD", "tp": 1.09,
        }, expect_status=400)

        # ── 3. Buy order test ──
        logging.info("\n--- Order Execution Tests (DEMO) ---")
        logging.info("  WARNING: These place real orders on your DEMO account!")

        # Get current price to set realistic SL/TP
        try:
            acct = requests.get(f"{self.base_url}/account", timeout=10).json()
            logging.info(f"  Account balance: {acct.get('balance', '?')}")
        except Exception:
            pass

        self.test("BUY EURUSD (demo)", {
            "action": "buy",
            "symbol": "EURUSD",
            "sl": 1.0500,
            "tp": 1.1200,
            "risk_pct": 0.5,
            "comment": "Demo Test BUY",
        }, expect_status=200)

        time.sleep(2)

        self.test("SELL GBPUSD (demo)", {
            "action": "sell",
            "symbol": "GBPUSD",
            "sl": 1.3200,
            "tp": 1.2800,
            "risk_pct": 0.5,
            "comment": "Demo Test SELL",
        }, expect_status=200)

        time.sleep(2)

        # ── 4. Check positions ──
        logging.info("\n--- Position Verification ---")
        try:
            resp = requests.get(f"{self.base_url}/positions", timeout=10)
            positions = resp.json().get('positions', [])
            logging.info(f"  Open positions: {len(positions)}")
            for pos in positions:
                logging.info(f"    {pos['type'].upper()} {pos['symbol']} "
                           f"{pos['volume']} lots P&L={pos['profit']:.2f}")
        except Exception as e:
            logging.error(f"  Cannot check positions: {e}")

        # ── 5. Close test ──
        logging.info("\n--- Close Position Tests ---")
        self.test("Close EURUSD positions", {
            "action": "closelong",
            "symbol": "EURUSD",
        }, expect_status=200)

        time.sleep(1)

        self.test("Close GBPUSD positions", {
            "action": "closeshort",
            "symbol": "GBPUSD",
        }, expect_status=200)

        # ── 6. Status check ──
        logging.info("\n--- System Status ---")
        try:
            resp = requests.get(f"{self.base_url}/status", timeout=10)
            if resp.status_code == 200:
                status = resp.json()
                logging.info(f"  Session: {status.get('session_info', '?')}")
                logging.info(f"  Daily P&L: {status.get('daily_pnl', '?')}")
                logging.info(f"  Trading allowed: {status.get('trading_allowed', '?')}")
        except Exception:
            pass

        # ── Summary ──
        self._print_summary()

    def _print_summary(self):
        passed = sum(1 for r in self.results if r['passed'])
        total  = len(self.results)
        failed = total - passed

        logging.info("\n" + "=" * 60)
        logging.info(f"  RESULTS: {passed}/{total} tests passed")
        logging.info("=" * 60)

        if failed == 0:
            logging.info("\n  ALL TESTS PASSED!")
        else:
            logging.info(f"\n  {failed} test(s) FAILED:")
            for r in self.results:
                if not r['passed']:
                    logging.info(f"    - {r['name']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Demo Account Tester')
    parser.add_argument('--url', default='http://localhost:5000', help='Bot base URL')
    args = parser.parse_args()

    tester = DemoTester(base_url=args.url)
    tester.run_all_tests()
