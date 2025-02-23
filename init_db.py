from app import create_app, db
from models import Stock
from config import Config

def init_db():
    app = create_app()
    with app.app_context():
        # Drop all tables
        db.drop_all()
        
        # Create all tables
        db.create_all()
        
        # Add default stocks if they don't exist
        for symbol in Config.DEFAULT_STOCKS:
            if not Stock.query.filter_by(symbol=symbol).first():
                stock = Stock(symbol=symbol)
                db.session.add(stock)
        
        db.session.commit()
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_db() 