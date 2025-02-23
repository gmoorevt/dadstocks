"""Mock Alpaca services for simulation mode"""
import random
from datetime import datetime, timedelta, timezone
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class MockAsset:
    symbol: str
    name: str
    class_: str = 'us_equity'
    exchange: str = 'NYSE'
    status: str = 'active'
    tradable: bool = True
    marginable: bool = True
    maintenance_margin_requirement: float = 30.0
    shortable: bool = True
    easy_to_borrow: bool = True
    fractionable: bool = True
    
    def __init__(self, symbol: str, name: str):
        self.symbol = symbol
        self.name = name

class MockAlpacaService:
    """Mock Alpaca service that simulates stock price movements"""
    
    def __init__(self):
        self._prices: Dict[str, float] = {}
        self._previous_closes: Dict[str, float] = {}
        self._assets = {
            'AAPL': MockAsset('AAPL', 'Apple Inc.'),
            'GOOGL': MockAsset('GOOGL', 'Alphabet Inc.'),
            'MSFT': MockAsset('MSFT', 'Microsoft Corporation'),
            'AMZN': MockAsset('AMZN', 'Amazon.com Inc.'),
            'META': MockAsset('META', 'Meta Platforms Inc.'),
            'SPY': MockAsset('SPY', 'SPDR S&P 500 ETF Trust'),
            'DIA': MockAsset('DIA', 'SPDR Dow Jones Industrial Average ETF'),
            'QQQ': MockAsset('QQQ', 'Invesco QQQ Trust')
        }
        
        # Initialize with some realistic base prices
        self._base_prices = {
            'AAPL': 175.0,
            'GOOGL': 140.0,
            'MSFT': 400.0,
            'AMZN': 175.0,
            'META': 485.0,
            'SPY': 510.0,
            'DIA': 385.0,
            'QQQ': 430.0
        }
        
        # Initialize current prices and previous closes
        for symbol, price in self._base_prices.items():
            self._prices[symbol] = price
            self._previous_closes[symbol] = price * (1 + random.uniform(-0.02, 0.02))
    
    def _simulate_price_movement(self, symbol: str) -> float:
        """Simulate a price movement for a stock"""
        current_price = self._prices[symbol]
        base_price = self._base_prices[symbol]
        
        # Calculate maximum allowed movement (more volatile for higher-priced stocks)
        max_movement = current_price * 0.02  # 2% maximum movement
        
        # Add mean reversion tendency
        reversion_force = (base_price - current_price) * 0.1
        
        # Generate random movement with mean reversion
        movement = random.uniform(-max_movement, max_movement) + reversion_force
        
        # Update price
        new_price = round(current_price + movement, 2)
        
        # Ensure price doesn't go too far from base price (±20%)
        min_price = base_price * 0.8
        max_price = base_price * 1.2
        new_price = max(min_price, min(max_price, new_price))
        
        return new_price

    def get_stock_bars(self, symbols: List[str]) -> pd.DataFrame:
        """Get simulated stock bars data"""
        data = []
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        
        for symbol in symbols:
            if symbol in self._assets:
                # Update the price
                new_price = self._simulate_price_movement(symbol)
                self._previous_closes[symbol] = self._prices[symbol]
                self._prices[symbol] = new_price
                
                # Add current and previous day's data
                data.extend([
                    {
                        'symbol': symbol,
                        'timestamp': yesterday,
                        'close': self._previous_closes[symbol]
                    },
                    {
                        'symbol': symbol,
                        'timestamp': now,
                        'close': new_price
                    }
                ])
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        return df.set_index(['symbol', 'timestamp'])
    
    def get_assets(self) -> List[MockAsset]:
        """Get list of available assets"""
        return list(self._assets.values())
    
    def get_news(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """Get simulated news articles"""
        if symbols is None:
            symbols = list(self._assets.keys())
        
        # Generate some random news
        headlines = [
            "Company Reports Strong Quarterly Results",
            "Analysts Upgrade Stock Rating",
            "New Product Launch Announced",
            "Strategic Partnership Formed",
            "Market Share Increases",
            "Innovation Award Received",
            "Expansion Plans Revealed",
            "Industry Recognition Achievement"
        ]
        
        news_articles = []
        for symbol in symbols:
            if symbol in self._assets and random.random() < 0.3:  # 30% chance of news
                news_articles.append({
                    'headline': f"{self._assets[symbol].name} {random.choice(headlines)}",
                    'summary': f"Latest updates about {self._assets[symbol].name} and its market performance.",
                    'author': "Market Analyst",
                    'url': f"http://example.com/news/{symbol.lower()}",
                    'updated_at': datetime.now().isoformat(),
                    'symbols': [symbol]
                })
        
        return news_articles 