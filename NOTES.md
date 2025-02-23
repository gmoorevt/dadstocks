# Dad's Stocks - Quick Reference

## Common Docker Commands

```bash
# Start the application
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild containers
docker-compose up --build

# Stop the application
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Restart services
docker-compose restart

# View running containers
docker-compose ps

# Shell access
docker-compose exec web bash
```

## Development Tasks

### Database Management
```bash
# Access SQLite CLI
docker-compose exec web sqlite3 instance/stocks.db

# Common SQLite commands
.tables          # List all tables
.schema stocks   # Show table schema
.quit           # Exit SQLite

# Reset Database
docker-compose down -v    # Remove volumes
docker-compose up        # Recreate database
```

### Port Management
```bash
# Check what's using port 5001
lsof -i :5001

# Kill process using port 5001
kill $(lsof -t -i:5001)

# Alternative port in docker-compose.yml
ports:
  - "5002:5001"  # Host:Container
```

### Testing
```bash
# Run all tests
docker-compose exec web python -m pytest

# Run with coverage
docker-compose exec web python -m pytest --cov=. --cov-report=term-missing

# Run specific test file
docker-compose exec web python -m pytest tests/test_models.py
```

### Debugging
```bash
# View real-time logs
docker-compose logs -f

# View Python errors
docker-compose logs -f web

# Access container with shell
docker-compose exec web bash

# Check container status
docker ps
```

## Common Issues & Solutions

### Container Won't Start
1. Check if port is in use:
   ```bash
   lsof -i :5001
   ```

2. Check container logs:
   ```bash
   docker-compose logs
   ```

3. Verify volume permissions:
   ```bash
   ls -la instance/
   ```

### Database Issues
1. Reset database:
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```

2. Check database contents:
   ```bash
   docker-compose exec web sqlite3 instance/stocks.db
   ```

### Live Reload Not Working
1. Check file permissions
2. Ensure volume is mounted correctly
3. Verify FLASK_ENV=development is set

## Environment Variables

```bash
# Development
FLASK_ENV=development
FLASK_DEBUG=1
SIMULATION_MODE=true

# Production
FLASK_ENV=production
FLASK_DEBUG=0
SIMULATION_MODE=false
```

## URLs

- Main Dashboard: http://localhost:5001
- News Page: http://localhost:5001/news
- Admin Dashboard: http://localhost:5001/admin/login 