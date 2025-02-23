"""Tests for Flask routes"""
import unittest
from unittest.mock import patch, MagicMock
import json
from app import create_app, get_stock_data, get_news_for_symbols
from models import db, Stock, APICredential
from config import TestConfig
from datetime import datetime

class TestRoutes(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        self.app = create_app()
        self.app.config.from_object(TestConfig)
        
        # Register routes
        from app import (index, get_stocks, admin_login, admin_dashboard,
                       admin_logout, update_stocks, news)
        
        self.app.add_url_rule('/', 'index', index, methods=['GET', 'POST'])
        self.app.add_url_rule('/api/stocks', 'get_stocks', get_stocks)
        self.app.add_url_rule('/admin/login', 'admin_login', admin_login, methods=['GET', 'POST'])
        self.app.add_url_rule('/admin/dashboard', 'admin_dashboard', admin_dashboard, methods=['GET', 'POST'])
        self.app.add_url_rule('/admin/logout', 'admin_logout', admin_logout, methods=['POST'])
        self.app.add_url_rule('/admin/update-stocks', 'update_stocks', update_stocks, methods=['POST'])
        self.app.add_url_rule('/news', 'news', news)
        
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Add test stock
        self.test_stock = Stock('AAPL', 'Apple Inc.')
        self.test_stock.update_price(150.0, 145.0)
        db.session.add(self.test_stock)
        db.session.commit()
    
    def tearDown(self):
        """Clean up test environment after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_index_route(self):
        """Test the main dashboard route"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Stock Dashboard', response.data)
        self.assertIn(b'AAPL', response.data)
    
    @patch('app.get_stock_data')
    def test_add_stock(self, mock_get_stock_data):
        """Test adding a new stock"""
        mock_get_stock_data.return_value = {
            'GOOGL': {
                'price': 2800.0,
                'previous_close': 2750.0,
                'name': 'Alphabet Inc.',
                'timestamp': '2024-01-01T12:00:00Z'
            }
        }
        
        response = self.client.post('/', data={
            'symbol': 'GOOGL',
            'csrf_token': 'test'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        stock = Stock.query.filter_by(symbol='GOOGL').first()
        self.assertIsNotNone(stock)
        self.assertEqual(stock.symbol, 'GOOGL')
    
    def test_add_duplicate_stock(self):
        """Test adding a stock that already exists"""
        response = self.client.post('/', data={
            'symbol': 'AAPL',
            'csrf_token': 'test'
        }, follow_redirects=True)
        
        self.assertIn(b'already being tracked', response.data)
    
    @patch('app.get_stock_data')
    @patch('app.get_news_for_symbols')
    def test_api_stocks_route(self, mock_get_news, mock_get_stock_data):
        """Test the API endpoint for stock data"""
        # Mock stock data response
        mock_get_stock_data.return_value = {
            'SPY': {
                'price': 400.0,
                'previous_close': 395.0,
                'name': 'S&P 500',
                'timestamp': datetime.now()
            }
        }
        
        # Mock news response
        mock_get_news.return_value = [{
            'headline': 'Test News',
            'symbols': ['AAPL']
        }]
        
        response = self.client.get('/api/stocks')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(isinstance(data, list))
        self.assertTrue(any(stock['symbol'] == 'AAPL' for stock in data))
        self.assertTrue(any(stock['symbol'] == 'SPY' for stock in data))
    
    def test_admin_login_route(self):
        """Test admin login functionality"""
        # Test GET request
        response = self.client.get('/admin/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Admin Login', response.data)
        
        # Test successful login
        response = self.client.post('/admin/login', data={
            'username': TestConfig.ADMIN_USERNAME,
            'password': TestConfig.ADMIN_PASSWORD,
            'csrf_token': 'test'
        })
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard
        
        # Test failed login
        response = self.client.post('/admin/login', data={
            'username': 'wrong',
            'password': 'wrong',
            'csrf_token': 'test'
        }, follow_redirects=True)
        self.assertIn(b'Invalid credentials', response.data)
    
    def test_admin_dashboard_unauthorized(self):
        """Test accessing admin dashboard without login"""
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_admin_dashboard_authorized(self):
        """Test accessing admin dashboard with login"""
        # Login first
        self.client.post('/admin/login', data={
            'username': TestConfig.ADMIN_USERNAME,
            'password': TestConfig.ADMIN_PASSWORD,
            'csrf_token': 'test'
        })
        
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Admin Dashboard', response.data)
    
    @patch('app.get_news_for_symbols')
    def test_news_route(self, mock_get_news):
        """Test the news page route"""
        mock_get_news.return_value = [{
            'headline': 'Test News',
            'summary': 'Test Summary',
            'author': 'Test Author',
            'url': 'http://test.com',
            'updated_at': '2024-01-01T12:00:00Z',
            'symbols': ['AAPL']
        }]
        
        response = self.client.get('/news')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Stock News', response.data)
        self.assertIn(b'Test News', response.data)
    
    @patch('app.StockHistoricalDataClient')
    @patch('app.TradingClient')
    def test_admin_update_api_credentials(self, mock_trading_client, mock_data_client):
        """Test updating API credentials through admin dashboard"""
        # Mock successful API validation
        mock_account = MagicMock()
        mock_trading_client.return_value.get_account.return_value = mock_account
        
        # Login first
        self.client.post('/admin/login', data={
            'username': TestConfig.ADMIN_USERNAME,
            'password': TestConfig.ADMIN_PASSWORD,
            'csrf_token': 'test'
        })
        
        # Update API credentials
        response = self.client.post('/admin/dashboard', data={
            'action': 'update_key',
            'api_key': 'new_test_key',
            'secret_key': 'new_test_secret',
            'csrf_token': 'test'
        }, follow_redirects=True)
        
        self.assertIn(b'API credentials updated successfully', response.data)
        
        # Verify credentials were saved
        creds = APICredential.get_active_credentials()
        self.assertEqual(creds['api_key'], 'new_test_key')
        self.assertEqual(creds['secret_key'], 'new_test_secret')
    
    def test_admin_remove_stock(self):
        """Test removing a stock through admin dashboard"""
        # Login first
        self.client.post('/admin/login', data={
            'username': TestConfig.ADMIN_USERNAME,
            'password': TestConfig.ADMIN_PASSWORD,
            'csrf_token': 'test'
        })
        
        # Remove stock
        response = self.client.post('/admin/dashboard', data={
            'action': 'remove_stock',
            'symbol': 'AAPL',
            'csrf_token': 'test'
        }, follow_redirects=True)
        
        self.assertIn(b'Stock AAPL removed successfully', response.data)
        
        # Verify stock was removed
        stock = Stock.query.filter_by(symbol='AAPL').first()
        self.assertIsNone(stock)

if __name__ == '__main__':
    unittest.main() 