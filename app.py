from flask import Flask, render_template, request, jsonify, current_app
import sys
import logging
import ccxt
sys.path.append(r'C:\Users\andre\OneDrive\Desktop\Play\Dailystock')
import claudeanalize
from markdown2 import Markdown
from datetime import datetime, timedelta
from market_analysis import analyze_market
from openai_analysis import analyze_with_openai
from system_prompt import SYSTEM_PROMPT
import yfinance as yf
import traceback

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def perform_analysis(symbol, model='claude'):
    try:
        compiled_data = claudeanalize.main(symbol)
        
        if model == 'claude':
            analysis = claudeanalize.analyze_with_claude(compiled_data, SYSTEM_PROMPT)
        elif model == 'openai':
            analysis = analyze_with_openai(compiled_data, SYSTEM_PROMPT)
        else:
            raise ValueError(f"Invalid model: {model}")
        
        # Convert Markdown to HTML
        markdowner = Markdown(extras=["fenced-code-blocks", "cuddled-lists"])
        html_content = markdowner.convert(analysis)
        
        logger.info(f"Analysis completed for {symbol} using {model} model.")
        return html_content
    except Exception as e:
        logger.error(f"Error performing analysis for {symbol} using {model} model: {str(e)}")
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/fetch_symbols')
def fetch_symbols():
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    crypto_pairs = list(markets.keys())
    
    additional_symbols = ['SPX', 'VIX', 'QQQ', 'US10Y', 'US02Y', 'US30Y', 'GOLD', 'SILVER', 'OIL_CRUD']
    
    all_symbols = crypto_pairs + additional_symbols
    return jsonify(all_symbols)

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

last_progress_update = {'time': datetime.now(), 'progress': 0}

@app.route('/market_analysis_progress')
def market_analysis_progress():
    global last_progress_update
    current_time = datetime.now()
    
    # Only update progress if it's been more than 1 second since the last update
    if current_time - last_progress_update['time'] > timedelta(seconds=1):
        progress = current_app.config.get('MARKET_ANALYSIS_PROGRESS', 0)
        last_progress_update = {'time': current_time, 'progress': progress}
    else:
        progress = last_progress_update['progress']
    
    return jsonify({'progress': progress})



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