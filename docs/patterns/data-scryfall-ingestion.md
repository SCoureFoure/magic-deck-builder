# Data: Scryfall Bulk Ingestion

## Context
Use this pattern when ingesting large datasets from Scryfall's bulk data API. Handles rate limiting, caching, and memory-efficient streaming to comply with Scryfall ToS and avoid loading 200MB+ JSON files into memory.

## Implementation
**Scryfall ToS compliance:**
- Required headers on every request: `User-Agent` (app/version) and `Accept: application/json`
- Rate limiting: 50-100ms delay between requests (~10 req/s average)
- Cache responses for at least 24 hours
- Use bulk data files for ingestion (not individual card API calls)

**Client design (`ScryfallClient`):**
- Singleton-like pattern: one client per process
- SHA-256 hash for cache keys (prevents path traversal attacks)
- Time-based cache validation (default 24h TTL)
- Streaming download with chunked writes (8KB chunks)
- Extended timeout for large files (300s vs default 30s)

**Streaming JSON parsing:**
- Use `ijson` library for memory-efficient parsing
- Process cards one at a time from ~200MB file
- Never load entire file into memory

**Database upsert pattern:**
- Batch commits every 500 cards (configurable)
- Query for existing card by `scryfall_id`
- Update if exists, insert if new
- Extract image URIs with fallback to card faces (for double-faced cards)

**Key technical decisions:**
- Cache key hashing: Security against path traversal, deterministic for same input
- Streaming vs loading: Keeps memory usage constant regardless of file size
- Upsert vs truncate/insert: Preserves any custom data added to cards

## Trade-offs
**Optimizes for:**
- Memory efficiency (processes 200MB+ files in <100MB RAM)
- ToS compliance (caching, rate limiting, proper headers)
- Resumability (can stop/restart without re-downloading)

**Sacrifices:**
- Slower than bulk insert (upsert checks existing records)
- No parallel processing (single-threaded streaming)
- Full re-scan on every ingest (could optimize with incremental updates)

## Examples
- [src/ingestion/scryfall_client.py:14-148](src/ingestion/scryfall_client.py) - Client with rate limiting and caching
- [src/ingestion/bulk_ingest.py:59-89](src/ingestion/bulk_ingest.py) - Upsert pattern with batch commits
- [src/ingestion/bulk_ingest.py:25-36](src/ingestion/bulk_ingest.py) - Image URI extraction with fallback

## Updated
2026-01-14: Initial pattern documentation
