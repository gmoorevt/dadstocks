from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from datetime import timezone
import pytz

db = SQLAlchemy()

class Stock(db.Model):
    __tablename__ = 'stocks'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100))
    current_price = db.Column(db.Float)
    previous_close = db.Column(db.Float)
    price_change = db.Column(db.Float)
    price_change_percent = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, symbol, name=None):
        self.symbol = symbol
        self.name = name
        self.last_updated = datetime.utcnow()
    
    def update_price(self, current_price, previous_close):
        self.current_price = current_price
        self.previous_close = previous_close
        self.price_change = current_price - previous_close
        self.price_change_percent = (self.price_change / previous_close) * 100
        self.last_updated = datetime.utcnow()
    
    def to_dict(self):
        # Convert UTC to local time
        local_tz = pytz.timezone('America/New_York')  # Using NY time for market hours
        now = datetime.now(timezone.utc)
        
        if self.last_updated:
            # Convert last_updated to aware datetime
            last_updated_utc = self.last_updated.replace(tzinfo=timezone.utc)
            last_updated_local = last_updated_utc.astimezone(local_tz)
            time_diff = now - last_updated_utc
            minutes = int(time_diff.total_seconds() / 60)
            
            if minutes < 1:
                friendly_time = "Just now"
            else:
                friendly_time = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            friendly_time = "Never"
            last_updated_local = None
            
        return {
            'symbol': self.symbol,
            'name': self.name,
            'current_price': self.current_price,
            'previous_close': self.previous_close,
            'price_change': self.price_change,
            'price_change_percent': self.price_change_percent,
            'last_updated': last_updated_local.strftime('%Y-%m-%d %I:%M %p %Z') if last_updated_local else None,
            'friendly_time': friendly_time,
            'has_news': getattr(self, 'has_news', False)
        }

class APICredential(db.Model):
    __tablename__ = 'api_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    api_key = db.Column(db.String(100), nullable=False)
    secret_key = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_active_credentials(cls):
        """Get the most recently updated API credentials"""
        credential = cls.query.order_by(cls.last_updated.desc()).first()
        if credential:
            return {
                'api_key': credential.api_key,
                'secret_key': credential.secret_key
            }
        return None 