import os
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import requests
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator
from api_logic import analyze_with_claude
from system_prompt import SYSTEM_PROMPT
from fundingrate import funding_dydx

# Load environment variables
load_dotenv()

# Get CoinAPI key from .env file
COINAPI_KEY = os.getenv('COINAPI_KEY')

# Updated Parameters
TIMEFRAMES = ['90m', '1d', '1wk']
LOOKBACK_YEARS = 1
CACHE_EXPIRY = {'90m': timedelta(hours=2), '1d': timedelta(days=1), '1wk': timedelta(weeks=1)}


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

# Updated timeframe mapping for crypto exchanges
CRYPTO_TIMEFRAME_MAP = {
    '90m': '90m',
    '1d': '1d',
    '1wk': '1w'
}

def fetch_or_load_data(symbol, timeframes, filename_prefix='data'):
    dataframes = {}

    for timeframe in timeframes:
        filename = os.path.join(DATA_CACHE_DIR, f'{filename_prefix}_{symbol.replace("/", "").replace("^", "").replace("-", "")}__{timeframe}.pkl')
        
        if os.path.exists(filename):
            print(f"Loading {timeframe} data from {filename}")
            with open(filename, 'rb') as f:
                df, last_updated = pickle.load(f)
            
            df.index = pd.to_datetime(df.index).tz_localize(None)
            
            # Check if cache has expired
            if datetime.now() - last_updated > CACHE_EXPIRY[timeframe]:
                print(f"Cache expired for {timeframe}, fetching new data...")
                df = fetch_financial_data(symbol, timeframe)
                last_updated = datetime.now()
            else:
                # Update data for non-expired cache
                end_date = datetime.now().replace(tzinfo=None)
                start_date = df.index[-1].replace(tzinfo=None)
                latest_data = fetch_financial_data(symbol, timeframe, start=start_date, end=end_date)
                if not latest_data.empty:
                    latest_data.index = latest_data.index.tz_localize(None)
                    df = pd.concat([df, latest_data[~latest_data.index.isin(df.index)]])
        else:
            print(f"No cache found for {timeframe}, fetching all data...")
            df = fetch_financial_data(symbol, timeframe)
            last_updated = datetime.now()
        
        if not df.empty:
            df.index = pd.to_datetime(df.index).tz_localize(None)
            
            # Filter data based on timeframe
            if timeframe == '90m':
                cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=59)
            else:
                cutoff_date = datetime.now().replace(tzinfo=None) - timedelta(days=365*LOOKBACK_YEARS)
            df = df[df.index > cutoff_date]
            
            # Save updated data to cache
            with open(filename, 'wb') as f:
                pickle.dump((df, last_updated), f)
            
            print(f"\nLatest {timeframe} data points:")
            print(df.tail().to_string())
            dataframes[timeframe] = df
        else:
            print(f"No data available for {symbol} with timeframe {timeframe}")
    
    return dataframes

def fetch_financial_data(symbol, timeframe, start=None, end=None):
    end = end or datetime.now()
    
    if timeframe == '90m':
        # For 90m data, only fetch the last 59 days
        start = end - timedelta(days=59)
    elif start is None:
        if timeframe == '1d':
            start = end - timedelta(days=365*LOOKBACK_YEARS)
        elif timeframe == '1wk':
            start = end - timedelta(days=365*LOOKBACK_YEARS*2)  # Fetch more data for weekly timeframe

    # Convert timeframe to yfinance interval
    interval = timeframe

    try:
        df = yf.download(symbol.replace('/', '-'), start=start, end=end, interval=interval)
    except Exception as e:
        print(f"Error downloading data for {symbol}: {str(e)}")
        return pd.DataFrame()

    if df.empty:
        print(f"No data available for {symbol} with timeframe {timeframe}")
        return df

    df.index.name = 'timestamp'
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
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

def is_crypto(symbol):
    # Simple check to determine if a symbol is likely a cryptocurrency
    return not symbol.startswith('^') and '/' in symbol

def fetch_order_book(symbol, limit=20):
    if not is_crypto(symbol):
        print(f"Skipping order book fetch for non-crypto asset: {symbol}")
        return None

    try:
        # Convert symbol to CoinAPI format (e.g., 'BTC/USDT' to 'DYDX_PERP_BTC_USDT')
        base, quote = symbol.split('/')
        coinapi_symbol = f"DYDX_PERP_{base}_{quote}"

        url = f"https://rest.coinapi.io/v1/orderbooks/{coinapi_symbol}/current"
        headers = {'X-CoinAPI-Key': COINAPI_KEY}
        response = requests.get(url, headers=headers, timeout=10)  # Add timeout

        if response.status_code == 200:
            data = response.json()
            return {
                'bids': data['bids'][:limit],
                'asks': data['asks'][:limit]
            }
        else:
            print(f"Error fetching order book for {symbol}: HTTP Status {response.status_code}")
            print(f"Response content: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching order book for {symbol}: {str(e)}")
        return None
    except Exception as e:
        print(f"Error fetching order book for {symbol}: {str(e)}")
        return None

def fetch_funding_rate(symbol):
    if not is_crypto(symbol):
        print(f"Skipping funding rate fetch for non-crypto asset: {symbol}")
        return None

    try:
        # Convert symbol to dYdX format if necessary (e.g., 'BTC/USDT' to 'BTC-USD')
        base, _ = symbol.split('/')
        dydx_symbol = f"{base}-USD"

        funder = funding_dydx([dydx_symbol])
        rates = funder.get_formatted_funding_rates()
        if not rates.empty:
            return rates.iloc[0]['rate']  # Return the most recent funding rate
        else:
            print(f"No funding rate data available for {symbol}")
            return None
    except Exception as e:
        print(f"Error fetching funding rate for {symbol}: {str(e)}")
        return None

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
    
    if is_crypto(symbol):
        # Fetch order book data
        order_book = fetch_order_book(symbol)
        if order_book:
            compiled_data['order_book'] = order_book
        
        # Fetch funding rate data
        funding_rate = fetch_funding_rate(symbol)
        if funding_rate is not None:
            compiled_data['funding_rate'] = funding_rate
    
    return compiled_data

def main(symbol):
    dataframes = fetch_or_load_data(symbol, TIMEFRAMES)
    
    for timeframe in TIMEFRAMES:
        print(f"Adding indicators for {timeframe} timeframe...")
        dataframes[timeframe] = add_indicators(dataframes[timeframe])

    print("Compiling chart data for analysis...")
    compiled_data = compile_chart_data(symbol, dataframes)

    # Add additional data to compiled_data
    compiled_data['symbol'] = symbol
    if is_crypto(symbol):
        compiled_data['fear_greed_index'] = fetch_crypto_fear_greed_index()

    print("Performing analysis with Claude...")
    analysis = analyze_with_claude(compiled_data, SYSTEM_PROMPT)

    return {
        'compiled_data': compiled_data,
        'analysis': analysis
    }

if __name__ == "__main__":
    # You can add any testing or standalone functionality here
    symbol = "BTC/USD"  # Example symbol
    result = main(symbol)
    print(f"Analysis for {symbol}:")
    print(result['analysis'])