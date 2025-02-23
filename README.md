# Dad's Stocks

![CI/CD](https://github.com/gmoorevt/investment-dashboard/workflows/CI/CD/badge.svg)
[![codecov](https://codecov.io/gh/gmoorevt/investment-dashboard/branch/main/graph/badge.svg)](https://codecov.io/gh/gmoorevt/investment-dashboard)

A Flask-based web application that tracks real-time stock prices and their changes from the previous close. Built with love for Dad to keep track of his investments.

![Dad's Stocks Logo](static/logo.svg)

## Features

- Real-time stock price tracking with simulation mode
- Historical price comparison
- News aggregation for tracked stocks
- Market index tracking (S&P 500, Dow Jones, NASDAQ)
- SQLite database for stock data persistence
- Clean and responsive web interface
- Admin dashboard for managing tracked stocks

## Technologies

- Python 3.9+
- Flask 3.0.0
- SQLAlchemy
- Alpaca Markets API
- TailwindCSS
- Chart.js

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your Alpaca API credentials
```

4. Initialize the database:
```bash
python init_db.py
```

5. Run the application:
```bash
python app.py
```

6. Access the dashboard at `http://localhost:5001`

## Running Tests

Run the test suite with coverage reporting:

```bash
python run_tests.py
```

## Project Structure

```
├── app.py              # Main application file
├── models.py           # Database models
├── init_db.py          # Database initialization script
├── config.py           # Configuration settings
├── services/          # Service modules
│   ├── alpaca_factory.py    # Alpaca API service factory
│   └── mock_alpaca.py       # Mock service for simulation
├── templates/          # HTML templates
│   ├── base.html      # Base template
│   ├── index.html     # Dashboard template
│   └── news.html      # News page template
├── static/            # Static files (CSS, JS, images)
├── tests/             # Test suite
└── requirements.txt   # Project dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for more information. 