"""
Data Store — merges items from disk scanner, Obsidian, and manual entries.
Persists manual items and overrides to a local JSON file.
"""

import json
import threading
from pathlib import Path
from datetime import datetime


DATA_FILE = Path(__file__).parent / "data" / "items.json"
MANUAL_FILE = Path(__file__).parent / "data" / "manual_items.json"
OVERRIDES_FILE = Path(__file__).parent / "data" / "overrides.json"


class DataStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._disk_items: list[dict] = []
        self._obsidian_items: list[dict] = []
        self._manual_items: list[dict] = []
        self._overrides: dict[str, dict] = {}  # id -> partial overrides
        self._load_persisted()

    def _ensure_data_dir(self):
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_persisted(self):
        self._ensure_data_dir()
        # Load manual items
        if MANUAL_FILE.exists():
            try:
                with open(MANUAL_FILE, "r", encoding="utf-8") as f:
                    self._manual_items = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._manual_items = []

        # Load overrides (user edits to auto-discovered items)
        if OVERRIDES_FILE.exists():
            try:
                with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
                    self._overrides = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._overrides = {}

    def _save_manual(self):
        self._ensure_data_dir()
        with open(MANUAL_FILE, "w", encoding="utf-8") as f:
            json.dump(self._manual_items, f, indent=2, default=str)

    def _save_overrides(self):
        self._ensure_data_dir()
        with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
            json.dump(self._overrides, f, indent=2, default=str)

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

            return all_items

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

    def update_item(self, item_id: str, updates: dict):
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

    def delete_item(self, item_id: str):
        """Delete a manual item or hide an auto-discovered item."""
        with self._lock:
            # Remove from manual
            self._manual_items = [i for i in self._manual_items if i["id"] != item_id]
            self._save_manual()

            # For auto-discovered items, mark as hidden via override
            self._overrides.setdefault(item_id, {})["_hidden"] = True
            self._save_overrides()

    def get_all_items_filtered(self) -> list[dict]:
        """Get all items excluding hidden ones."""
        return [i for i in self.get_all_items() if not i.get("_hidden")]

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
