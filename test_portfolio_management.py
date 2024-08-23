import unittest
from unittest.mock import patch, MagicMock
import json
import os
from datetime import datetime, timedelta
from alpaca.trading.enums import OrderSide
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockLatestQuoteRequest

# Import the functions and classes we want to test
from portfolio_management_script import (
    load_portfolio, save_portfolio, load_transactions, save_transaction,
    get_current_price, calculate_pnl, execute_trade, update_portfolio,
    analyze_and_trade, generate_portfolio_report, main
)

class TestPortfolioManagement(unittest.TestCase):

    def setUp(self):
        # Set up any necessary test data
        self.test_portfolio = {'cash': 1000, 'positions': {'AAPL': 10, 'GOOGL': 5}}
        self.test_transaction = {
            'timestamp': datetime.now().isoformat(),
            'symbol': 'AAPL',
            'quantity': 2,
            'side': 'BUY',
            'price': 150.0
        }

    def tearDown(self):
        # Clean up any files created during tests
        files_to_remove = ['portfolio.json', 'transactions.json']
        for file in files_to_remove:
            if os.path.exists(file):
                os.remove(file)

    def test_load_save_portfolio(self):
        save_portfolio(self.test_portfolio)
        loaded_portfolio = load_portfolio()
        self.assertEqual(self.test_portfolio, loaded_portfolio)

    def test_load_save_transaction(self):
        save_transaction(self.test_transaction)
        loaded_transactions = load_transactions()
        self.assertEqual(1, len(loaded_transactions))
        self.assertEqual(self.test_transaction, loaded_transactions[0])

    @patch('portfolio_management_script.stock_client')
    def test_get_current_price(self, mock_stock_client):
        mock_quote = {
            'AAPL': MagicMock(ask_price=151.0, bid_price=150.0)
        }
        mock_stock_client.get_stock_latest_quote.return_value = mock_quote
        
        price = get_current_price('AAPL')
        
        self.assertEqual(150.5, price)
        mock_stock_client.get_stock_latest_quote.assert_called_once()
        
        args, kwargs = mock_stock_client.get_stock_latest_quote.call_args
        self.assertIsInstance(args[0], StockLatestQuoteRequest)
        self.assertEqual(args[0].symbol_or_symbols, 'AAPL')
        self.assertEqual(str(args[0].timeframe), str(TimeFrame.Minute))  # Compare string representations
        self.assertEqual(args[0].limit, 1)
        self.assertEqual(args[0].feed, DataFeed.IEX)

    @patch('portfolio_management_script.trading_client')
    def test_calculate_pnl(self, mock_trading_client):
        mock_account = MagicMock(equity='1100')
        mock_trading_client.get_account.return_value = mock_account
        pnl = calculate_pnl({'cash': 1000, 'positions': {}})
        self.assertEqual(100, pnl)

    @patch('portfolio_management_script.trading_client')
    @patch('portfolio_management_script.get_current_price')
    def test_execute_trade(self, mock_get_price, mock_trading_client):
        mock_get_price.return_value = 150.0
        mock_trading_client.submit_order.return_value = MagicMock()
        order = execute_trade('AAPL', 2, OrderSide.BUY)
        self.assertIsNotNone(order)

    @patch('portfolio_management_script.get_current_price')
    def test_update_portfolio(self, mock_get_price):
        mock_get_price.return_value = 150.0
        portfolio = {'cash': 1000, 'positions': {'AAPL': 10}}
        update_portfolio(portfolio, 'AAPL', 2, OrderSide.BUY)
        self.assertEqual(700, portfolio['cash'])
        self.assertEqual(12, portfolio['positions']['AAPL'])

    @patch('portfolio_management_script.analyze_market')
    @patch('portfolio_management_script.analyze_with_claude')
    @patch('portfolio_management_script.execute_trade')
    @patch('portfolio_management_script.update_portfolio')
    def test_analyze_and_trade(self, mock_update_portfolio, mock_execute_trade, mock_analyze_with_claude, mock_analyze_market):
        mock_analyze_market.return_value = {
            'status': 'success',
            'market_analysis': 'Market is bullish',
            'individual_analyses': {
                'AAPL': {'analysis': 'AAPL looks good'},
                'GOOGL': {'analysis': 'GOOGL is neutral'}
            }
        }
        mock_analyze_with_claude.return_value = json.dumps({
            'portfolio_summary': 'Portfolio looks balanced',
            'market_outlook': 'Bullish',
            'risk_assessment': 'Moderate risk',
            'cash_management': 'Keep some cash reserve',
            'trades': [
                {'symbol': 'AAPL', 'action': 'buy', 'quantity': 2, 'reasoning': 'Bullish on tech'}
            ]
        })
        mock_execute_trade.return_value = MagicMock()

        analyze_and_trade()

        mock_execute_trade.assert_called_once()
        mock_update_portfolio.assert_called_once()

    @patch('portfolio_management_script.load_portfolio')
    @patch('portfolio_management_script.load_transactions')
    @patch('portfolio_management_script.calculate_pnl')
    @patch('portfolio_management_script.get_current_price')
    def test_generate_portfolio_report(self, mock_get_price, mock_calculate_pnl, mock_load_transactions, mock_load_portfolio):
        mock_load_portfolio.return_value = self.test_portfolio
        mock_load_transactions.return_value = [self.test_transaction]
        mock_calculate_pnl.return_value = 100
        mock_get_price.return_value = 150.0

        report = generate_portfolio_report()
        
        self.assertIn('Portfolio Report', report)
        self.assertIn('Current Portfolio', report)
        self.assertIn('Performance', report)
        self.assertIn('Transaction History', report)

    @patch('portfolio_management_script.analyze_and_trade')
    @patch('portfolio_management_script.generate_portfolio_report')
    def test_main(self, mock_generate_report, mock_analyze_and_trade):
        mock_generate_report.return_value = "Test Report"
        main()
        mock_analyze_and_trade.assert_called_once()
        mock_generate_report.assert_called_once()

class TestPortfolioManagementIntegration(unittest.TestCase):

    @patch('portfolio_management_script.trading_client')
    @patch('portfolio_management_script.stock_client')
    @patch('portfolio_management_script.analyze_market')
    @patch('portfolio_management_script.analyze_with_claude')
    def test_full_workflow(self, mock_analyze_with_claude, mock_analyze_market, mock_stock_client, mock_trading_client):
        # Set up mock returns
        mock_trading_client.get_account.return_value = MagicMock(equity='1100')
        mock_trading_client.submit_order.return_value = MagicMock()
        
        mock_bars = {
            'AAPL': [MagicMock(close=150.0)]
        }
        mock_stock_client.get_stock_bars.return_value = mock_bars
        
        mock_analyze_market.return_value = {
            'status': 'success',
            'market_analysis': 'Market is bullish',
            'individual_analyses': {
                'AAPL': {'analysis': 'AAPL looks good'},
                'GOOGL': {'analysis': 'GOOGL is neutral'}
            }
        }
        
        mock_analyze_with_claude.return_value = json.dumps({
            'portfolio_summary': 'Portfolio looks balanced',
            'market_outlook': 'Bullish',
            'risk_assessment': 'Moderate risk',
            'cash_management': 'Keep some cash reserve',
            'trades': [
                {'symbol': 'AAPL', 'action': 'buy', 'quantity': 2, 'reasoning': 'Bullish on tech'}
            ]
        })

        # Run the main function
        main()

        # Assert that the workflow executed as expected
        mock_analyze_market.assert_called_once()
        mock_analyze_with_claude.assert_called_once()
        mock_trading_client.submit_order.assert_called_once()
        mock_stock_client.get_stock_bars.assert_called()
        
        args, kwargs = mock_stock_client.get_stock_bars.call_args
        self.assertIsInstance(args[0], StockBarsRequest)
        self.assertEqual(args[0].symbol_or_symbols, ['AAPL'])
        self.assertEqual(args[0].feed, DataFeed.IEX)

if __name__ == '__main__':
    unittest.main()