"""Tests for database models"""
import unittest
from datetime import datetime, timezone, timedelta
from freezegun import freeze_time
from app import create_app
from models import db, Stock, APICredential
from config import TestConfig

class TestModels(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        self.app = create_app()
        self.app.config.from_object(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
    
    def tearDown(self):
        """Clean up test environment after each test"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_stock_creation(self):
        """Test creating a new stock"""
        stock = Stock('AAPL', 'Apple Inc.')
        db.session.add(stock)
        db.session.commit()
        
        saved_stock = Stock.query.filter_by(symbol='AAPL').first()
        self.assertIsNotNone(saved_stock)
        self.assertEqual(saved_stock.symbol, 'AAPL')
        self.assertEqual(saved_stock.name, 'Apple Inc.')
    
    def test_stock_update_price(self):
        """Test updating stock price"""
        stock = Stock('AAPL', 'Apple Inc.')
        stock.update_price(current_price=150.0, previous_close=145.0)
        
        self.assertEqual(stock.current_price, 150.0)
        self.assertEqual(stock.previous_close, 145.0)
        self.assertEqual(stock.price_change, 5.0)
        self.assertAlmostEqual(stock.price_change_percent, (5.0 / 145.0) * 100)
    
    @freeze_time("2024-01-01 12:00:00")
    def test_stock_to_dict(self):
        """Test stock to dictionary conversion"""
        stock = Stock('AAPL', 'Apple Inc.')
        stock.update_price(current_price=150.0, previous_close=145.0)
        stock.has_news = True
        
        stock_dict = stock.to_dict()
        
        self.assertEqual(stock_dict['symbol'], 'AAPL')
        self.assertEqual(stock_dict['name'], 'Apple Inc.')
        self.assertEqual(stock_dict['current_price'], 150.0)
        self.assertEqual(stock_dict['previous_close'], 145.0)
        self.assertEqual(stock_dict['price_change'], 5.0)
        self.assertTrue(stock_dict['has_news'])
        self.assertEqual(stock_dict['friendly_time'], 'Just now')
    
    def test_api_credential_creation(self):
        """Test creating new API credentials"""
        cred = APICredential(api_key='test_key', secret_key='test_secret')
        db.session.add(cred)
        db.session.commit()
        
        saved_cred = APICredential.query.first()
        self.assertIsNotNone(saved_cred)
        self.assertEqual(saved_cred.api_key, 'test_key')
        self.assertEqual(saved_cred.secret_key, 'test_secret')
    
    def test_get_active_credentials(self):
        """Test getting most recent API credentials"""
        # Add old credentials
        old_cred = APICredential(api_key='old_key', secret_key='old_secret')
        db.session.add(old_cred)
        db.session.commit()
        
        # Add new credentials
        new_cred = APICredential(api_key='new_key', secret_key='new_secret')
        db.session.add(new_cred)
        db.session.commit()
        
        active_creds = APICredential.get_active_credentials()
        self.assertEqual(active_creds['api_key'], 'new_key')
        self.assertEqual(active_creds['secret_key'], 'new_secret')
    
    @freeze_time("2024-01-01 12:00:00")
    def test_stock_friendly_time(self):
        """Test friendly time display for different time intervals"""
        stock = Stock('AAPL', 'Apple Inc.')
        
        # Test just now
        stock.last_updated = datetime.now(timezone.utc)
        self.assertEqual(stock.to_dict()['friendly_time'], 'Just now')
        
        # Test 1 minute ago
        stock.last_updated = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.assertEqual(stock.to_dict()['friendly_time'], '1 minute ago')
        
        # Test multiple minutes ago
        stock.last_updated = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.assertEqual(stock.to_dict()['friendly_time'], '5 minutes ago')

if __name__ == '__main__':
    unittest.main() 