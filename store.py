"""
Data Store — merges items from disk scanner, Obsidian, and manual entries.
Persists manual items and overrides to a local JSON file.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import tempfile
from typing import Any
import threading
from pathlib import Path
from datetime import datetime

log = logging.getLogger("tasktray")

DATA_FILE = Path(__file__).parent / "data" / "items.json"
MANUAL_FILE = Path(__file__).parent / "data" / "manual_items.json"
OVERRIDES_FILE = Path(__file__).parent / "data" / "overrides.json"

CURRENT_SCHEMA_VERSION = 1


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._disk_items: list[dict] = []
        self._obsidian_items: list[dict] = []
        self._manual_items: list[dict] = []
        self._overrides: dict[str, dict] = {}  # id -> partial overrides
        self._read_only = False
        self._load_persisted()

    def _ensure_data_dir(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, filepath: Path, data: object) -> None:
        """Write JSON atomically: write to temp file, then os.replace()."""
        fd, tmp_path = tempfile.mkstemp(
            dir=filepath.parent, suffix=".tmp", prefix=filepath.stem
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            # Create backup before replacing
            if filepath.exists():
                backup = filepath.with_suffix(".json.bak")
                try:
                    shutil.copy2(filepath, backup)
                except OSError:
                    pass
            os.replace(tmp_path, filepath)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load_json_with_backup(self, filepath: Path, default: Any) -> Any:
        """Load JSON from filepath, falling back to .bak on error."""
        # Try primary file
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Failed to load %s: %s; trying backup", filepath, e)

        # Try backup file
        backup = filepath.with_suffix(".json.bak")
        if backup.exists():
            try:
                with open(backup, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Failed to load backup %s: %s; using empty default", backup, e)

        # Both corrupted or missing — return fresh empty of same type
        return type(default)()

    def _migrate_if_needed(self, data: Any, filepath: Path) -> Any:
        """Normalise data to versioned dict format and check schema version.

        Returns the normalised data dict.  Sets self._read_only = True if the
        file was written by a newer version of the schema.
        """
        # v0 legacy: plain list -> wrap it
        if isinstance(data, list):
            data = {"_schema_version": 0, "items": data}

        version = data.get("_schema_version", 0)

        if version > CURRENT_SCHEMA_VERSION:
            log.error(
                "File %s has schema version %d > current %d; entering read-only mode",
                filepath, version, CURRENT_SCHEMA_VERSION,
            )
            self._read_only = True
            return data

        # v0 -> v1: identity migration — just bump the version number
        if version < CURRENT_SCHEMA_VERSION:
            data["_schema_version"] = CURRENT_SCHEMA_VERSION

        return data

    def _load_persisted(self) -> None:
        self._ensure_data_dir()

        # --- manual items ---
        raw_manual = self._load_json_with_backup(MANUAL_FILE, [])
        manual_version_before = raw_manual.get("_schema_version", 0) if isinstance(raw_manual, dict) else 0
        manual_data = self._migrate_if_needed(raw_manual, MANUAL_FILE)
        self._manual_items = manual_data.get("items", [])
        # Persist immediately if version was bumped (v0 → v1)
        if manual_data.get("_schema_version", 0) > manual_version_before and not self._read_only:
            self._save_manual()

        # --- overrides ---
        raw_overrides = self._load_json_with_backup(OVERRIDES_FILE, {})
        overrides_version_before = raw_overrides.get("_schema_version", 0) if isinstance(raw_overrides, dict) else 0
        overrides_data = self._migrate_if_needed(raw_overrides, OVERRIDES_FILE)
        # Strip the version key before storing overrides
        self._overrides = {k: v for k, v in overrides_data.items() if k != "_schema_version"}
        # Persist immediately if version was bumped (v0 → v1)
        if overrides_data.get("_schema_version", 0) > overrides_version_before and not self._read_only:
            self._save_overrides()

    def _save_manual(self) -> None:
        if self._read_only:
            raise RuntimeError("DataStore is read-only due to schema version mismatch")
        self._ensure_data_dir()
        self._atomic_write(MANUAL_FILE, {"_schema_version": CURRENT_SCHEMA_VERSION, "items": self._manual_items})

    def _save_overrides(self) -> None:
        if self._read_only:
            raise RuntimeError("DataStore is read-only due to schema version mismatch")
        self._ensure_data_dir()
        self._atomic_write(OVERRIDES_FILE, {"_schema_version": CURRENT_SCHEMA_VERSION, **self._overrides})

    def update_disk_items(self, items: list[dict]):
        with self._lock:
            self._disk_items = items

    def update_obsidian_items(self, items: list[dict]):
        with self._lock:
            self._obsidian_items = items

    def get_all_items(self) -> list[dict]:
        """Return merged list with overrides applied."""
        with self._lock:
            all_items = []
            seen_ids = set()

            # Manual items first (highest priority)
            for item in self._manual_items:
                all_items.append(item)
                seen_ids.add(item["id"])

            # Obsidian items
            for item in self._obsidian_items:
                if item["id"] not in seen_ids:
                    merged = {**item, **self._overrides.get(item["id"], {})}
                    all_items.append(merged)
                    seen_ids.add(item["id"])

            # Disk items
            for item in self._disk_items:
                if item["id"] not in seen_ids:
                    merged = {**item, **self._overrides.get(item["id"], {})}
                    all_items.append(merged)
                    seen_ids.add(item["id"])

            return copy.deepcopy(all_items)

    def has_status_override(self, item_id: str) -> bool:
        """Check if an item has a manual status override."""
        with self._lock:
            override = self._overrides.get(item_id, {})
            if isinstance(override, dict):
                return "status" in override
            return False

    def is_manual_item(self, item_id: str) -> bool:
        """Check if an item exists as a manual item (prevents auto-promote collisions)."""
        with self._lock:
            return any(i["id"] == item_id for i in self._manual_items)

    def add_manual_item(self, item: dict) -> dict:
        """Add a new manual item."""
        with self._lock:
            if "id" not in item:
                item["id"] = f"manual_{int(datetime.now().timestamp() * 1000):x}"
            if "created_at" not in item:
                item["created_at"] = datetime.now().isoformat()
            item["source"] = "manual"
            self._manual_items.insert(0, item)
            self._save_manual()
            return item

    def update_item(self, item_id: str, updates: dict) -> dict:
        """Update an item. Manual items are updated directly; others get overrides."""
        with self._lock:
            # Check if it's a manual item
            for i, item in enumerate(self._manual_items):
                if item["id"] == item_id:
                    self._manual_items[i] = {**item, **updates}
                    self._save_manual()
                    return self._manual_items[i]

            # Otherwise store as override
            self._overrides.setdefault(item_id, {}).update(updates)
            self._save_overrides()
            return updates

    def delete_item(self, item_id: str) -> None:
        """Delete a manual item or hide an auto-discovered item."""
        with self._lock:
            # Check if item was in manual items before removal
            was_manual = any(i["id"] == item_id for i in self._manual_items)

            if was_manual:
                self._manual_items = [i for i in self._manual_items if i["id"] != item_id]
                self._save_manual()
            else:
                # For auto-discovered items, mark as hidden via override
                self._overrides.setdefault(item_id, {})["_hidden"] = True
                self._save_overrides()

    def get_all_items_filtered(self) -> list[dict]:
        """Get all items excluding hidden ones. Strips internal-only fields."""
        result = []
        for i in self.get_all_items():
            if not i.get("_hidden"):
                i.pop("has_recent_activity", None)
                result.append(i)
        return result

    def get_stats(self) -> dict:
        items = self.get_all_items_filtered()
        return {
            "total": len(items),
            "active": sum(1 for i in items if i.get("status") == "active"),
            "backlog": sum(1 for i in items if i.get("status") == "backlog"),
            "paused": sum(1 for i in items if i.get("status") == "paused"),
            "done": sum(1 for i in items if i.get("status") == "done"),
            "by_source": {
                "disk": sum(1 for i in items if i.get("source") == "disk"),
                "obsidian": sum(1 for i in items if i.get("source") == "obsidian"),
                "manual": sum(1 for i in items if i.get("source") == "manual"),
            },
            "focused": sum(1 for i in items if i.get("focused")),
        }
