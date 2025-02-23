"""Factory for creating Alpaca services"""
from typing import Optional, Dict, Any
from alpaca.data import StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from .mock_alpaca import MockAlpacaService

class AlpacaFactory:
    """Factory for creating Alpaca services"""
    
    _instance: Optional['AlpacaFactory'] = None
    _mock_service: Optional[MockAlpacaService] = None
    _data_client: Optional[StockHistoricalDataClient] = None
    _trading_client: Optional[TradingClient] = None
    
    def __init__(self):
        raise RuntimeError('Use get_instance() instead')
    
    @classmethod
    def get_instance(cls) -> 'AlpacaFactory':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = object.__new__(cls)
            cls._instance._mock_service = None
            cls._instance._data_client = None
            cls._instance._trading_client = None
        return cls._instance
    
    def initialize(self, simulation_mode: bool, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        """Initialize the factory with either real or mock services"""
        if simulation_mode:
            self._mock_service = MockAlpacaService()
            self._data_client = None
            self._trading_client = None
        else:
            if not api_key or not secret_key:
                raise ValueError("API key and secret key are required for real mode")
            self._mock_service = None
            self._data_client = StockHistoricalDataClient(api_key, secret_key)
            self._trading_client = TradingClient(api_key, secret_key, paper=True)
    
    @property
    def is_simulation_mode(self) -> bool:
        """Check if running in simulation mode"""
        return self._mock_service is not None
    
    def get_data_client(self) -> Any:
        """Get the data client (either real or mock)"""
        return self._mock_service if self.is_simulation_mode else self._data_client
    
    def get_trading_client(self) -> Any:
        """Get the trading client (either real or mock)"""
        return self._mock_service if self.is_simulation_mode else self._trading_client
    
    def get_stock_data(self, symbols: list) -> Dict:
        """Get stock data using either real or mock service"""
        if self.is_simulation_mode:
            bars = self._mock_service.get_stock_bars(symbols)
            assets = {asset.symbol: asset for asset in self._mock_service.get_assets()}
        else:
            from app import get_stock_data  # Import here to avoid circular import
            return get_stock_data(symbols)
        
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
    
    def get_news(self, symbols: list) -> list:
        """Get news using either real or mock service"""
        if self.is_simulation_mode:
            return self._mock_service.get_news(symbols)
        else:
            from app import get_news_for_symbols  # Import here to avoid circular import
            return get_news_for_symbols(symbols) 