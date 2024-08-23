import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus
import json
import time
from datetime import datetime, timedelta
import logging
import anthropic
from market_analysis import analyze_market, analyze_asset

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Alpaca API configuration
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_PAPER = True  # Set to True for paper trading

CACHE_DIR = 'analysis_cache'
MARKET_CACHE_FILE = os.path.join(CACHE_DIR, 'market_analysis.json')
CACHE_EXPIRY = timedelta(hours=24)  # Cache expires after 24 hours

# Initialize Alpaca clients
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
stock_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

# Update symbol mappings
SYMBOL_MAPPING = {
    'OIL_CRUD': 'CL=F',
    'US30Y': '^TYX'
}

def get_portfolio():
    """Fetch the current portfolio from Alpaca"""
    account = trading_client.get_account()
    positions = trading_client.get_all_positions()
    
    portfolio = {
        'cash': float(account.cash),
        'positions': {pos.symbol: int(pos.qty) for pos in positions}
    }
    return portfolio

def get_transactions(start_date=None, end_date=None, limit=50):
    """Fetch transactions from Alpaca"""
    try:
        # Assuming trading_client is already initialized elsewhere in your code
        # If not, you should initialize it here:
        # trading_client = TradingClient('api-key', 'secret-key', paper=True)

        # Set up request parameters
        request_params = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,  # We want OPEN orders
            limit=limit
        )

        if start_date:
            request_params.after = start_date.isoformat()
        if end_date:
            request_params.until = end_date.isoformat()

        # Get orders
        orders = trading_client.get_orders(filter=request_params)

        # Convert orders to our transaction format
        transactions = [
            {
                'timestamp': order.submitted_at.isoformat(),
                'symbol': order.symbol,
                'quantity': float(order.filled_qty),
                'side': order.side.value,
                'price': float(order.filled_avg_price) if order.filled_avg_price else None
            }
            for order in orders
        ]

        logging.info(f"Retrieved {len(transactions)} transactions from Alpaca")
        return transactions
    except Exception as e:
        logging.error(f"Error fetching orders from Alpaca: {str(e)}")
        return []

def get_current_price(symbol, max_retries=3):
    symbol = SYMBOL_MAPPING.get(symbol, symbol)  # Use mapped symbol if available
    for attempt in range(max_retries):
        try:
            request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            latest_quote = stock_client.get_stock_latest_quote(request_params)
            
            if latest_quote and symbol in latest_quote:
                return (latest_quote[symbol].ask_price + latest_quote[symbol].bid_price) / 2
            else:
                logging.warning(f"No data available for symbol: {symbol} (Attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            logging.error(f"Error fetching price for {symbol}: {str(e)} (Attempt {attempt + 1}/{max_retries})")
        
        time.sleep(1)  # Wait for 1 second before retrying
    
    raise ValueError(f"Unable to fetch price for symbol: {symbol} after {max_retries} attempts")

def calculate_pnl():
    """Calculate PnL using Alpaca account information"""
    account = trading_client.get_account()
    initial_balance = float(account.last_equity)  # You might want to store the initial balance somewhere
    current_equity = float(account.equity)
    return current_equity - initial_balance

def execute_trade(symbol, quantity, side):
    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=abs(quantity),
        side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
        time_in_force=TimeInForce.DAY
    )
    
    try:
        order = trading_client.submit_order(order_data)
        logging.info(f"Order placed: {side} {abs(quantity)} shares of {symbol}")
        return order
    except Exception as e:
        logging.error(f"Error placing order for {symbol}: {str(e)}")
        return None

def analyze_portfolio_with_claude(portfolio_data, market_analysis, asset_reports):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    message = f"""
    Here's the current portfolio data, market analysis, and asset reports:

    Portfolio:
    {json.dumps(portfolio_data, indent=2)}

    Market Analysis:
    {market_analysis}

    Asset Reports:
    {json.dumps(asset_reports, indent=2)}

    Based on this information, provide a portfolio analysis and trading recommendations in JSON format.
    
    Provide your analysis and recommendations in the following JSON format:

    ```json
    {{
      "portfolio_summary": "Brief overview of current portfolio status and performance",
      "market_outlook": "Brief summary of current market conditions",
      "trades": [
        {{
          "symbol": "AAPL",
          "action": "buy/sell/hold",
          "quantity": 10,
          "reasoning": "Concise explanation for the decision"
        }}
      ],
      "risk_assessment": "Brief assessment of current portfolio risk and any recommended changes",
      "cash_management": "Recommendation for cash allocation"
    }}
    ```

    Ensure your entire response is valid JSON that can be parsed.
    """

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=2000,
            temperature=0.5,
            system="You are an AI assistant that provides portfolio analysis and trading recommendations.",
            messages=[
                {"role": "user", "content": message}
            ]
        )
        
        logging.info(f"Raw response from Claude API: {response.content}")
        
        # Extract JSON from the response
        content = response.content[0].text
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        json_str = content[json_start:json_end]
        
        try:
            parsed_response = json.loads(json_str)
            return parsed_response
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse extracted JSON: {e}")
            logging.error(f"Extracted content: {json_str}")
            return None

    except Exception as e:
        logging.error(f"Error in analyze_portfolio_with_claude: {str(e)}")
        return None

def analyze_and_trade():
    portfolio = get_portfolio()
    
    # Check if we have a valid cached market analysis
    if os.path.exists(MARKET_CACHE_FILE):
        with open(MARKET_CACHE_FILE, 'r') as f:
            cached_analysis = json.load(f)
        
        cache_time = datetime.fromisoformat(cached_analysis['timestamp'])
        if datetime.now() - cache_time < CACHE_EXPIRY:
            market_analysis = cached_analysis
            logging.info("Using cached market analysis")
        else:
            market_analysis = perform_market_analysis()
    else:
        market_analysis = perform_market_analysis()

    if market_analysis['status'] != 'success':
        logging.error("Failed to get market analysis")
        return

    # Filter out assets that failed analysis
    valid_assets = {symbol: analysis for symbol, analysis in market_analysis['individual_analyses'].items() 
                    if 'error' not in analysis}

    asset_reports = {symbol: analyze_asset(symbol, symbol) for symbol in set(list(portfolio['positions'].keys()) + list(valid_assets.keys()))}

    analysis_result = analyze_portfolio_with_claude(portfolio, market_analysis['market_analysis'], asset_reports)
    
    if analysis_result is None:
        logging.error("Failed to get portfolio analysis from Claude")
        return
    
    process_portfolio_analysis(analysis_result)

def perform_market_analysis():
    try:
        market_analysis = analyze_market()
        
        # Cache the market analysis
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(MARKET_CACHE_FILE, 'w') as f:
            json.dump({**market_analysis, 'timestamp': datetime.now().isoformat()}, f)
        
        return market_analysis
    except Exception as e:
        logging.error(f"Error in market analysis: {str(e)}")
        return {'status': 'error', 'error': str(e)}


def process_portfolio_analysis(analysis):
    logging.info(f"Portfolio Summary: {analysis['portfolio_summary']}")
    logging.info(f"Market Outlook: {analysis['market_outlook']}")
    logging.info(f"Risk Assessment: {analysis['risk_assessment']}")
    logging.info(f"Cash Management: {analysis['cash_management']}")
    
    for trade in analysis['trades']:
        symbol = trade['symbol']
        quantity = trade['quantity']
        action = trade['action']
        
        # Skip Solana trades
        if 'SOL' in symbol:
            logging.info(f"Skipping Solana trade: {action} {quantity} {symbol}")
            continue
        
        if action == 'buy':
            order = execute_trade(symbol, quantity, OrderSide.BUY)
        elif action == 'sell':
            order = execute_trade(symbol, quantity, OrderSide.SELL)
        else:
            logging.info(f"Holding position in {symbol}")
        
        logging.info(f"{action.capitalize()} {quantity} shares of {symbol}. Reasoning: {trade['reasoning']}")

def generate_portfolio_report():
    portfolio = get_portfolio()
    transactions = get_transactions(start_date=datetime.now() - timedelta(days=30))  # Get last 30 days of transactions
    pnl = calculate_pnl()

    report = f"""
    # Portfolio Report

    ## Current Portfolio
    Cash: ${portfolio['cash']:.2f}
    
    Positions:
    """
    for symbol, quantity in portfolio['positions'].items():
        current_price = get_current_price(symbol)
        value = quantity * current_price
        report += f"- {symbol}: {quantity} shares, Current Price: ${current_price:.2f}, Total Value: ${value:.2f}\n"

    report += f"""
    ## Performance
    Profit/Loss: ${pnl:.2f}

    ## Recent Transactions
    """
    for transaction in transactions[:10]:  # Show last 10 transactions
        price_str = f"at ${transaction['price']:.2f}" if transaction['price'] is not None else "(price not available)"
        report += f"- {transaction['timestamp']}: {transaction['side']} {transaction['quantity']} shares of {transaction['symbol']} {price_str}\n"

    return report

def main():
    analyze_and_trade()
    report = generate_portfolio_report()
    print(report)
    
    # Save report to a file
    with open('portfolio_report.md', 'w') as f:
        f.write(report)

if __name__ == "__main__":
    main()