"""Scryfall API client with rate limiting and caching."""
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

from src.config import settings


class ScryfallClient:
    """Client for interacting with the Scryfall API.

    Complies with Scryfall ToS:
    - Required User-Agent and Accept headers
    - Rate limiting (50-100ms delay between requests)
    - Caching for at least 24 hours
    """

    BASE_URL = "https://api.scryfall.com"
    BULK_DATA_URL = f"{BASE_URL}/bulk-data"

    def __init__(
        self,
        user_agent: Optional[str] = None,
        rate_limit_ms: Optional[int] = None,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize Scryfall client.

        Args:
            user_agent: Custom user agent string
            rate_limit_ms: Delay between requests in milliseconds
            cache_dir: Directory for caching responses
        """
        self.user_agent = user_agent or settings.scryfall_user_agent
        self.rate_limit_ms = rate_limit_ms or settings.scryfall_rate_limit_ms
        self.cache_dir = cache_dir or settings.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_request_time: float = 0

        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed_ms = (time.time() - self.last_request_time) * 1000
        if elapsed_ms < self.rate_limit_ms:
            time.sleep((self.rate_limit_ms - elapsed_ms) / 1000)
        self.last_request_time = time.time()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key.

        Uses SHA-256 hash to prevent path traversal and collisions.
        """
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is still valid (within TTL)."""
        if not cache_path.exists():
            return False

        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        max_age = timedelta(hours=settings.cache_ttl_hours)
        return cache_age < max_age

    def _read_cache(self, cache_key: str) -> Optional[dict[str, Any]]:
        """Read data from cache if valid."""
        cache_path = self._get_cache_path(cache_key)
        if self._is_cache_valid(cache_path):
            with open(cache_path, "r") as f:
                return json.load(f)
        return None

    def _write_cache(self, cache_key: str, data: dict[str, Any]) -> None:
        """Write data to cache."""
        cache_path = self._get_cache_path(cache_key)
        with open(cache_path, "w") as f:
            json.dump(data, f)

    def get_bulk_data_info(self, use_cache: bool = True) -> dict[str, Any]:
        """Get information about available bulk data files.

        Args:
            use_cache: Whether to use cached response if available

        Returns:
            Bulk data info from Scryfall API

        Raises:
            httpx.HTTPError: If request fails
        """
        cache_key = "bulk_data_info"

        if use_cache:
            cached = self._read_cache(cache_key)
            if cached:
                return cached

        self._rate_limit()

        with httpx.Client() as client:
            response = client.get(self.BULK_DATA_URL, headers=self.headers)
            response.raise_for_status()
            data = response.json()

        self._write_cache(cache_key, data)
        return data

    def download_bulk_file(
        self, download_url: str, output_path: Path, force: bool = False
    ) -> Path:
        """Download a bulk data file from Scryfall.

        Args:
            download_url: URL to download from
            output_path: Where to save the file
            force: Force re-download even if file exists

        Returns:
            Path to downloaded file

        Raises:
            httpx.HTTPError: If download fails
        """
        if output_path.exists() and not force:
            if self._is_cache_valid(output_path):
                return output_path

        self._rate_limit()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=300.0) as client:  # 5 minute timeout for large files
            with client.stream("GET", download_url, headers=self.headers) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

        return output_path

    def get_card_named(self, name: str, exact: bool = True) -> dict[str, Any]:
        """Get a card by name.

        Args:
            name: Card name to search for
            exact: Whether to do exact match or fuzzy search

        Returns:
            Card data from Scryfall

        Raises:
            httpx.HTTPError: If request fails
        """
        cache_key = f"card_named:{name}:exact={exact}"
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        self._rate_limit()

        endpoint = "exact" if exact else "fuzzy"
        url = f"{self.BASE_URL}/cards/named"

        with httpx.Client() as client:
            response = client.get(url, headers=self.headers, params={endpoint: name})
            response.raise_for_status()
            data = response.json()

        self._write_cache(cache_key, data)
        return data

    def search_cards(self, query: str, page: int = 1) -> dict[str, Any]:
        """Search cards using Scryfall search endpoint."""
        url = f"{self.BASE_URL}/cards/search"
        for attempt in range(3):
            self._rate_limit()
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.get(
                        url,
                        headers=self.headers,
                        params={"q": query, "page": page},
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.ReadTimeout:
                if attempt == 2:
                    raise
                time.sleep(1.0)
