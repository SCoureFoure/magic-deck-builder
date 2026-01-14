"""Tests for Scryfall client."""
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from src.ingestion.scryfall_client import ScryfallClient


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def client(temp_cache_dir):
    """Create a Scryfall client with temp cache."""
    return ScryfallClient(
        user_agent="test-client/0.1.0", rate_limit_ms=10, cache_dir=temp_cache_dir
    )


def test_client_initialization(client, temp_cache_dir):
    """Test client initializes with correct settings."""
    assert client.user_agent == "test-client/0.1.0"
    assert client.rate_limit_ms == 10
    assert client.cache_dir == temp_cache_dir
    assert "User-Agent" in client.headers
    assert "Accept" in client.headers


def test_rate_limiting(client):
    """Test that rate limiting delays requests appropriately."""
    start = time.time()
    client._rate_limit()
    client._rate_limit()
    client._rate_limit()
    elapsed_ms = (time.time() - start) * 1000

    # Should have at least 2 delays (between 3 calls)
    min_expected_ms = 2 * client.rate_limit_ms
    assert elapsed_ms >= min_expected_ms * 0.9  # Allow 10% margin


def test_cache_path(client):
    """Test cache path generation uses hash."""
    cache_path = client._get_cache_path("test_key")
    # Should be a hash, not the raw key
    assert cache_path.name.endswith(".json")
    assert cache_path.name != "test_key.json"
    assert len(cache_path.name) == 69  # 64 char hash + .json
    assert cache_path.parent == client.cache_dir


def test_cache_path_prevents_traversal(client):
    """Test that cache path prevents directory traversal attacks."""
    dangerous_keys = [
        "../../../etc/passwd",
        "../../dangerous",
        "some/nested/path",
        "file with / slash",
    ]

    for key in dangerous_keys:
        cache_path = client._get_cache_path(key)
        # All should be in the cache dir, not escaped
        assert cache_path.parent == client.cache_dir
        # Should not contain slashes in filename
        assert "/" not in cache_path.name[:-5]  # Exclude .json extension


def test_cache_write_and_read(client):
    """Test writing and reading from cache."""
    test_data = {"name": "Sol Ring", "cmc": 1}
    cache_key = "test_card"

    client._write_cache(cache_key, test_data)
    cached_data = client._read_cache(cache_key)

    assert cached_data == test_data


def test_cache_expiry(client, temp_cache_dir):
    """Test that cache expires after TTL."""
    test_data = {"name": "Sol Ring"}
    cache_key = "test_expiry"
    cache_path = client._get_cache_path(cache_key)

    # Write cache
    client._write_cache(cache_key, test_data)
    assert client._is_cache_valid(cache_path)

    # Manually set file modification time to past
    old_time = time.time() - (25 * 60 * 60)  # 25 hours ago
    import os

    os.utime(cache_path, (old_time, old_time))

    # Cache should be invalid
    assert not client._is_cache_valid(cache_path)


@patch("httpx.Client")
def test_get_bulk_data_info(mock_client_class, client):
    """Test fetching bulk data info."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"type": "oracle_cards"}]}
    mock_client = Mock()
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    result = client.get_bulk_data_info(use_cache=False)

    assert result == {"data": [{"type": "oracle_cards"}]}
    mock_client.get.assert_called_once()
    assert "User-Agent" in mock_client.get.call_args[1]["headers"]


@patch("httpx.Client")
def test_get_bulk_data_info_uses_cache(mock_client_class, client):
    """Test that bulk data info uses cache."""
    # Pre-populate cache
    cached_data = {"data": [{"type": "cached"}]}
    client._write_cache("bulk_data_info", cached_data)

    result = client.get_bulk_data_info(use_cache=True)

    # Should return cached data without making request
    assert result == cached_data
    mock_client_class.assert_not_called()


@patch("httpx.Client")
def test_get_card_named(mock_client_class, client):
    """Test fetching a card by name."""
    mock_response = Mock()
    mock_response.json.return_value = {"name": "Sol Ring", "cmc": 1}
    mock_client = Mock()
    mock_client.get.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    result = client.get_card_named("Sol Ring", exact=True)

    assert result["name"] == "Sol Ring"
    assert result["cmc"] == 1
    mock_client.get.assert_called_once()


def test_download_bulk_file(client, temp_cache_dir):
    """Test downloading bulk file (mocked)."""
    output_path = temp_cache_dir / "test_bulk.json"
    test_data = b'[{"name": "Sol Ring"}]'

    with patch("httpx.Client") as mock_client_class:
        mock_response = Mock()
        mock_response.iter_bytes.return_value = [test_data]
        mock_response.raise_for_status = Mock()

        mock_stream = Mock()
        mock_stream.__enter__ = Mock(return_value=mock_response)
        mock_stream.__exit__ = Mock(return_value=False)

        mock_client = Mock()
        mock_client.stream.return_value = mock_stream
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client_class.return_value.__exit__ = Mock(return_value=False)

        result = client.download_bulk_file(
            "https://example.com/bulk.json", output_path, force=True
        )

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == test_data
