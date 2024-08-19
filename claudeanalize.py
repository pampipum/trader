import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ccxt
import os
import pickle
import requests
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
from api_logic import analyze_with_claude
from system_prompt import SYSTEM_PROMPT

# Parameters
TIMEFRAMES = ['90m', '1d', '1wk']
LOOKBACK_YEARS = 1

# Indicator parameters
WT_CHANNEL_LEN = 10
WT_AVERAGE_LEN = 21
AO_FAST_PERIOD = 5
AO_SLOW_PERIOD = 34
RSI_PERIOD = 14
FAST_MA_PERIOD = 5
SLOW_MA_PERIOD = 13
BB_PERIOD = 100
BB_STD_DEV = 2.0
ATR_PERIOD = 14

# Create data_cache directory if it doesn't exist
DATA_CACHE_DIR = 'data_cache'
os.makedirs(DATA_CACHE_DIR, exist_ok=True)

# Timeframe mapping for crypto exchanges
CRYPTO_TIMEFRAME_MAP = {
    '90m': '4h',
    '1d': '1d',
    '1wk': '1w'
}

def fetch_or_load_data(symbol, timeframes, filename_prefix='data'):
    dataframes = {}
    is_crypto = '/' in symbol

    for timeframe in timeframes:
        if is_crypto:
            exchange_timeframe = CRYPTO_TIMEFRAME_MAP.get(timeframe, timeframe)
        else:
            exchange_timeframe = timeframe

        filename = os.path.join(DATA_CACHE_DIR, f'{filename_prefix}_{symbol.replace("/", "").replace("^", "")}__{timeframe}.pkl')
        
        if os.path.exists(filename):
            print(f"Loading {timeframe} data from {filename}")
            with open(filename, 'rb') as f:
                df = pickle.load(f)
            
            # Ensure index is tz-naive
            df.index = pd.to_datetime(df.index).tz_localize(None)
            
            # Update data
            if is_crypto:
                latest_df = fetch_all_ohlcv(symbol, exchange_timeframe)
                if not latest_df.empty:
                    df = pd.concat([df, latest_df[~latest_df.index.isin(df.index)]])
            else:
                end_date = datetime.now().replace(tzinfo=None)
                start_date = df.index[-1].replace(tzinfo=None)
                latest_data = yf.download(symbol, start=start_date, end=end_date, interval=timeframe)
                if not latest_data.empty:
                    latest_data.index = latest_data.index.tz_localize(None)
                    df = pd.concat([df, latest_data[~latest_data.index.isin(df.index)]])
        else:
            print(f"Fetching {timeframe} data from exchange...")
            if is_crypto:
                df = fetch_all_ohlcv(symbol, exchange_timeframe)
            else:
                df = fetch_financial_data(symbol, timeframe)
            
            if not df.empty:
                # Ensure index is tz-naive before saving
                df.index = pd.to_datetime(df.index).tz_localize(None)
                
                with open(filename, 'wb') as f:
                    pickle.dump(df, f)
            else:
                print(f"No data available for {symbol} with timeframe {timeframe}")
                continue  # Skip to the next timeframe
        
        # Final check to ensure all datetime objects are tz-naive
        df.index = pd.to_datetime(df.index).tz_localize(None)
        
        # Filter for the last LOOKBACK_YEARS
        cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=365*LOOKBACK_YEARS)
        df = df[df.index > cutoff_date]
        
        if not df.empty:
            print(f"\nLatest {timeframe} data points:")
            print(df.tail().to_string())
            dataframes[timeframe] = df
        else:
            print(f"No data available for {symbol} with timeframe {timeframe} after filtering")
    
    return dataframes

# Update fetch_financial_data function
def fetch_financial_data(symbol, timeframe):
    if timeframe == '90m':
        period = '1mo'
    elif timeframe == '1d':
        period = '1y'
    elif timeframe == '1wk':
        period = '2y'
    
    df = yf.Ticker(symbol).history(period=period, interval=timeframe)
    df.index = df.index.tz_localize(None)  # Ensure tz-naive
    df.index.name = 'timestamp'
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    return df


def fetch_all_ohlcv(symbol, timeframe):
    exchange = ccxt.binance()
    all_ohlcv = []
    start_date = int((datetime.now().replace(tzinfo=None) - timedelta(days=365*LOOKBACK_YEARS)).timestamp() * 1000)

    while True:
        print(f"Fetching data from {exchange.iso8601(start_date)}...")
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=start_date, limit=1000)
        if len(ohlcv) == 0:
            break
        all_ohlcv.extend(ohlcv)
        start_date = ohlcv[-1][0] + 1
    
    if not all_ohlcv:
        print(f"No data fetched for {symbol} with timeframe {timeframe}")
        return pd.DataFrame()  # Return an empty DataFrame if no data is fetched

    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df.index = df.index.tz_localize(None)  # Ensure tz-naive
    
    print(f"Fetched {len(df)} datapoints for {symbol} with timeframe {timeframe}")
    print(df.head())
    print(df.tail())
    
    return df

def add_indicators(df):
    # Wave Trend Oscillator
    ap = (df['high'] + df['low'] + df['close']) / 3
    esa = EMAIndicator(ap, WT_CHANNEL_LEN).ema_indicator()
    d = EMAIndicator(abs(ap - esa), WT_CHANNEL_LEN).ema_indicator()
    ci = (ap - esa) / (0.015 * d)
    df['wt1'] = EMAIndicator(ci, WT_AVERAGE_LEN).ema_indicator()
    df['wt2'] = df['wt1'].rolling(4).mean()

    # Awesome Oscillator
    df['ao'] = df['close'].rolling(AO_FAST_PERIOD).mean() - df['close'].rolling(AO_SLOW_PERIOD).mean()

    # RSI
    df['rsi'] = RSIIndicator(df['close'], window=RSI_PERIOD).rsi()

    # Moving Averages
    df['fastMa'] = EMAIndicator(df['close'], window=FAST_MA_PERIOD).ema_indicator()
    df['slowMa'] = EMAIndicator(df['close'], window=SLOW_MA_PERIOD).ema_indicator()

    # Bollinger Bands
    bb = BollingerBands(df['close'], window=BB_PERIOD, window_dev=BB_STD_DEV)
    df['bbMiddle'] = bb.bollinger_mavg()
    df['bbUpper'] = bb.bollinger_hband()
    df['bbLower'] = bb.bollinger_lband()

    # On-Balance Volume
    df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()

    # Average True Range
    df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=ATR_PERIOD).average_true_range()

    return df

def fetch_crypto_fear_greed_index():
    url = "https://api.alternative.me/fng/"
    response = requests.get(url)
    data = response.json()
    return data['data'][0]['value']

def calculate_fibonacci_levels(df):
    high = df['high'].max()
    low = df['low'].min()
    diff = high - low
    levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
    fib_levels = {level: low + diff * level for level in levels}
    return fib_levels

def fetch_order_book(symbol, limit=20):
    exchange = ccxt.binance()
    order_book = exchange.fetch_order_book(symbol, limit)
    return order_book

def fetch_funding_rate(symbol):
    try:
        exchange = ccxt.binance()
        # Check if the symbol is a perpetual futures contract
        markets = exchange.load_markets()
        if symbol in markets and markets[symbol]['type'] == 'future' and markets[symbol]['linear']:
            funding_rate = exchange.fetch_funding_rate(symbol)
            return funding_rate['fundingRate']
        else:
            return "N/A (Not a perpetual futures contract)"
    except Exception as e:
        print(f"Error fetching funding rate for {symbol}: {str(e)}")
        return "N/A (Error fetching data)"

def compile_chart_data(symbol, dataframes):
    compiled_data = {}
    for timeframe, df in dataframes.items():
        fib_levels = calculate_fibonacci_levels(df)
        
        compiled_data[timeframe] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "data_range": f"{df.index[0].isoformat()} to {df.index[-1].isoformat()}",
            "total_candles": len(df),
            "price_range": {
                "start": float(df['close'].iloc[0]),
                "end": float(df['close'].iloc[-1]),
                "low": float(df['low'].min()),
                "high": float(df['high'].max())
            },
            "volume_stats": {
                "total": float(df['volume'].sum()),
                "average": float(df['volume'].mean())
            },
            "indicator_latest": {
                "RSI": float(df['rsi'].iloc[-1]),
                "Wave Trend": {
                    "WT1": float(df['wt1'].iloc[-1]),
                    "WT2": float(df['wt2'].iloc[-1])
                },
                "Awesome Oscillator": float(df['ao'].iloc[-1]),
                "Moving Averages": {
                    "Fast": float(df['fastMa'].iloc[-1]),
                    "Slow": float(df['slowMa'].iloc[-1])
                },
                "Bollinger Bands": {
                    "Upper": float(df['bbUpper'].iloc[-1]),
                    "Middle": float(df['bbMiddle'].iloc[-1]),
                    "Lower": float(df['bbLower'].iloc[-1])
                },
                "On-Balance Volume": float(df['obv'].iloc[-1]),
                "Average True Range": float(df['atr'].iloc[-1])
            },
            "fibonacci_levels": {k: float(v) for k, v in fib_levels.items()}
        }
    return compiled_data

def main(symbol):
    is_crypto = '/' in symbol

    if symbol in ['SPX', 'VIX', 'QQQ', 'US10Y', 'US02Y', 'US30Y', 'GOLD', 'SILVER', 'OIL_CRUD']:
        # Use yfinance for market indices and assets
        symbol_map = {
            'SPX': '^GSPC',
            'VIX': '^VIX',
            'QQQ': 'QQQ',
            'US10Y': '^TNX',
            'US02Y': '^TWO',
            'US30Y': '^TYX',
            'GOLD': 'GC=F',
            'SILVER': 'SI=F',
            'OIL_CRUD': 'CL=F'
        }
        yf_symbol = symbol_map[symbol]
        dataframes = fetch_or_load_data(yf_symbol, TIMEFRAMES)
    else:
        dataframes = fetch_or_load_data(symbol, TIMEFRAMES)
    
    for timeframe in TIMEFRAMES:
        print(f"Adding indicators for {timeframe} timeframe...")
        dataframes[timeframe] = add_indicators(dataframes[timeframe])

    # Fetch additional data (only for crypto assets)
    if is_crypto:
        fear_greed_index = fetch_crypto_fear_greed_index()
        order_book = fetch_order_book(symbol)
        funding_rate = fetch_funding_rate(symbol)
    else:
        fear_greed_index = "N/A"
        order_book = "N/A"
        funding_rate = "N/A"

    print("Compiling chart data for analysis...")
    compiled_data = compile_chart_data(symbol, dataframes)

    # Add additional data to compiled_data
    compiled_data['symbol'] = symbol
    compiled_data['fear_greed_index'] = fear_greed_index
    compiled_data['order_book'] = order_book
    compiled_data['funding_rate'] = funding_rate

    return compiled_data

if __name__ == "__main__":
    # You can add any testing or standalone functionality here
    pass