"""
Phase 3 — Walk-Forward Optimization Engine
============================================
Prevents overfitting by testing optimized parameters on unseen data.

The walk-forward method:
  1. Split data into rolling windows (70% train, 30% test)
  2. Optimize parameters on training window
  3. Test those params on the out-of-sample window
  4. Slide the window forward and repeat
  5. Aggregate out-of-sample results → if profitable, strategy is robust

Usage:
    python walk_forward.py --data data/EURUSD_H1.csv --windows 4
"""

import argparse
import logging
import pandas as pd
import pandas_ta as ta
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class RSI_MACD_EMA_WF(Strategy):
    """Walk-forward optimizable strategy."""

    ema_fast   = 9
    ema_slow   = 21
    rsi_period = 14
    rsi_os     = 30
    rsi_ob     = 70
    atr_mult   = 1.5
    rr_ratio   = 2.0

    def init(self):
        close = pd.Series(self.data.Close)
        high  = pd.Series(self.data.High)
        low   = pd.Series(self.data.Low)

        self.ema_f = self.I(ta.ema, close, self.ema_fast)
        self.ema_s = self.I(ta.ema, close, self.ema_slow)
        self.rsi   = self.I(ta.rsi, close, self.rsi_period)
        self.atr   = self.I(ta.atr, high, low, close, 14)

    def next(self):
        price   = self.data.Close[-1]
        atr_val = self.atr[-1]

        if pd.isna(atr_val) or atr_val <= 0:
            return

        sl_dist = atr_val * self.atr_mult
        tp_dist = sl_dist * self.rr_ratio

        bullish = self.ema_f[-1] > self.ema_s[-1]
        bearish = self.ema_f[-1] < self.ema_s[-1]

        rsi_buy  = crossover(self.rsi, self.rsi_os)
        rsi_sell = crossover(self.rsi_ob, self.rsi)

        if bullish and rsi_buy and not self.position:
            self.buy(sl=price - sl_dist, tp=price + tp_dist)
        elif bearish and rsi_sell and not self.position:
            self.sell(sl=price + sl_dist, tp=price - tp_dist)


def walk_forward_optimization(
    data: pd.DataFrame,
    n_windows: int = 4,
    train_pct: float = 0.7,
    cash: float = 10_000,
) -> dict:
    """
    Run walk-forward optimization.

    Args:
        data:       Full OHLCV DataFrame
        n_windows:  Number of rolling windows
        train_pct:  Fraction of each window used for training
        cash:       Starting capital

    Returns:
        Dict with per-window results and aggregate metrics
    """
    total_bars = len(data)
    window_size = total_bars // n_windows
    train_size  = int(window_size * train_pct)
    test_size   = window_size - train_size

    logging.info(f"Total bars: {total_bars}")
    logging.info(f"Windows: {n_windows}, each {window_size} bars (train: {train_size}, test: {test_size})")
    logging.info("=" * 70)

    results = []
    all_oos_returns = []

    for i in range(n_windows):
        start = i * window_size
        train_end = start + train_size
        test_end  = min(start + window_size, total_bars)

        train_data = data.iloc[start:train_end]
        test_data  = data.iloc[train_end:test_end]

        if len(test_data) < 50:
            logging.warning(f"Window {i+1}: Test data too small ({len(test_data)} bars), skipping")
            continue

        logging.info(f"\nWindow {i+1}/{n_windows}")
        logging.info(f"  Train: {train_data.index[0]} to {train_data.index[-1]} ({len(train_data)} bars)")
        logging.info(f"  Test:  {test_data.index[0]} to {test_data.index[-1]} ({len(test_data)} bars)")

        # ── Step 1: Optimize on training data ──
        bt_train = Backtest(
            train_data, RSI_MACD_EMA_WF,
            cash=cash, commission=0.0005, exclusive_orders=True,
        )

        try:
            opt_stats = bt_train.optimize(
                ema_fast  = range(7, 15, 2),
                ema_slow  = range(18, 30, 3),
                rsi_os    = range(25, 40, 5),
                atr_mult  = [1.0, 1.5, 2.0],
                rr_ratio  = [1.5, 2.0, 2.5],
                maximize  = 'Sharpe Ratio',
                constraint = lambda p: p.ema_fast < p.ema_slow,
            )

            # Extract optimized parameters
            opt_params = {
                'ema_fast': opt_stats._strategy.ema_fast,
                'ema_slow': opt_stats._strategy.ema_slow,
                'rsi_os':   opt_stats._strategy.rsi_os,
                'atr_mult': opt_stats._strategy.atr_mult,
                'rr_ratio': opt_stats._strategy.rr_ratio,
            }

            logging.info(f"  Optimized params: {opt_params}")
            logging.info(f"  Train Sharpe: {opt_stats['Sharpe Ratio']:.2f}, "
                        f"Train Return: {opt_stats['Return [%]']:.2f}%")

        except Exception as e:
            logging.error(f"  Optimization failed: {e}")
            continue

        # ── Step 2: Test on out-of-sample data ──
        bt_test = Backtest(
            test_data, RSI_MACD_EMA_WF,
            cash=cash, commission=0.0005, exclusive_orders=True,
        )

        test_stats = bt_test.run(**opt_params)

        oos_return = test_stats['Return [%]']
        oos_sharpe = test_stats['Sharpe Ratio']
        oos_trades = test_stats['# Trades']
        oos_winrate = test_stats['Win Rate [%]']
        oos_drawdown = test_stats['Max. Drawdown [%]']

        all_oos_returns.append(oos_return)

        logging.info(f"  OOS Return:   {oos_return:.2f}%")
        logging.info(f"  OOS Sharpe:   {oos_sharpe:.2f}")
        logging.info(f"  OOS Win Rate: {oos_winrate:.1f}%")
        logging.info(f"  OOS Trades:   {oos_trades}")
        logging.info(f"  OOS Max DD:   {oos_drawdown:.2f}%")

        results.append({
            'window':       i + 1,
            'train_start':  str(train_data.index[0]),
            'train_end':    str(train_data.index[-1]),
            'test_start':   str(test_data.index[0]),
            'test_end':     str(test_data.index[-1]),
            'params':       opt_params,
            'train_return': opt_stats['Return [%]'],
            'train_sharpe': opt_stats['Sharpe Ratio'],
            'oos_return':   oos_return,
            'oos_sharpe':   oos_sharpe,
            'oos_winrate':  oos_winrate,
            'oos_trades':   oos_trades,
            'oos_drawdown': oos_drawdown,
        })

    # ── Aggregate results ──
    logging.info("\n" + "=" * 70)
    logging.info("WALK-FORWARD RESULTS SUMMARY")
    logging.info("=" * 70)

    if not results:
        logging.error("No valid windows completed!")
        return {'windows': [], 'robust': False}

    profitable_windows = sum(1 for r in all_oos_returns if r > 0)
    avg_return = sum(all_oos_returns) / len(all_oos_returns)

    for r in results:
        status = "PASS" if r['oos_return'] > 0 else "FAIL"
        logging.info(
            f"  Window {r['window']}: OOS Return={r['oos_return']:+.2f}%, "
            f"Sharpe={r['oos_sharpe']:.2f}, WR={r['oos_winrate']:.0f}% [{status}]"
        )

    logging.info(f"\n  Profitable windows: {profitable_windows}/{len(results)}")
    logging.info(f"  Average OOS return: {avg_return:+.2f}%")

    # Robustness check: strategy is robust if >50% of OOS windows are profitable
    robust = profitable_windows > len(results) / 2
    if robust:
        logging.info("  VERDICT: STRATEGY IS ROBUST - passed walk-forward validation")
    else:
        logging.warning("  VERDICT: STRATEGY MAY BE OVERFIT - failed walk-forward validation")

    return {
        'windows': results,
        'profitable_windows': profitable_windows,
        'total_windows': len(results),
        'avg_oos_return': avg_return,
        'robust': robust,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Walk-Forward Optimization')
    parser.add_argument('--data', required=True, help='Path to OHLCV CSV file')
    parser.add_argument('--windows', type=int, default=4, help='Number of rolling windows')
    parser.add_argument('--cash', type=float, default=10000, help='Starting capital')
    args = parser.parse_args()

    data = pd.read_csv(args.data, index_col=0, parse_dates=True)

    # Normalize columns
    col_map = {}
    for col in data.columns:
        lower = col.lower()
        if 'open' in lower: col_map[col] = 'Open'
        elif 'high' in lower: col_map[col] = 'High'
        elif 'low' in lower: col_map[col] = 'Low'
        elif 'close' in lower: col_map[col] = 'Close'
        elif 'vol' in lower: col_map[col] = 'Volume'
    data = data.rename(columns=col_map)
    if 'Volume' not in data.columns:
        data['Volume'] = 0

    walk_forward_optimization(data, n_windows=args.windows, cash=args.cash)
