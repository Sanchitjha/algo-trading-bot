"""
Phase 3 — MT5 Historical Data Downloader
==========================================
Downloads OHLCV data from MetaTrader5 for backtesting.
Supports all timeframes and symbols defined in strategy_rules.

Usage:
    python data_downloader.py                              # All symbols, 1H, 12 months
    python data_downloader.py --symbol EURUSD --tf M5      # Specific pair & timeframe
    python data_downloader.py --months 24                  # 2 years of data
"""

import argparse
import os
import logging
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd

from config.settings import MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER
from config.strategy_rules import ALL_SYMBOLS

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# MT5 timeframe mapping
TF_MAP = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
    'H4':  mt5.TIMEFRAME_H4,
    'D1':  mt5.TIMEFRAME_D1,
    'W1':  mt5.TIMEFRAME_W1,
}


def connect_mt5():
    """Initialize and login to MT5."""
    if not mt5.initialize():
        raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
    if not mt5.login(MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER):
        raise ConnectionError(f"MT5 login failed: {mt5.last_error()}")
    logging.info(f"Connected to MT5: {MT5_SERVER}")


def download_data(
    symbol: str,
    timeframe: str = 'H1',
    months: int = 12,
    output_dir: str = 'data',
) -> pd.DataFrame:
    """
    Download OHLCV data for a symbol from MT5.

    Args:
        symbol:    Trading pair (e.g., 'EURUSD')
        timeframe: MT5 timeframe string (e.g., 'H1', 'M5', 'D1')
        months:    How many months of history to download
        output_dir: Directory to save CSV files

    Returns:
        DataFrame with OHLCV data
    """
    tf = TF_MAP.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"Invalid timeframe '{timeframe}'. Must be one of: {list(TF_MAP.keys())}")

    # Ensure symbol is available
    if not mt5.symbol_select(symbol, True):
        raise ValueError(f"Symbol {symbol} not available in MT5")

    # Calculate date range
    date_to = datetime.now()
    date_from = date_to - timedelta(days=months * 30)

    logging.info(f"Downloading {symbol} {timeframe} from {date_from.date()} to {date_to.date()}...")

    # Fetch rates
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    if rates is None or len(rates) == 0:
        logging.error(f"No data returned for {symbol} {timeframe}")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df = df.rename(columns={
        'open':        'Open',
        'high':        'High',
        'low':         'Low',
        'close':       'Close',
        'tick_volume': 'Volume',
    })
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

    # Save to CSV
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{symbol}_{timeframe}_{date_from.strftime('%Y%m')}_to_{date_to.strftime('%Y%m')}.csv"
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath)
    logging.info(f"Saved {len(df)} bars to {filepath}")

    return df


def download_all(timeframe: str = 'H1', months: int = 12):
    """Download data for all configured symbols."""
    results = {}
    for symbol in ALL_SYMBOLS:
        try:
            df = download_data(symbol, timeframe, months)
            results[symbol] = len(df)
        except Exception as e:
            logging.error(f"Failed to download {symbol}: {e}")
            results[symbol] = 0

    # Summary
    logging.info("\n" + "=" * 50)
    logging.info("DOWNLOAD SUMMARY")
    logging.info("=" * 50)
    for symbol, bars in results.items():
        status = "OK" if bars > 0 else "FAILED"
        logging.info(f"  {symbol}: {bars} bars [{status}]")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download MT5 historical data')
    parser.add_argument('--symbol', default=None, help='Specific symbol (default: all)')
    parser.add_argument('--tf', default='H1', help='Timeframe: M1, M5, M15, M30, H1, H4, D1, W1')
    parser.add_argument('--months', type=int, default=12, help='Months of history')
    args = parser.parse_args()

    connect_mt5()

    if args.symbol:
        download_data(args.symbol, args.tf, args.months)
    else:
        download_all(args.tf, args.months)

    mt5.shutdown()
