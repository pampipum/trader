import requests
import os
from datetime import datetime, timedelta

# Load API key from environment variable
API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')

BASE_URL = 'https://www.alphavantage.co/query'

def get_market_news(symbols=None, topics=None, time_from=None, limit=10):
    """
    Fetch market news and sentiment data.
    """
    params = {
        'function': 'NEWS_SENTIMENT',
        'apikey': API_KEY,
        'limit': limit
    }
    
    if symbols:
        params['tickers'] = ','.join(symbols)
    if topics:
        params['topics'] = ','.join(topics)
    if time_from:
        params['time_from'] = time_from.strftime('%Y%m%dT%H%M')
    
    response = requests.get(BASE_URL, params=params)
    return response.json()

def get_top_gainers_losers():
    """
    Fetch top gainers, losers, and most actively traded tickers.
    """
    params = {
        'function': 'TOP_GAINERS_LOSERS',
        'apikey': API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    return response.json()

def get_market_analytics(symbols, start_date, end_date, interval='DAILY', calculations=None):
    """
    Fetch advanced analytics for given symbols.
    """
    if calculations is None:
        calculations = ['MEAN', 'STDDEV', 'CORRELATION']
    
    params = {
        'function': 'ANALYTICS_FIXED_WINDOW',
        'SYMBOLS': ','.join(symbols),
        'RANGE': start_date.strftime('%Y-%m-%d'),
        'RANGE': end_date.strftime('%Y-%m-%d'),
        'INTERVAL': interval,
        'OHLC': 'close',
        'CALCULATIONS': ','.join(calculations),
        'apikey': API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    return response.json()

def fetch_market_data():
    """
    Fetch comprehensive market data for analysis.
    """
    # Get market news for the last 24 hours
    yesterday = datetime.now() - timedelta(days=1)
    news_data = get_market_news(time_from=yesterday, limit=20)
    
    # Get top gainers and losers
    market_movers = get_top_gainers_losers()
    
    # Get analytics for major indices (adjust symbols as needed)
    indices = ['SPY', 'QQQ', 'IWM']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    analytics_data = get_market_analytics(indices, start_date, end_date)
    
    return {
        'news': news_data,
        'market_movers': market_movers,
        'analytics': analytics_data
    }

if __name__ == '__main__':
    market_data = fetch_market_data()
    print(market_data)