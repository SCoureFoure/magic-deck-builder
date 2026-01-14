# Magic Deck Builder

Commander (EDH) deck builder CLI tool with a lightweight web UI.

## Quick Start

```bash
# Copy environment variables
cp .env.example .env

# Install dependencies
pip install -e ".[dev]"

# Start database
docker compose up -d

# Run migrations
alembic upgrade head

# Ingest Scryfall data
python -m src.cli ingest bulk oracle_cards

# Search for a commander
python -m src.cli search commander "Atraxa"
```

## Web UI (FastAPI + Vite)

```bash
# Backend API
uvicorn src.web.app:app --reload

# Frontend (in another shell)
cd web
npm install
npm run dev
```

Open `http://localhost:5173` and search commanders using the API at `http://localhost:8000`.

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Format code
ruff format src tests

# Lint code
ruff check src tests
```

## Project Structure

- `src/` - Source code
  - `models/` - Data models (Card, Commander, Deck)
  - `database/` - Database connection and schema
  - `ingestion/` - Scryfall client and bulk loader
  - `engine/` - Deck building logic
  - `cli/` - Command-line interface
- `tests/` - Test suite
- `data/` - Cache directory (gitignored)
- `docs/` - Documentation

## Architecture

See [docs/discovery.md](docs/discovery.md) for full discovery brief.
