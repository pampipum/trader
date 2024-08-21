import logging
import json
from datetime import datetime, timedelta
from flask import current_app
import os
import pandas as pd
from claudeanalize import (
    fetch_or_load_data, add_indicators, compile_chart_data, TIMEFRAMES
)
from api_logic import analyze_with_claude
from system_prompt import SYSTEM_PROMPT, MARKET_ANALYSIS_PROMPT
from alpha_vantage_api import fetch_market_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = 'analysis_cache'
MARKET_CACHE_FILE = os.path.join(CACHE_DIR, 'market_analysis.json')
CACHE_EXPIRY = timedelta(hours=1)

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

def update_progress(progress):
    try:
        current_app.config['MARKET_ANALYSIS_PROGRESS'] = progress
    except RuntimeError:
        logger.warning("Working outside of application context. Progress update skipped.")

def analyze_asset(symbol, original_symbol):
    try:
        current_time = datetime.now()
        cache_file = os.path.join(CACHE_DIR, f'{symbol.replace("^", "").replace("/", "-").replace("=", "")}_analysis.json')

        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_analysis = json.load(f)
            
            if 'timestamp' in cached_analysis:
                cache_time = datetime.fromisoformat(cached_analysis['timestamp'])
                if current_time - cache_time < CACHE_EXPIRY:
                    return cached_analysis

        data = fetch_or_load_data(symbol, TIMEFRAMES)
        
        if not data or not isinstance(data, dict):
            raise ValueError(f"Invalid data returned for {original_symbol}")

        available_timeframes = list(data.keys())
        
        for timeframe in available_timeframes:
            if timeframe not in data or not isinstance(data[timeframe], pd.DataFrame):
                raise ValueError(f"Missing or invalid data for {original_symbol} at {timeframe}")
            data[timeframe] = add_indicators(data[timeframe])
        
        compiled_data = compile_chart_data(symbol, data)
        
        if not isinstance(compiled_data, dict):
            raise ValueError(f"Invalid compiled data for {original_symbol}")
        
        response = analyze_with_claude(compiled_data, SYSTEM_PROMPT)
        
        result = {
            'symbol': original_symbol,
            'analysis': response,
            'timestamp': current_time.isoformat(),
            'available_timeframes': available_timeframes
        }

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
    
    update_progress(0)  # Initialize progress

    individual_analyses = {}
    failed_analyses = []
    assets_to_analyze = list(MACRO_ASSETS.items()) + list(TRADE_ASSETS.items())
    total_assets = len(assets_to_analyze)

    for i, (asset, symbol) in enumerate(assets_to_analyze):
        logger.info(f"Analyzing asset: {asset} ({symbol})")
        analysis = analyze_asset(symbol, asset)
        individual_analyses[asset] = analysis
        
        if 'error' in analysis:
            failed_analyses.append(asset)
            logger.error(f"Analysis failed for {asset}: {analysis['error']}")
        
        progress = int(((i + 1) / total_assets) * 70)  # Up to 70% for individual analyses
        update_progress(progress)

    logger.info("Fetching data from Alpha Vantage API")
    alpha_vantage_data = fetch_market_data()
    update_progress(80)

    market_data = {
        "macro_assets": {asset: analysis for asset, analysis in individual_analyses.items() if asset in MACRO_ASSETS},
        "trade_assets": {asset: analysis for asset, analysis in individual_analyses.items() if asset in TRADE_ASSETS},
        "failed_analyses": failed_analyses,
        "alpha_vantage_data": alpha_vantage_data
    }
    
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

def format_analysis_as_html(analysis_data):
    html_content = f"""
    <h1>Elite Market Analysis Daily Briefing</h1>

    <div class="section">
    <h2>1. Market Overview</h2>
    <p>{analysis_data['market_overview']}</p>
    </div>

    <div class="section">
    <h2>2. Key Asset Performance</h2>
    <table>
    <tr><th>Asset</th><th>1D % Change</th><th>1W % Change</th><th>1M % Change</th></tr>
    """

    for asset, changes in analysis_data['asset_performance'].items():
        html_content += f"<tr><td>{asset}</td><td>{changes['1D']}%</td><td>{changes['1W']}%</td><td>{changes['1M']}%</td></tr>"

    html_content += """
    </table>
    </div>

    <!-- Add other sections here -->

    <div class="section">
    <h2>10. Conclusion and Outlook</h2>
    <p>{analysis_data['conclusion']}</p>
    </div>
    """

    return html_content

if __name__ == '__main__':
    result = analyze_market()
    print(json.dumps(result, indent=2))