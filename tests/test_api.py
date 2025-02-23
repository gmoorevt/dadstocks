"""Tests for API integration"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
from app import create_app, get_stock_data, get_news_for_symbols
from models import db
from config import TestConfig

class TestAPI(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        self.app = create_app()
        self.app.config.from_object(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Sample stock data
        self.sample_bars = pd.DataFrame({
            'symbol': ['AAPL', 'AAPL'],
            'close': [145.0, 150.0],  # Previous close, current price
            'timestamp': [
                datetime.now().date() - timedelta(days=1),
                datetime.now().date()
            ]
        }).set_index(['symbol', 'timestamp'])
        
        # Sample news data
        self.sample_news = {
            'news': [
                {
                    'headline': 'Test News',
                    'summary': 'Test Summary',
                    'author': 'Test Author',
                    'url': 'http://test.com',
                    'updated_at': '2024-01-01T12:00:00Z',
                    'symbols': ['AAPL']
                }
            ]
        }
    
    def tearDown(self):
        """Clean up test environment after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    @patch('app.StockHistoricalDataClient')
    @patch('app.TradingClient')
    def test_get_stock_data(self, mock_trading_client, mock_data_client):
        """Test getting stock data from Alpaca API"""
        # Mock the data client response
        mock_bars = MagicMock()
        mock_bars.df = self.sample_bars
        mock_data_client.return_value.get_stock_bars.return_value = mock_bars
        
        # Mock the trading client response
        mock_asset = MagicMock()
        mock_asset.symbol = 'AAPL'
        mock_asset.name = 'Apple Inc.'
        mock_trading_client.return_value.get_all_assets.return_value = [mock_asset]
        
        # Get stock data
        result = get_stock_data(['AAPL'])
        
        # Verify the result
        self.assertIn('AAPL', result)
        self.assertEqual(result['AAPL']['price'], 150.0)
        self.assertEqual(result['AAPL']['previous_close'], 145.0)
        self.assertEqual(result['AAPL']['name'], 'Apple Inc.')
    
    @patch('app.requests.get')
    def test_get_news_for_symbols(self, mock_get):
        """Test getting news articles from Alpaca API"""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_news
        mock_get.return_value = mock_response
        
        # Get news articles
        articles = get_news_for_symbols(['AAPL'])
        
        # Verify the result
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['headline'], 'Test News')
        self.assertEqual(articles[0]['symbols'], ['AAPL'])
    
    @patch('app.requests.get')
    def test_get_news_api_error(self, mock_get):
        """Test handling of news API errors"""
        # Mock an API error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        # Get news articles
        articles = get_news_for_symbols(['AAPL'])
        
        # Verify empty result on error
        self.assertEqual(articles, [])
    
    @patch('app.StockHistoricalDataClient')
    @patch('app.TradingClient')
    def test_get_stock_data_error(self, mock_trading_client, mock_data_client):
        """Test handling of stock data API errors"""
        # Mock an API error
        mock_data_client.return_value.get_stock_bars.side_effect = Exception('API Error')
        mock_trading_client.return_value.get_all_assets.return_value = []
        
        # Get stock data
        result = get_stock_data(['AAPL'])
        
        # Verify empty result on error
        self.assertEqual(result, {})
    
    @patch('app.StockHistoricalDataClient')
    @patch('app.TradingClient')
    def test_get_stock_data_empty_response(self, mock_trading_client, mock_data_client):
        """Test handling of empty API response"""
        # Mock empty data response
        mock_bars = MagicMock()
        mock_bars.df = pd.DataFrame()
        mock_data_client.return_value.get_stock_bars.return_value = mock_bars
        mock_trading_client.return_value.get_all_assets.return_value = []
        
        # Get stock data
        result = get_stock_data(['AAPL'])
        
        # Verify empty result
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main() 