# Testing: Pytest Structure

## Context
Use this pattern to organize tests in this project. Separates unit tests (isolated, fast) from integration tests (database, external dependencies) for efficient test execution during development.

## Implementation
**Directory structure:**
```
tests/
├── __init__.py
├── unit/               # Fast, isolated tests
│   ├── __init__.py
│   ├── test_*.py
├── integration/        # Slower tests with dependencies
│   ├── __init__.py
│   └── test_*.py
```

**Unit test conventions:**
- Test pure functions and business logic
- Use in-memory SQLite for database tests (`sqlite:///:memory:`)
- Mock external dependencies (HTTP, file I/O)
- Should run in <1s total

**Fixtures:**
- Database fixture: `@pytest.fixture` that creates in-memory DB, yields session, closes on cleanup
- Scope fixtures appropriately: function (default), module, or session
- Use `yield` for setup/teardown pattern

**Test naming:**
- File: `test_{module_name}.py`
- Function: `test_{function_name}_{scenario}()`
- Example: `test_is_commander_eligible_legendary_creature()`

**Assertions:**
- Test both positive and negative cases
- Assert return values and object state
- Use descriptive failure messages when needed

**Property-based testing:**
- Use Hypothesis for generative tests (not heavily used yet)
- Good for testing invariants (e.g., "all generated decks are legal")

## Trade-offs
**Optimizes for:**
- Fast feedback loop during development
- Clear separation of test types
- Easy to run subsets of tests

**Sacrifices:**
- No parallel test execution yet
- Some duplication between unit/integration fixtures
- Coverage reporting not enforced in CI

## Examples
- [tests/unit/test_database.py](tests/unit/test_database.py) - In-memory DB fixture and model tests
- [tests/unit/test_scryfall_client.py](tests/unit/test_scryfall_client.py) - Testing with mocked HTTP
- [tests/unit/test_bulk_ingest.py](tests/unit/test_bulk_ingest.py) - Streaming ingest edge cases

## Updated
2026-01-14: Initial pattern documentation
