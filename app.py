from flask import Flask, render_template, request, jsonify, current_app
import sys
import logging
import yfinance as yf
sys.path.append(r'C:\Users\andre\OneDrive\Desktop\Play\Dailystock')
import claudeanalize
from markdown2 import Markdown
from datetime import datetime, timedelta
from market_analysis import analyze_market, analyze_asset
from openai_analysis import analyze_with_openai
from system_prompt import SYSTEM_PROMPT
import traceback

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CRYPTO_PAIRS = {
    'BTC/USDT': 'BTC-USD',
    'SOL/USDT': 'SOL-USD',
    'SOL/BTC': 'SOL-BTC',
    'ETH/USDT': 'ETH-USD'
}

MACRO_ASSETS = ['SPX', 'VIX', 'QQQ', 'US10Y', 'US02Y', 'US30Y', 'GOLD', 'SILVER', 'OIL_CRUD']

def fetch_symbols():
    all_symbols = []
    
    # Fetch crypto symbols
    for ccxt_symbol, yf_symbol in CRYPTO_PAIRS.items():
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            if info and 'symbol' in info:
                all_symbols.append(ccxt_symbol)  # Use the CCXT symbol format
        except Exception as e:
            logger.error(f"Error fetching {yf_symbol} from yfinance: {str(e)}")
    
    # Add macro assets
    all_symbols.extend(MACRO_ASSETS)
    
    return all_symbols

def perform_analysis(symbol, model):
    try:
        if symbol in CRYPTO_PAIRS:
            yf_symbol = CRYPTO_PAIRS[symbol]
        else:
            yf_symbol = symbol

        if model == 'claude':
            analysis_result = analyze_asset(yf_symbol, symbol)
            if 'error' in analysis_result:
                raise Exception(analysis_result['error'])
            return analysis_result['analysis']
        elif model == 'openai':
            compiled_data = claudeanalize.main(yf_symbol)
            return analyze_with_openai(compiled_data, SYSTEM_PROMPT)
        else:
            raise ValueError(f"Invalid model: {model}")
    except Exception as e:
        logger.error(f"Error in perform_analysis: {str(e)}")
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/fetch_symbols')
def fetch_symbols_route():
    return jsonify(fetch_symbols())

@app.route('/analyze', methods=['POST'])
def analyze():
    symbol = request.form['symbol']
    model = request.form.get('model', 'claude')  # Default to Claude if not specified
    
    try:
        analysis = perform_analysis(symbol, model)
        
        analysis_data = {
            'analysis': analysis,
            'symbol': symbol,
            'model': model,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(analysis_data)
    except Exception as e:
        return jsonify({'error': str(e), 'symbol': symbol, 'model': model, 'timestamp': datetime.now().isoformat()})

@app.route('/search_ticker')
def search_ticker():
    query = request.args.get('query', '').strip().upper()
    if not query:
        return jsonify([])
    
    try:
        # Search for tickers
        tickers = yf.Ticker(query).info
        if tickers:
            return jsonify([query])  # Return the valid ticker
        else:
            return jsonify([])  # No valid ticker found
    except Exception as e:
        print(f"Error searching for ticker: {str(e)}")
        return jsonify([])

@app.route('/analyze_market', methods=['POST'])
def analyze_market_route():
    try:
        current_app.config['MARKET_ANALYSIS_PROGRESS'] = 0
        results = analyze_market()
        if results['status'] == 'error':
            logger.error(f"Error in market analysis: {results['error_message']}")
            return jsonify({
                "error": results['error_message'],
                "individual_analyses": results['individual_analyses'],
                "failed_analyses": results['failed_analyses']
            }), 500
        return jsonify(results)
    except Exception as e:
        logger.error(f"Unexpected error in analyze_market_route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Unexpected error: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500

if __name__ == '__main__':
    app.run(debug=True)