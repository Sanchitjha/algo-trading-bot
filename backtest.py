"""
Algo Trading Bot — Backtesting Engine
=======================================
RSI + MACD + EMA confluence strategy with ATR-based dynamic SL/TP.
Uses backtesting.py library for historical validation.

Usage:
    python backtest.py                     # Run with defaults
    python backtest.py --optimize          # Run parameter optimization
    python backtest.py --data EURUSD.csv   # Custom data file
"""

import argparse
import pandas as pd
import pandas_ta as ta
from backtesting import Backtest, Strategy
from backtesting.lib import crossover


class RSI_MACD_EMA(Strategy):
    """
    Confluence strategy combining:
    - EMA crossover for trend direction
    - RSI for mean-reversion entry timing
    - MACD for momentum confirmation
    - ATR for dynamic stop loss / take profit
    """

    # Optimizable parameters
    ema_fast   = 9
    ema_slow   = 21
    rsi_period = 14
    rsi_os     = 30      # Oversold threshold (buy trigger)
    rsi_ob     = 70      # Overbought threshold (sell trigger)
    atr_period = 14
    atr_mult   = 1.5     # ATR multiplier for stop loss distance
    rr_ratio   = 2.0     # Risk:Reward ratio for take profit
    use_macd   = True     # Whether to require MACD confirmation

    def init(self):
        close = pd.Series(self.data.Close)
        high  = pd.Series(self.data.High)
        low   = pd.Series(self.data.Low)

        # Trend indicators
        self.ema_f = self.I(ta.ema, close, self.ema_fast)
        self.ema_s = self.I(ta.ema, close, self.ema_slow)

        # Momentum
        self.rsi = self.I(ta.rsi, close, self.rsi_period)

        # MACD (12, 26, 9 standard)
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None:
            self.macd_line   = self.I(lambda: macd_df.iloc[:, 0].values)
            self.macd_signal = self.I(lambda: macd_df.iloc[:, 1].values)
            self.macd_hist   = self.I(lambda: macd_df.iloc[:, 2].values)
        else:
            self.use_macd = False

        # Volatility
        self.atr = self.I(ta.atr, high, low, close, self.atr_period)

    def next(self):
        price   = self.data.Close[-1]
        atr_val = self.atr[-1]

        if pd.isna(atr_val) or atr_val <= 0:
            return

        sl_dist = atr_val * self.atr_mult
        tp_dist = sl_dist * self.rr_ratio

        # ─── Trend filter ───
        bullish = self.ema_f[-1] > self.ema_s[-1]
        bearish = self.ema_f[-1] < self.ema_s[-1]

        # ─── RSI triggers ───
        rsi_buy  = crossover(self.rsi, self.rsi_os)   # RSI crosses above oversold
        rsi_sell = crossover(self.rsi_ob, self.rsi)    # RSI crosses below overbought

        # ─── MACD confirmation ───
        macd_buy  = True
        macd_sell = True
        if self.use_macd and hasattr(self, 'macd_line'):
            macd_buy  = crossover(self.macd_line, self.macd_signal)
            macd_sell = crossover(self.macd_signal, self.macd_line)

        # ─── BUY condition: bullish trend + RSI bounce + (optional) MACD ───
        if bullish and rsi_buy and macd_buy and not self.position:
            sl = price - sl_dist
            tp = price + tp_dist
            self.buy(sl=sl, tp=tp)

        # ��── SELL condition: bearish trend + RSI drop + (optional) MACD ───
        elif bearish and rsi_sell and macd_sell and not self.position:
            sl = price + sl_dist
            tp = price - tp_dist
            self.sell(sl=sl, tp=tp)


def run_backtest(data_path: str, optimize: bool = False):
    """Load data and run backtest with optional optimization."""

    # Load OHLCV data
    data = pd.read_csv(data_path, index_col=0, parse_dates=True)

    # Normalize column names
    col_map = {}
    for col in data.columns:
        lower = col.lower()
        if 'open' in lower:
            col_map[col] = 'Open'
        elif 'high' in lower:
            col_map[col] = 'High'
        elif 'low' in lower:
            col_map[col] = 'Low'
        elif 'close' in lower:
            col_map[col] = 'Close'
        elif 'vol' in lower:
            col_map[col] = 'Volume'
    data = data.rename(columns=col_map)

    required = {'Open', 'High', 'Low', 'Close'}
    if not required.issubset(data.columns):
        raise ValueError(f"CSV must have columns: {required}. Found: {set(data.columns)}")

    if 'Volume' not in data.columns:
        data['Volume'] = 0

    print(f"Loaded {len(data)} bars from {data.index[0]} to {data.index[-1]}")
    print(f"{'=' * 60}")

    bt = Backtest(
        data,
        RSI_MACD_EMA,
        cash=10_000,
        commission=0.0005,    # 0.05% commission (typical forex)
        exclusive_orders=True,
    )

    if optimize:
        print("Running parameter optimization (this may take a few minutes)...\n")
        stats = bt.optimize(
            ema_fast   = range(7, 15, 2),
            ema_slow   = range(18, 30, 3),
            rsi_os     = range(25, 40, 5),
            rsi_ob     = range(60, 80, 5),
            atr_mult   = [1.0, 1.5, 2.0, 2.5],
            rr_ratio   = [1.5, 2.0, 2.5, 3.0],
            maximize   = 'Sharpe Ratio',
            constraint = lambda p: p.ema_fast < p.ema_slow,
        )
    else:
        stats = bt.run()

    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(stats)

    # Key metrics summary
    print(f"\n{'─' * 40}")
    print(f"  Total Return:    {stats['Return [%]']:.2f}%")
    print(f"  Win Rate:        {stats['Win Rate [%]']:.1f}%")
    print(f"  Max Drawdown:    {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  Sharpe Ratio:    {stats['Sharpe Ratio']:.2f}")
    print(f"  Profit Factor:   {stats.get('Profit Factor', 'N/A')}")
    print(f"  Total Trades:    {stats['# Trades']}")
    print(f"{'─' * 40}")

    if stats['# Trades'] < 30:
        print("\n  WARNING: Less than 30 trades — results may not be statistically significant.")

    # Show recent trades
    if hasattr(stats, '_trades') and len(stats._trades) > 0:
        print("\nLast 10 trades:")
        print(stats._trades.tail(10).to_string())

    # Plot
    try:
        bt.plot(open_browser=True)
    except Exception:
        print("\n(Could not open browser for plot — run in a GUI environment)")

    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Algo Trading Backtester')
    parser.add_argument('--data', default='data/EURUSD_H1.csv', help='Path to OHLCV CSV file')
    parser.add_argument('--optimize', action='store_true', help='Run parameter optimization')
    args = parser.parse_args()

    run_backtest(args.data, args.optimize)
