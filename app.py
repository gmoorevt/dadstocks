from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from models import db, Stock, APICredential
from config import Config
from datetime import datetime, timedelta, timezone
import threading
import time
from functools import wraps
from flask_wtf import CSRFProtect
from flask_wtf.form import FlaskForm
import secrets
from alpaca.data import StockHistoricalDataClient, StockBarsRequest, TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
import requests
from services.alpaca_factory import AlpacaFactory
import pandas as pd
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockBarsRequest
from alpaca.data.enums import Adjustment
import pytz
import os

# Create a base form for CSRF protection
class CSRFForm(FlaskForm):
    pass

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Ensure we have a strong secret key
    if app.config['SECRET_KEY'] == 'dev':
        app.config['SECRET_KEY'] = secrets.token_hex(32)
    
    db.init_app(app)
    csrf = CSRFProtect(app)
    
    # Initialize the Alpaca factory
    alpaca_factory = AlpacaFactory.get_instance()
    
    def initialize_alpaca():
        """Initialize Alpaca services based on configuration"""
        simulation_mode = app.config['SIMULATION_MODE']
        if isinstance(simulation_mode, str):
            simulation_mode = simulation_mode.lower() == 'true'
        
        api_key = app.config.get('ALPACA_API_KEY')
        secret_key = app.config.get('ALPACA_SECRET_KEY')
        
        alpaca_factory.initialize(
            simulation_mode=simulation_mode,
            api_key=api_key,
            secret_key=secret_key
        )
        
        if simulation_mode:
            app.logger.info("Running in simulation mode")
            # Add default stocks in simulation mode
            with app.app_context():
                default_stocks = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META']
                for symbol in default_stocks:
                    if not Stock.query.filter_by(symbol=symbol).first():
                        stock = Stock(symbol=symbol)
                        db.session.add(stock)
                try:
                    db.session.commit()
                    app.logger.info("Added default stocks for simulation mode")
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error adding default stocks: {str(e)}")
        else:
            app.logger.info("Running with real Alpaca API")
        
        return alpaca_factory
    
    with app.app_context():
        db.create_all()
        app.alpaca_factory = initialize_alpaca()
    
    return app

app = create_app()
alpaca_factory = app.alpaca_factory

def get_stock_data(symbols):
    """Get current stock data for the given symbols"""
    if alpaca_factory.is_simulation_mode:
        return alpaca_factory.get_stock_data(symbols)
        
    client = alpaca_factory.get_data_client()
    now = datetime.now(pytz.UTC)
    start = now - timedelta(days=2)
    
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=now,
        adjustment=Adjustment.ALL
    )
    
    try:
        bars = client.get_stock_bars(request)
        trading_client = alpaca_factory.get_trading_client()
        assets = {asset.symbol: asset for asset in trading_client.get_all_assets()}
        
        result = {}
        for symbol in symbols:
            if symbol in assets:
                symbol_bars = bars[bars.index.get_level_values('symbol') == symbol]
                if len(symbol_bars) >= 1:
                    current_price = float(symbol_bars.iloc[-1]['close'])
                    previous_close = float(symbol_bars.iloc[-2]['close']) if len(symbol_bars) > 1 else current_price
                    
                    result[symbol] = {
                        'price': current_price,
                        'previous_close': previous_close,
                        'name': assets[symbol].name,
                        'timestamp': symbol_bars.iloc[-1].name[1]
                    }
        
        return result
    except Exception as e:
        app.logger.error(f"Error fetching stock data: {str(e)}")
        return {}

def update_stock_prices(manual=False):
    """Background task to update stock prices using Alpaca API"""
    try:
        if manual:
            print(f"[{datetime.now()}] Starting manual stock price update...")
        else:
            print(f"[{datetime.now()}] Starting scheduled stock price update...")
            
        stocks = Stock.query.all()
        
        # Get all stock symbols
        symbols = [stock.symbol for stock in stocks]
        
        if symbols:  # Only make API call if we have stocks to update
            # Fetch data for all stocks
            stock_data = get_stock_data(symbols)
            
            # Update each stock
            for stock in stocks:
                try:
                    if stock.symbol in stock_data:
                        data = stock_data[stock.symbol]
                        
                        # Update stock name if not set
                        if not stock.name:
                            stock.name = data['name']
                        
                        stock.update_price(
                            current_price=data['price'],
                            previous_close=data['previous_close']
                        )
                        stock.last_updated = data['timestamp']  # Explicitly set the last_updated timestamp
                        print(f"[{datetime.now()}] Updated {stock.symbol}: ${data['price']:.2f} (prev: ${data['previous_close']:.2f})")
                    else:
                        print(f"[{datetime.now()}] No data available for {stock.symbol}")
                        
                except Exception as e:
                    print(f"[{datetime.now()}] Error updating {stock.symbol}: {str(e)}")
            
            try:
                db.session.commit()
                if manual:
                    flash('Stock prices updated successfully', 'success')
            except Exception as e:
                print(f"[{datetime.now()}] Error committing updates: {str(e)}")
                db.session.rollback()
                if manual:
                    flash(f'Error updating stock prices: {str(e)}', 'error')
        
        print(f"[{datetime.now()}] Stock price update completed.")
        return True
    except Exception as e:
        error_msg = f"Error in update process: {str(e)}"
        print(f"[{datetime.now()}] {error_msg}")
        if manual:
            flash(error_msg, 'error')
        return False

def background_update_task():
    """Background task that runs continuously"""
    retry_delay = 60  # Start with 1 minute retry delay
    max_retry_delay = 900  # Maximum 15 minutes between retries
    
    while True:
        try:
            with app.app_context():
                success = update_stock_prices()
                if success:
                    retry_delay = 60  # Reset delay after successful update
                else:
                    retry_delay = min(retry_delay * 2, max_retry_delay)
                
                print(f"[{datetime.now()}] Next update in {Config.STOCK_UPDATE_INTERVAL} seconds.")
                time.sleep(Config.STOCK_UPDATE_INTERVAL)
        except Exception as e:
            print(f"[{datetime.now()}] Error in update loop: {str(e)}")
            print(f"[{datetime.now()}] Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def index():
    form = CSRFForm()
    if request.method == 'POST' and form.validate():
        symbol = request.form.get('symbol', '').strip().upper()
        if symbol:
            try:
                # Check if stock already exists
                if Stock.query.filter_by(symbol=symbol).first():
                    flash(f'Stock {symbol} is already being tracked', 'error')
                else:
                    # Validate the symbol with Alpaca
                    stock_data = get_stock_data([symbol])
                    if not stock_data or symbol not in stock_data:
                        raise ValueError(f"Could not fetch data for {symbol}")
                    
                    # Add the stock
                    stock = Stock(symbol=symbol)
                    db.session.add(stock)
                    db.session.commit()
                    flash(f'Stock {symbol} added successfully', 'success')
            except Exception as e:
                flash(f'Error adding stock: {str(e)}', 'error')
        else:
            flash('Stock symbol is required', 'error')
        return redirect(url_for('index'))
    
    # Get market indexes data
    index_symbols = ['SPY', 'DIA', 'QQQ', 'IWM']  # ETFs tracking S&P 500, Dow Jones, NASDAQ, and Russell 2000
    index_data = get_stock_data(index_symbols)
    
    # Create a dictionary for easy template access
    indexes = {symbol: index_data.get(symbol, {}) for symbol in index_symbols}
    
    # Get all tracked stocks
    stocks = Stock.query.all()
    
    # Get news for all symbols
    all_symbols = [stock.symbol for stock in stocks] + index_symbols
    news_articles = get_news_for_symbols(all_symbols)
    
    # Create a set of symbols that have news
    symbols_with_news = set()
    for article in news_articles:
        symbols_with_news.update(article.get('symbols', []))
    
    # Add has_news flag to each stock
    for stock in stocks:
        stock.has_news = stock.symbol in symbols_with_news
    
    return render_template('index.html', stocks=stocks, form=form, indexes=indexes)

@app.route('/api/stocks')
def get_stocks():
    # Get both user stocks and indexes
    stocks = Stock.query.all()
    stock_data = [stock.to_dict() for stock in stocks]
    
    # Add index data
    index_symbols = ['SPY', 'DIA', 'QQQ', 'IWM']
    index_data = get_stock_data(index_symbols)
    
    # Get news for all symbols
    all_symbols = [stock.symbol for stock in stocks] + index_symbols
    news_articles = get_news_for_symbols(all_symbols)
    
    # Create a set of symbols that have news
    symbols_with_news = set()
    for article in news_articles:
        symbols_with_news.update(article.get('symbols', []))
    
    # Get current time for timestamp calculations
    now = datetime.now(timezone.utc)
    
    # Combine the data
    for symbol in index_symbols:
        if symbol in index_data:
            data = index_data[symbol]
            timestamp = data['timestamp']
            
            # Convert timestamp to datetime with timezone if needed
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif isinstance(timestamp, datetime):
                if not timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            time_diff = now - timestamp
            minutes = int(time_diff.total_seconds() / 60)
            
            friendly_time = "Just now" if minutes < 1 else f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            
            stock_data.append({
                'symbol': symbol,
                'name': {
                    'SPY': 'S&P 500',
                    'DIA': 'Dow Jones',
                    'QQQ': 'NASDAQ',
                    'IWM': 'Russell 2000'
                }.get(symbol, symbol),
                'current_price': data['price'],
                'previous_close': data['previous_close'],
                'price_change': data['price'] - data['previous_close'],
                'price_change_percent': ((data['price'] - data['previous_close']) / data['previous_close']) * 100,
                'last_updated': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'friendly_time': friendly_time,
                'has_news': symbol in symbols_with_news
            })
    
    return jsonify(stock_data)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = CSRFForm()
    if request.method == 'POST' and form.validate():
        username = request.form.get('username')
        password = request.form.get('password')
        
        if (username == app.config['ADMIN_USERNAME'] and 
            password == app.config['ADMIN_PASSWORD']):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
    
    return render_template('admin_login.html', form=form)

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    form = CSRFForm()
    if request.method == 'POST' and form.validate():
        action = request.form.get('action', '')
        
        if action == 'update_key':
            api_key = request.form.get('api_key')
            secret_key = request.form.get('secret_key')
            
            if api_key and secret_key:
                try:
                    print(f"[{datetime.now()}] Testing new API credentials...")
                    print(f"[{datetime.now()}] API Key (masked): {api_key[:4]}...{api_key[-4:]}")
                    
                    # Test the API keys with a simple request
                    data_client = StockHistoricalDataClient(
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    print(f"[{datetime.now()}] Data client initialized, testing with AAPL data...")
                    
                    # Test trading client as well
                    trading_client = TradingClient(
                        api_key=api_key,
                        secret_key=secret_key,
                        paper=True
                    )
                    print(f"[{datetime.now()}] Trading client initialized, testing connection...")
                    
                    # Test by getting account information
                    account = trading_client.get_account()
                    print(f"[{datetime.now()}] Successfully connected to Alpaca API")
                    
                    # Save the API keys
                    print(f"[{datetime.now()}] Saving credentials to database...")
                    credential = APICredential(api_key=api_key, secret_key=secret_key)
                    db.session.add(credential)
                    db.session.commit()
                    print(f"[{datetime.now()}] Credentials saved successfully")
                    
                    flash('API credentials updated successfully', 'success')
                except Exception as e:
                    error_msg = f"Error validating API credentials: {str(e)}"
                    print(f"[{datetime.now()}] {error_msg}")
                    import traceback
                    print(f"[{datetime.now()}] Traceback: {traceback.format_exc()}")
                    flash(error_msg, 'error')
            else:
                flash('Both API key and secret key are required', 'error')
        
        elif action == 'add_stock':
            symbol = request.form.get('symbol', '').strip().upper()
            if symbol:
                try:
                    print(f"[{datetime.now()}] Attempting to add new stock: {symbol}")
                    # Check if stock already exists
                    if Stock.query.filter_by(symbol=symbol).first():
                        print(f"[{datetime.now()}] Stock {symbol} already exists in database")
                        flash(f'Stock {symbol} is already being tracked', 'error')
                    else:
                        # Validate the symbol with Alpaca
                        print(f"[{datetime.now()}] Validating {symbol} with Alpaca API...")
                        stock_data = get_stock_data([symbol])
                        if not stock_data or symbol not in stock_data:
                            raise ValueError(f"Could not fetch data for {symbol}")
                        
                        # Add the stock
                        print(f"[{datetime.now()}] Adding {symbol} to database...")
                        stock = Stock(symbol=symbol)
                        db.session.add(stock)
                        db.session.commit()
                        print(f"[{datetime.now()}] Successfully added {symbol}")
                        flash(f'Stock {symbol} added successfully', 'success')
                except Exception as e:
                    error_msg = f"Error adding stock: {str(e)}"
                    print(f"[{datetime.now()}] {error_msg}")
                    import traceback
                    print(f"[{datetime.now()}] Traceback: {traceback.format_exc()}")
                    flash(error_msg, 'error')
            else:
                flash('Stock symbol is required', 'error')
        
        elif action == 'remove_stock':
            symbol = request.form.get('symbol', '').strip().upper()
            if symbol:
                try:
                    print(f"[{datetime.now()}] Attempting to remove stock: {symbol}")
                    stock = Stock.query.filter_by(symbol=symbol).first()
                    if stock:
                        db.session.delete(stock)
                        db.session.commit()
                        print(f"[{datetime.now()}] Successfully removed {symbol}")
                        flash(f'Stock {symbol} removed successfully', 'success')
                    else:
                        print(f"[{datetime.now()}] Stock {symbol} not found in database")
                        flash(f'Stock {symbol} not found', 'error')
                except Exception as e:
                    error_msg = f"Error removing stock: {str(e)}"
                    print(f"[{datetime.now()}] {error_msg}")
                    import traceback
                    print(f"[{datetime.now()}] Traceback: {traceback.format_exc()}")
                    flash(error_msg, 'error')
            else:
                flash('Stock symbol is required', 'error')
    
    current_creds = APICredential.get_active_credentials()
    last_updated = None
    if current_creds:
        credential = APICredential.query.order_by(APICredential.last_updated.desc()).first()
        last_updated = credential.last_updated.strftime('%Y-%m-%d %H:%M:%S')
    
    stocks = Stock.query.all()
    
    # In development mode, pre-populate with environment variables
    env_api_key = None
    env_secret_key = None
    if app.debug:
        env_api_key = app.config['ALPACA_API_KEY']
        env_secret_key = app.config['ALPACA_SECRET_KEY']
    
    return render_template('admin_dashboard.html', 
                         current_key=current_creds['api_key'] if current_creds else None,
                         current_secret=current_creds['secret_key'] if current_creds else None,
                         last_updated=last_updated,
                         stocks=stocks,
                         form=form,
                         env_api_key=env_api_key,
                         env_secret_key=env_secret_key)

@app.route('/admin/logout', methods=['POST'])
@login_required
def admin_logout():
    form = CSRFForm()
    if form.validate():
        session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/update-stocks', methods=['POST'])
@login_required
def update_stocks():
    """Manual trigger for updating stock prices"""
    form = CSRFForm()
    if form.validate():
        with app.app_context():
            update_stock_prices(manual=True)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_simulation', methods=['POST'])
@login_required
def toggle_simulation():
    """Toggle simulation mode"""
    if not request.form.get('csrf_token') or not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid CSRF token', 'error')
        return redirect(url_for('admin_dashboard'))
    
    current_mode = app.config['SIMULATION_MODE'].lower() == 'true'
    new_mode = not current_mode
    
    # Update the environment variable
    os.environ['SIMULATION_MODE'] = str(new_mode).lower()
    app.config['SIMULATION_MODE'] = str(new_mode).lower()
    
    # Reinitialize Alpaca services with new mode
    app.alpaca_factory = initialize_alpaca()
    
    flash(f"Simulation mode {'enabled' if new_mode else 'disabled'}", 'success')
    return redirect(url_for('admin_dashboard'))

def get_news_for_symbols(symbols):
    """Get news articles for the given symbols"""
    return alpaca_factory.get_news(symbols)

@app.route('/news')
def news():
    """Display news for tracked stocks"""
    # Get all tracked stock symbols
    stocks = Stock.query.all()
    symbols = [stock.symbol for stock in stocks]
    
    # Add market indexes
    symbols.extend(['SPY', 'DIA', 'QQQ'])
    
    # Get news articles
    articles = get_news_for_symbols(symbols)
    
    # Group articles by stock
    articles_by_stock = {}
    for article in articles:
        for symbol in article.get('symbols', []):
            if symbol in symbols:  # Only include articles for tracked stocks
                if symbol not in articles_by_stock:
                    articles_by_stock[symbol] = []
                articles_by_stock[symbol].append(article)
    
    return render_template('news.html', 
                         articles_by_stock=articles_by_stock,
                         stocks=stocks)

# Global flag to track if initialization has occurred
_is_initialized = False

@app.before_request
def initialize():
    global _is_initialized
    if not _is_initialized:
        # Start the background task for updating stock prices
        update_thread = threading.Thread(target=background_update_task)
        update_thread.daemon = True
        update_thread.start()
        _is_initialized = True

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0') 