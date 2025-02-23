from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from models import db, Stock, APICredential, User, UserStock
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
        
        # In simulation mode, we don't need real API credentials
        if simulation_mode:
            app.logger.info("Running in simulation mode")
            alpaca_factory.initialize(simulation_mode=True)
        else:
            app.logger.info("Running with real Alpaca API")
            # We'll get credentials per user when needed
            alpaca_factory.initialize(simulation_mode=False)
        
        return alpaca_factory
    
    with app.app_context():
        db.create_all()
        app.alpaca_factory = initialize_alpaca()
    
    return app

app = create_app()
alpaca_factory = app.alpaca_factory

def user_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('admin_login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('index'))
        
        flash('Invalid email or password', 'error')
    
    return render_template('splash.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        user = User(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@user_login_required
def index():
    form = CSRFForm()
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST' and form.validate():
        symbol = request.form.get('symbol', '').strip().upper()
        if symbol:
            try:
                # Check if stock already exists for this user
                existing_stock = Stock.query.join(UserStock).filter(
                    Stock.symbol == symbol,
                    UserStock.user_id == user.id
                ).first()
                
                if existing_stock:
                    flash(f'Stock {symbol} is already being tracked', 'error')
                else:
                    # Get or create the stock
                    stock = Stock.query.filter_by(symbol=symbol).first()
                    if not stock:
                        # Validate the symbol with Alpaca
                        stock_data = get_stock_data([symbol])
                        if not stock_data or symbol not in stock_data:
                            raise ValueError(f"Could not fetch data for {symbol}")
                        
                        stock = Stock(symbol=symbol)
                        db.session.add(stock)
                    
                    # Create user-stock association
                    user_stock = UserStock(user_id=user.id, stock_id=stock.id)
                    db.session.add(user_stock)
                    db.session.commit()
                    flash(f'Stock {symbol} added successfully', 'success')
            except Exception as e:
                flash(f'Error adding stock: {str(e)}', 'error')
        else:
            flash('Stock symbol is required', 'error')
        return redirect(url_for('index'))
    
    # Get market indexes data
    index_symbols = ['SPY', 'DIA', 'QQQ', 'IWM']
    index_data = get_stock_data(index_symbols)
    indexes = {symbol: index_data.get(symbol, {}) for symbol in index_symbols}
    
    # Get user's tracked stocks
    user_stocks = UserStock.query.filter_by(user_id=user.id).all()
    
    # Get news for all symbols
    all_symbols = [us.stock.symbol for us in user_stocks] + index_symbols
    news_articles = get_news_for_symbols(all_symbols)
    
    # Create a set of symbols that have news
    symbols_with_news = set()
    for article in news_articles:
        symbols_with_news.update(article.get('symbols', []))
    
    # Add has_news flag to each stock
    for user_stock in user_stocks:
        user_stock.has_news = user_stock.stock.symbol in symbols_with_news
    
    return render_template('index.html', 
                         stocks=user_stocks,
                         form=form,
                         indexes=indexes,
                         user=user)

@app.route('/api/stocks')
@user_login_required
def get_stocks():
    user = User.query.get(session['user_id'])
    
    # Get user's stocks
    user_stocks = UserStock.query.filter_by(user_id=user.id).all()
    stock_data = [us.to_dict() for us in user_stocks]
    
    # Add index data
    index_symbols = ['SPY', 'DIA', 'QQQ', 'IWM']
    index_data = get_stock_data(index_symbols)
    
    # Get news for all symbols
    all_symbols = [us.stock.symbol for us in user_stocks] + index_symbols
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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email, is_admin=True).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid credentials')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@admin_login_required
def admin_dashboard():
    form = CSRFForm()
    admin = User.query.get(session['user_id'])
    
    if request.method == 'POST' and form.validate():
        action = request.form.get('action', '')
        
        if action == 'create_admin':
            email = request.form.get('email')
            password = request.form.get('password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            
            if email and password:
                try:
                    if User.query.filter_by(email=email).first():
                        flash('Email already registered', 'error')
                    else:
                        new_admin = User(
                            email=email,
                            password=password,
                            first_name=first_name,
                            last_name=last_name,
                            is_admin=True
                        )
                        db.session.add(new_admin)
                        db.session.commit()
                        flash('Admin user created successfully', 'success')
                except Exception as e:
                    flash(f'Error creating admin user: {str(e)}', 'error')
            else:
                flash('Email and password are required', 'error')
        
        elif action == 'delete_user':
            user_id = request.form.get('user_id')
            if user_id:
                try:
                    user = User.query.get(user_id)
                    if user:
                        db.session.delete(user)
                        db.session.commit()
                        flash('User deleted successfully', 'success')
                    else:
                        flash('User not found', 'error')
                except Exception as e:
                    flash(f'Error deleting user: {str(e)}', 'error')
    
    # Get all users for display
    users = User.query.all()
    
    return render_template('admin_dashboard.html',
                         users=users,
                         form=form,
                         admin=admin)

@app.route('/user/dashboard', methods=['GET', 'POST'])
@user_login_required
def user_dashboard():
    form = CSRFForm()
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST' and form.validate():
        action = request.form.get('action', '')
        
        if action == 'update_credentials':
            api_key = request.form.get('api_key')
            secret_key = request.form.get('secret_key')
            
            if api_key and secret_key:
                try:
                    # Test the API keys
                    data_client = StockHistoricalDataClient(
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    
                    trading_client = TradingClient(
                        api_key=api_key,
                        secret_key=secret_key,
                        paper=True
                    )
                    
                    # Test by getting account information
                    account = trading_client.get_account()
                    
                    # Save the API keys
                    credential = APICredential(
                        user_id=user.id,
                        api_key=api_key,
                        secret_key=secret_key
                    )
                    db.session.add(credential)
                    db.session.commit()
                    
                    flash('API credentials updated successfully', 'success')
                except Exception as e:
                    flash(f'Error validating API credentials: {str(e)}', 'error')
            else:
                flash('Both API key and secret key are required', 'error')
        
        elif action == 'remove_stock':
            symbol = request.form.get('symbol', '').strip().upper()
            if symbol:
                try:
                    user_stock = UserStock.query.join(Stock).filter(
                        Stock.symbol == symbol,
                        UserStock.user_id == user.id
                    ).first()
                    
                    if user_stock:
                        db.session.delete(user_stock)
                        db.session.commit()
                        flash(f'Stock {symbol} removed successfully', 'success')
                    else:
                        flash(f'Stock {symbol} not found', 'error')
                except Exception as e:
                    flash(f'Error removing stock: {str(e)}', 'error')
            else:
                flash('Stock symbol is required', 'error')
    
    current_creds = APICredential.get_active_credentials(user.id)
    last_updated = None
    if current_creds:
        credential = APICredential.query.filter_by(user_id=user.id).order_by(APICredential.last_updated.desc()).first()
        last_updated = credential.last_updated.strftime('%Y-%m-%d %H:%M:%S')
    
    user_stocks = UserStock.query.filter_by(user_id=user.id).all()
    
    return render_template('user_dashboard.html',
                         current_key=current_creds['api_key'] if current_creds else None,
                         current_secret=current_creds['secret_key'] if current_creds else None,
                         last_updated=last_updated,
                         stocks=user_stocks,
                         form=form,
                         user=user)

def get_stock_data(symbols):
    """Get current stock data for the given symbols"""
    if alpaca_factory.is_simulation_mode:
        return alpaca_factory.get_stock_data(symbols)
    
    # Get the current user's credentials
    user_id = session.get('user_id')
    if not user_id:
        return {}
    
    credentials = APICredential.get_active_credentials(user_id)
    if not credentials:
        return {}
    
    client = StockHistoricalDataClient(
        api_key=credentials['api_key'],
        secret_key=credentials['secret_key']
    )
    
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
        trading_client = TradingClient(
            api_key=credentials['api_key'],
            secret_key=credentials['secret_key'],
            paper=True
        )
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