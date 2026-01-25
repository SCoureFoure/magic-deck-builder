# Magic Deck Builder

Commander (EDH) deck builder with CLI, REST API, and web UI for searching and building Magic: The Gathering Commander decks using Scryfall data.

## Features

- **Commander Search**: Search for legal commanders with eligibility detection (legendary creatures, partner, backgrounds, etc.)
- **Scryfall Integration**: Bulk data ingestion with streaming JSON parsing for memory efficiency
- **CLI Interface**: Beautiful terminal UI with Rich for commander search and data management
- **REST API**: FastAPI backend with commander search endpoints
- **SQLite/PostgreSQL**: Flexible database support for local dev and production
- **Comprehensive Tests**: 38+ passing tests with pytest

## Quick Start

```bash
# 1. Set up Python environment (requires Python 3.9+)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Copy environment variables
cp .env.example .env

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Ingest Scryfall data (takes a few minutes, downloads ~200MB)
python -m src.cli ingest bulk oracle_cards

# 5. Search for commanders
python -m src.cli search commander "Atraxa"
```

## CLI Commands

### Ingestion
```bash
# Ingest Scryfall bulk data (auto-downloads and caches)
python -m src.cli ingest bulk oracle_cards

# Ingest a smaller commander-legal subset (useful for small DB limits)
python -m src.cli ingest small --limit 20000

# Ingest from a local file
python -m src.cli ingest file ./data/oracle_cards.json

# Force re-download
python -m src.cli ingest bulk oracle_cards --force
```

### Commander Search
```bash
# Search for commanders
python -m src.cli search commander "Urza"

# Limit results
python -m src.cli search commander "Dragon" --limit 5

# Populate commanders table first (optional, for faster searches)
python -m src.cli search commander "Sisay" --populate
```

## Web API

### Start the Backend
```bash
# Activate virtual environment
source .venv/bin/activate

# Start FastAPI server with hot-reload
uvicorn src.web.app:app --reload --port 8000
```

### API Endpoints

**Health Check:**
```bash
curl http://localhost:8000/api/health
```

**Commander Search:**
```bash
curl "http://localhost:8000/api/commanders?query=Atraxa&limit=10"
```

**Parameters:**
- `query` (required): Commander name to search for
- `limit` (optional): Max results (1-50, default 10)
- `populate` (optional): Populate commanders table first (default false)

**Example Response:**
```json
{
    "query": "Atraxa",
    "count": 2,
    "results": [
        {
            "name": "Atraxa, Praetors' Voice",
            "type_line": "Legendary Creature — Phyrexian Angel Horror",
            "color_identity": ["B", "G", "U", "W"],
            "mana_cost": "{G}{W}{U}{B}",
            "cmc": 4.0,
            "eligibility": "legendary creature",
            "commander_legal": "legal"
        }
    ]
}
```

### Frontend (Coming Soon)
```bash
# Frontend development server
cd web
npm install
npm run dev
```

Open `http://localhost:5173` - the frontend will connect to the API at `http://localhost:8000`.

## Development

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_commander.py

# Run with verbose output
pytest -v
```

### Code Quality
```bash
# Format code
ruff format src tests

# Lint code
ruff check src tests

# Type checking (optional)
mypy src
```

### Database

The project uses **SQLite** by default for local development (no Docker required). To use PostgreSQL:

```bash
# Start PostgreSQL with Docker
docker compose up -d

# Update .env
DATABASE_URL=postgresql://magic:magic@localhost:5432/magic_deck_builder
```

## Project Structure

```
magic-deck-builder/
├── src/
│   ├── cli/              # Command-line interface (Typer + Rich)
│   ├── database/         # SQLAlchemy models and engine
│   ├── engine/           # Commander eligibility and search logic
│   ├── ingestion/        # Scryfall client and bulk data loader
│   ├── models/           # Pydantic models (future use)
│   └── web/              # FastAPI REST API
├── tests/
│   ├── unit/             # Unit tests (38+ tests)
│   └── integration/      # Integration tests (future)
├── web/                  # React + TypeScript frontend (basic setup)
├── data/                 # SQLite database and cache (gitignored)
├── docs/                 # Documentation
│   └── discovery.md      # Product requirements and architecture
├── pyproject.toml        # Python dependencies and config
└── README.md
```

## Technologies

**Backend:**
- Python 3.9+
- FastAPI - REST API framework
- SQLAlchemy - ORM with SQLite/PostgreSQL support
- Typer + Rich - Beautiful CLI
- httpx - HTTP client for Scryfall API
- ijson - Streaming JSON parser
- Pydantic - Data validation

**Frontend (Basic Setup):**
- React 18
- TypeScript
- Vite

**Testing:**
- pytest
- pytest-cov
- hypothesis (property-based testing)

## Architecture

See [docs/discovery.md](docs/discovery.md) for:
- Product requirements
- Technical architecture
- Data models
- API integration details
- Future roadmap

## Security Features

- SHA-256 cache key hashing (prevents path traversal attacks)
- Proper JSON field typing
- Rate limiting for Scryfall API (75ms default)
- Input validation with Pydantic

## Contributing

1. Create a feature branch
2. Make your changes with tests
3. Run `pytest` and `ruff check`
4. Submit a pull request

## License

MIT License (or your preferred license)
