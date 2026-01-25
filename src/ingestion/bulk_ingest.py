"""Bulk ingestion utilities for Scryfall data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

import ijson
from sqlalchemy.orm import Session

from src.database.models import Card
from src.ingestion.scryfall_client import ScryfallClient


def select_bulk_download_url(bulk_info: dict[str, Any], bulk_type: str) -> str:
    """Select the download URL for a bulk data type."""
    for item in bulk_info.get("data", []):
        if item.get("type") == bulk_type:
            download_uri = item.get("download_uri")
            if download_uri:
                return download_uri
    raise ValueError(f"Bulk data type not found: {bulk_type}")


def _extract_image_uris(card_data: dict[str, Any]) -> dict[str, str] | None:
    """Extract image URIs from a card, falling back to card faces."""
    image_uris = card_data.get("image_uris")
    if image_uris:
        return image_uris

    for face in card_data.get("card_faces", []):
        face_uris = face.get("image_uris")
        if face_uris:
            return face_uris

    return None


def map_card_data(card_data: dict[str, Any]) -> dict[str, Any]:
    """Map Scryfall card JSON to Card model fields."""
    prices = card_data.get("prices") or {}
    price_usd = prices.get("usd")

    return {
        "scryfall_id": card_data["id"],
        "name": card_data["name"],
        "type_line": card_data.get("type_line", ""),
        "oracle_text": card_data.get("oracle_text"),
        "colors": card_data.get("colors"),
        "color_identity": card_data.get("color_identity", []),
        "mana_cost": card_data.get("mana_cost"),
        "cmc": float(card_data.get("cmc", 0)),
        "legalities": card_data.get("legalities", {}),
        "price_usd": float(price_usd) if price_usd else None,
        "image_uris": _extract_image_uris(card_data),
        "card_faces": card_data.get("card_faces"),
    }


def upsert_cards(
    session: Session,
    card_iter: Iterable[dict[str, Any]],
    batch_size: int = 500,
    limit: int | None = None,
    filter_fn: Callable[[dict[str, Any]], bool] | None = None,
) -> int:
    """Insert or update cards from an iterable of Scryfall card data."""
    processed = 0

    for card_data in card_iter:
        if filter_fn and not filter_fn(card_data):
            continue
        if card_data.get("object") != "card":
            continue
        if not card_data.get("id"):
            continue

        mapped = map_card_data(card_data)
        existing = (
            session.query(Card).filter_by(scryfall_id=mapped["scryfall_id"]).one_or_none()
        )
        if existing:
            for key, value in mapped.items():
                setattr(existing, key, value)
        else:
            session.add(Card(**mapped))

        processed += 1
        if processed % batch_size == 0:
            session.commit()
        if limit is not None and processed >= limit:
            break

    session.commit()
    return processed


def ingest_bulk_file(
    session: Session,
    bulk_path: Path,
    limit: int | None = None,
    filter_fn: Callable[[dict[str, Any]], bool] | None = None,
) -> int:
    """Ingest a local Scryfall bulk JSON file into the database."""
    with open(bulk_path, "rb") as handle:
        try:
            for _, event, _ in ijson.parse(handle):
                if event == "start_array":
                    break
                if event in {"start_map", "null", "boolean", "number", "string"}:
                    raise ValueError("Bulk file did not contain a list of cards.")
        except ijson.JSONError as exc:
            raise json.JSONDecodeError("Invalid JSON", "", 0) from exc

        handle.seek(0)
        items = ijson.items(handle, "item")
        return upsert_cards(session, items, limit=limit, filter_fn=filter_fn)


def commander_legal_filter(card_data: dict[str, Any]) -> bool:
    legalities = card_data.get("legalities") or {}
    return legalities.get("commander") == "legal"


def download_and_ingest_bulk(
    session: Session,
    client: ScryfallClient,
    bulk_type: str = "oracle_cards",
    output_dir: Path | None = None,
    force_download: bool = False,
    limit: int | None = None,
    filter_fn: Callable[[dict[str, Any]], bool] | None = None,
) -> int:
    """Download and ingest a Scryfall bulk data type."""
    bulk_info = client.get_bulk_data_info()
    download_uri = select_bulk_download_url(bulk_info, bulk_type)

    output_dir = output_dir or client.cache_dir / "bulk"
    output_path = output_dir / f"{bulk_type}.json"
    client.download_bulk_file(download_uri, output_path, force=force_download)

    return ingest_bulk_file(session, output_path, limit=limit, filter_fn=filter_fn)
