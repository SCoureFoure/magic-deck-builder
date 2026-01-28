# Magic Deck Builder

Commander (EDH) deck builder with a CLI, FastAPI backend, and a Vite + React frontend for searching commanders, generating decks, and labeling synergy.

## Highlights

- Commander search with eligibility detection (legendary, partner, background, etc.)
- Deck generation with heuristic scoring, LLM agents, and optional council voting
- Council orchestration with YAML config, routing strategies, and vote aggregation
- Synergy training flows and community vote stats
- CLI ingestion of Scryfall bulk data with streaming JSON parsing
- Web UI for search, deck wizard, training, and Council Lab tuning

## Quick Start

```bash
# 1. Set up Python environment (requires Python 3.9+)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Copy environment variables
cp .env.example .env  # On Windows: copy .env.example .env

# 3. Install dependencies
pip install -e ".[dev]"

# 4. (Optional) Start PostgreSQL if you use the default DATABASE_URL
docker compose up -d

# 5. Ingest Scryfall data (takes a few minutes, downloads ~200MB)
python -m src.cli ingest bulk oracle_cards

# 6. Start the API
uvicorn src.web.app:app --reload --port 8000
```

Frontend (Vite):
```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. Set `VITE_API_BASE=http://localhost:8000` in `web/.env` for a custom API base.

## Environment

Core variables (see `.env.example`):

- `DATABASE_URL` (default points at PostgreSQL)
- `OPENAI_API_KEY` (required for LLM agents or council mode)
- `OPENAI_MODEL` (default `gpt-4o-mini`)

SQLite option for local-only use:
```
DATABASE_URL=sqlite:///./data/magic.db
```

## CLI Commands

### Ingestion
```bash
python -m src.cli ingest bulk oracle_cards
python -m src.cli ingest small --limit 20000
python -m src.cli ingest sample --limit 2000 --random-pages 3
python -m src.cli ingest file ./data/oracle_cards.json
python -m src.cli ingest bulk oracle_cards --force
```

### Commander Search
```bash
python -m src.cli search commander "Urza"
python -m src.cli search commander "Dragon" --limit 5
python -m src.cli search commander "Sisay" --populate
```

### Deck Generation
```bash
python -m src.cli generate deck "Atraxa"
python -m src.cli generate deck "Atraxa" --council --council-config council.yaml
python -m src.cli generate deck "Atraxa" --routing-strategy debate --debate-adjudicator-id llm-judge
```

### Evaluation
```bash
python -m src.cli eval golden --tasks data/test/golden_tasks.json --output results.json
```

## Web API

Start the backend:
```bash
uvicorn src.web.app:app --reload --port 8000
```

Key endpoints:

- `GET /api/health`
- `GET /api/commanders?query=...&limit=...&populate=...`
- `POST /api/decks/generate`
- `GET /api/commanders/{commander}/synergy?query=...`
- `GET /api/commanders/{commander}/synergy/top?limit=...&min_ratio=...`
- `POST /api/training/session/start`
- `GET /api/training/session/{id}/next`
- `POST /api/training/session/vote`
- `GET /api/training/stats`
- `GET /api/council/agents`
- `POST /api/council/agent/import`
- `POST /api/council/agent/export`
- `POST /api/training/council/analyze`
- `POST /api/training/council/consult`

Example deck generation:
```bash
curl -X POST http://localhost:8000/api/decks/generate \
  -H "Content-Type: application/json" \
  -d '{
    "commander_name": "Atraxa, Praetors'\'' Voice",
    "use_llm_agent": true,
    "use_council": true
  }'
```

## Council Configuration

Council behavior lives in `council.yaml` and is documented in `README-COUNCIL.md`.
Routing strategies include `parallel`, `sequential`, and `debate`. Most overrides can be passed via API or CLI.

## Frontend

The React app ships with:
- Commander search and eligibility results
- Deck Wizard for deck generation, roles, and metrics
- Synergy Training flow with vote stats
- Council Lab for per-agent prompts, weights, import/export, and live consults

Frontend lives in `web/`.

## Project Structure

```
magic-deck-builder/
├── src/
│   ├── cli/              # CLI (Typer + Rich)
│   ├── database/         # SQLAlchemy models and engine
│   ├── engine/           # Deck builder, council, metrics, validation
│   ├── ingestion/        # Scryfall client and bulk data loader
│   └── web/              # FastAPI REST API
├── web/                  # React + TypeScript frontend (Vite)
├── tests/                # Unit + integration tests
├── data/                 # Cache + local DB (gitignored)
├── docs/                 # Architecture and patterns
├── council.yaml
├── pyproject.toml
└── README.md
```

## Development

```bash
pytest
ruff format src tests
ruff check src tests
```

## Docs

See `docs/discovery.md` for architecture, and `docs/patterns/` for implementation patterns.
