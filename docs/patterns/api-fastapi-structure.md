# API: FastAPI Structure

## Context
Use this pattern for building REST APIs in this project. Establishes conventions for endpoint organization, CORS configuration, and response models.

## Implementation
**App structure:**
- Single FastAPI app instance in `src/web/app.py`
- Pydantic models for request/response validation
- Type hints on all endpoints for automatic OpenAPI docs

**CORS configuration:**
- Explicit origin allowlist (currently `http://localhost:5173` for Vite dev server)
- Allow credentials, all methods, all headers for development
- Tighten for production: specific origins, methods, headers

**Response models:**
- Define Pydantic `BaseModel` classes for all responses
- Use `response_model` parameter on endpoint decorators for validation
- Optional fields use `Optional[Type]`, required fields without default

**Error handling:**
- `HTTPException` for expected errors (404 not found, 400 bad input)
- Include helpful `detail` messages in exceptions
- Let FastAPI handle serialization to JSON

**Database access:**
- Use context manager pattern: `with get_db() as db:`
- Ensures connection cleanup even on errors
- Pass db session to engine functions, don't create in endpoints

## Trade-offs
**Optimizes for:**
- Type safety and auto-generated docs
- Fast iteration with hot reload
- Clear separation between API layer and business logic

**Sacrifices:**
- More boilerplate than Flask (Pydantic models)
- Async capabilities not used yet (all endpoints are sync)
- No request logging middleware yet

## Examples
- [src/web/app.py:35-43](src/web/app.py) - FastAPI app setup with CORS
- [src/web/app.py:14-33](src/web/app.py) - Pydantic response models
- [src/web/app.py:52-85](src/web/app.py) - Endpoint with response model and error handling

## Operations

### Starting the Backend
```bash
# Kill any existing process and start fresh
lsof -ti:8000 | xargs kill -9 2>/dev/null
.venv/bin/uvicorn src.web.app:app --reload --port 8000
```

**Important:** Always use `.venv/bin/uvicorn` or `.venv/bin/python` - the project uses a Python virtual environment and system Python won't have the required dependencies.

### Starting the Frontend
```bash
cd web && npm run dev
```
Frontend runs on port 5173 and proxies API calls to the backend on port 8000.

### Health Checks
```bash
# Backend health
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}

# Test endpoint
curl "http://localhost:8000/api/commanders?query=Atraxa&limit=1"
```

### Running CLI Commands
```bash
# Always use venv Python
.venv/bin/python -m src.cli search commander "Atraxa"
.venv/bin/python -m src.cli generate deck "Sisay"
```

### Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError` | Using system Python | Use `.venv/bin/python` |
| `database is locked` | Hung process holding DB | `lsof data/magic_deck_builder.db` then `kill -9 <PID>` |
| Port already in use | Stale process | `lsof -ti:8000 \| xargs kill -9` |
| Frontend can't reach API | Backend not running | Start backend, verify with health check |
| CORS errors | Origin mismatch | Backend allows `http://localhost:5173` only |

### Process Management

**Find what's using a port:**
```bash
lsof -i:8000  # Shows process on port 8000
```

**Kill process by port:**
```bash
lsof -ti:8000 | xargs kill -9
```

**Find processes holding the database:**
```bash
lsof data/magic_deck_builder.db
```

## Updated
2026-01-14: Added operations and troubleshooting section
2026-01-14: Initial pattern documentation
