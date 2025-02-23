import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file if it exists
env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path)
else:
    print("Warning: .env file not found. Using default configuration.")

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///stocks.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Stock update interval (in seconds) - 5 minutes
    STOCK_UPDATE_INTERVAL = 300
    
    # Default stocks to track
    DEFAULT_STOCKS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META']
    
    # Alpaca API settings
    ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
    ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
    
    # Admin credentials (in production, use proper user management)
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
    
    # Polygon.io settings
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    
    # Simulation mode
    SIMULATION_MODE = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'
    # Shorter update interval in simulation mode (30 seconds)
    SIMULATION_UPDATE_INTERVAL = 30

class TestConfig(Config):
    """Test configuration"""
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    # Use SQLite in-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Shorter update interval for testing
    STOCK_UPDATE_INTERVAL = 1
    
    # Limited set of stocks for testing
    DEFAULT_STOCKS = ['AAPL', 'GOOGL']
    
    # Test API credentials
    ALPACA_API_KEY = 'test_api_key'
    ALPACA_SECRET_KEY = 'test_secret_key' 