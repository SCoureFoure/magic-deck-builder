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

## Updated
2026-01-14: Initial pattern documentation
