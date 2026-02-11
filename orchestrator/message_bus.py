"""In-memory message bus for inter-agent communication."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class MessageBus:
    """Simple dict-based message bus that agents publish to and read from."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._timestamps: dict[str, str] = {}

    def publish(self, key: str, data: Any) -> None:
        """Publish data under a key (usually agent name)."""
        self._store[key] = data
        self._timestamps[key] = datetime.now().isoformat()
        logger.info(f"MessageBus: published '{key}'")

    def get(self, key: str) -> Any:
        """Retrieve data by key. Returns None if not found."""
        return self._store.get(key)

    def get_all(self) -> dict[str, Any]:
        """Return all published data."""
        return dict(self._store)

    def keys(self) -> list[str]:
        """Return all published keys."""
        return list(self._store.keys())

    def has(self, key: str) -> bool:
        return key in self._store

    def dump_json(self, path: Path) -> None:
        """Dump the full bus contents to a JSON file for debugging."""
        serializable = {}
        for k, v in self._store.items():
            if hasattr(v, "model_dump"):
                serializable[k] = v.model_dump()
            else:
                serializable[k] = v
        path.write_text(json.dumps(serializable, indent=2, default=str))
        logger.info(f"MessageBus: dumped to {path}")
