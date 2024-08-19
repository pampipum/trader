import logging
import json
from datetime import datetime, timedelta
from flask import current_app
import os
from claudeanalize import (
    fetch_or_load_data, add_indicators, compile_chart_data, TIMEFRAMES
)
from api_logic import analyze_with_claude
from system_prompt import SYSTEM_PROMPT, MARKET_ANALYSIS_PROMPT
from alpha_vantage_api import fetch_market_data  # Import the new function
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = 'analysis_cache'
MARKET_CACHE_FILE = os.path.join(CACHE_DIR, 'market_analysis.json')
CACHE_EXPIRY = timedelta(hours=24)

MACRO_ASSETS = {
    'VIX': '^VIX',
    'QQQ': 'QQQ',
    'US10Y': '^TNX',
    'US02Y': '^IRX',
    'US30Y': '^TYX',
    'GOLD': 'GC=F',
    'OIL_CRUD': 'CL=F',
    'SPX': '^GSPC'
}

TRADE_ASSETS = {
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'NVDA': 'NVDA',
    'TSM': 'TSM',
    'GOOGL': 'GOOGL',
    'BTC/USDT': 'BTC-USD',
    'SOL/USDT': 'SOL-USD',
    'SOL/BTC': 'SOL-BTC',
    'ETH/USDT': 'ETH-USD'
}


def analyze_asset(symbol, original_symbol):
    try:
        current_time = datetime.now()
        cache_file = os.path.join(CACHE_DIR, f'{symbol.replace("^", "").replace("/", "-").replace("=", "")}_analysis.json')

        # Check if a recent cached analysis exists
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_analysis = json.load(f)
            
            if 'timestamp' in cached_analysis:
                cache_time = datetime.fromisoformat(cached_analysis['timestamp'])
                if current_time - cache_time < CACHE_EXPIRY:
                    return cached_analysis

        # If no recent cache exists, perform the analysis
        data = fetch_or_load_data(symbol, TIMEFRAMES)
        
        if isinstance(data, str):
            logger.error(f"fetch_or_load_data returned a string for {original_symbol}: {data}")
            return {
                'symbol': original_symbol,
                'error': f'Data fetch failed: {data}',
                'timestamp': current_time.isoformat()
            }
        
        if not isinstance(data, dict):
            logger.error(f"fetch_or_load_data returned unexpected type for {original_symbol}: {type(data)}")
            return {
                'symbol': original_symbol,
                'error': f'Unexpected data type: {type(data)}',
                'timestamp': current_time.isoformat()
            }
        
        for timeframe in TIMEFRAMES:
            if timeframe not in data:
                logger.error(f"Missing timeframe {timeframe} for {original_symbol}")
                return {
                    'symbol': original_symbol,
                    'error': f'Missing timeframe {timeframe}',
                    'timestamp': current_time.isoformat()
                }
            if not isinstance(data[timeframe], pd.DataFrame):
                logger.error(f"Invalid data type for {original_symbol} at {timeframe}: {type(data[timeframe])}")
                return {
                    'symbol': original_symbol,
                    'error': f'Invalid data type for timeframe {timeframe}',
                    'timestamp': current_time.isoformat()
                }
            data[timeframe] = add_indicators(data[timeframe])
        
        compiled_data = compile_chart_data(symbol, data)
        
        if isinstance(compiled_data, str):
            logger.error(f"compile_chart_data returned a string for {original_symbol}: {compiled_data}")
            return {
                'symbol': original_symbol,
                'error': f'Data compilation failed: {compiled_data}',
                'timestamp': current_time.isoformat()
            }
        
        if not isinstance(compiled_data, dict):
            logger.error(f"compile_chart_data returned unexpected type for {original_symbol}: {type(compiled_data)}")
            return {
                'symbol': original_symbol,
                'error': f'Unexpected compiled data type: {type(compiled_data)}',
                'timestamp': current_time.isoformat()
            }
        
        response = analyze_with_claude(compiled_data, SYSTEM_PROMPT)
        
        result = {
            'symbol': original_symbol,
            'analysis': response,
            'timestamp': current_time.isoformat()
        }

        # Cache the analysis
        with open(cache_file, 'w') as f:
            json.dump(result, f)

        return result
    except Exception as e:
        logger.error(f"Error analyzing asset {original_symbol}: {str(e)}")
        return {
            'symbol': original_symbol,
            'error': f'Analysis failed: {str(e)}',
            'timestamp': current_time.isoformat()
        }

def analyze_market():
    current_time = datetime.now()
    
    def update_progress(progress):
        current_app.config['MARKET_ANALYSIS_PROGRESS'] = progress

    individual_analyses = {}
    failed_analyses = []
    assets_to_analyze = []

    update_progress(0)  # Initialize progress

    # Analyze all assets, including crypto pairs
    for asset, symbol in {**MACRO_ASSETS, **TRADE_ASSETS}.items():
        cache_file = os.path.join(CACHE_DIR, f'{symbol.replace("^", "").replace("/", "-").replace("=", "")}_analysis.json')
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_analysis = json.load(f)
            
            if 'timestamp' in cached_analysis:
                cache_time = datetime.fromisoformat(cached_analysis['timestamp'])
                if current_time - cache_time < CACHE_EXPIRY:
                    individual_analyses[asset] = cached_analysis
                    continue
        
        assets_to_analyze.append((asset, symbol))

    total_assets = len(assets_to_analyze)
    
    for i, (asset, symbol) in enumerate(assets_to_analyze):
        logger.info(f"Analyzing asset: {asset} ({symbol})")
        analysis = analyze_asset(symbol, asset)
        individual_analyses[asset] = analysis
        
        if 'error' in analysis:
            failed_analyses.append(asset)
            logger.error(f"Analysis failed for {asset}: {analysis['error']}")
        else:
            # Cache the individual asset analysis
            cache_file = os.path.join(CACHE_DIR, f'{symbol.replace("^", "").replace("/", "-").replace("=", "")}_analysis.json')
            with open(cache_file, 'w') as f:
                json.dump(analysis, f)
        
        progress = int(((i + 1) / total_assets) * 70)  # Up to 70% for individual analyses
        update_progress(progress)

    # Fetch data from Alpha Vantage API
    logger.info("Fetching data from Alpha Vantage API")
    alpha_vantage_data = fetch_market_data()
    update_progress(80)

    # Prepare data for market analysis
    market_data = {
        "macro_assets": {asset: analysis for asset, analysis in individual_analyses.items() if asset in MACRO_ASSETS},
        "trade_assets": {asset: analysis for asset, analysis in individual_analyses.items() if asset in TRADE_ASSETS},
        "failed_analyses": failed_analyses,
        "alpha_vantage_data": alpha_vantage_data
    }
    
    # Perform overall market analysis
    logger.info("Performing overall market analysis")
    market_analysis = analyze_with_claude(market_data, MARKET_ANALYSIS_PROMPT)
    update_progress(100)  # Market analysis complete

    result = {
        "status": "success",
        "market_analysis": market_analysis,
        "individual_analyses": individual_analyses,
        "failed_analyses": failed_analyses,
        "alpha_vantage_data": alpha_vantage_data,
        "timestamp": current_time.isoformat()
    }

    return result

if __name__ == '__main__':
    result = analyze_market()
    print(json.dumps(result, indent=2))