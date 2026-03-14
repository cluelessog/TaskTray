"""Tests for store.py — targeting >= 80% coverage."""
import json
import threading
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store as store_module
from store import DataStore


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """DataStore with all file paths redirected to tmp_path."""
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    return DataStore()


# ── Init ──────────────────────────────────────────────────────────────────────

def test_init_creates_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "subdir"
    manual = data_dir / "manual_items.json"
    overrides = data_dir / "overrides.json"
    monkeypatch.setattr(store_module, "MANUAL_FILE", manual)
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", overrides)
    monkeypatch.setattr(store_module, "DATA_FILE", data_dir / "items.json")
    DataStore()
    assert data_dir.exists()


def test_init_empty_when_no_files(isolated_store):
    items = isolated_store.get_all_items()
    assert items == []


def test_init_loads_existing_manual_items(tmp_path, monkeypatch):
    manual_file = tmp_path / "manual_items.json"
    manual_file.write_text(json.dumps([{"id": "manual_abc", "title": "Existing", "source": "manual"}]))
    monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    items = s.get_all_items()
    assert len(items) == 1
    assert items[0]["title"] == "Existing"


def test_init_loads_existing_overrides(tmp_path, monkeypatch):
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text(json.dumps({"disk_001": {"status": "done"}}))
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", overrides_file)
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    s.update_disk_items([{"id": "disk_001", "title": "Proj", "source": "disk", "status": "active"}])
    items = s.get_all_items()
    assert items[0]["status"] == "done"


def test_init_handles_corrupted_manual_json(tmp_path, monkeypatch):
    manual_file = tmp_path / "manual_items.json"
    manual_file.write_text("NOT VALID JSON {{{")
    monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    assert s.get_all_items() == []


def test_init_handles_corrupted_overrides_json(tmp_path, monkeypatch):
    overrides_file = tmp_path / "overrides.json"
    overrides_file.write_text("{bad json")
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", overrides_file)
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    assert s._overrides == {}


# ── add_manual_item ───────────────────────────────────────────────────────────

def test_add_manual_item_sets_title(isolated_store):
    item = isolated_store.add_manual_item({"title": "My Task"})
    assert item["title"] == "My Task"


def test_add_manual_item_generates_id_with_manual_prefix(isolated_store):
    item = isolated_store.add_manual_item({"title": "X"})
    assert item["id"].startswith("manual_")


def test_add_manual_item_sets_source_manual(isolated_store):
    item = isolated_store.add_manual_item({"title": "X"})
    assert item["source"] == "manual"


def test_add_manual_item_sets_created_at(isolated_store):
    item = isolated_store.add_manual_item({"title": "X"})
    assert "created_at" in item
    assert item["created_at"]


def test_add_manual_item_persists_to_disk(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    s.add_manual_item({"title": "Persist me"})
    manual_file = tmp_path / "manual_items.json"
    assert manual_file.exists()
    saved = json.loads(manual_file.read_text()).get("items", [])
    assert any(i["title"] == "Persist me" for i in saved)


def test_add_manual_item_preserves_provided_id(isolated_store):
    item = isolated_store.add_manual_item({"id": "custom_id_123", "title": "Custom"})
    assert item["id"] == "custom_id_123"


# ── update_item ───────────────────────────────────────────────────────────────

def test_update_item_updates_manual_item_fields(isolated_store):
    added = isolated_store.add_manual_item({"title": "Old Title"})
    result = isolated_store.update_item(added["id"], {"title": "New Title"})
    assert result["title"] == "New Title"
    items = isolated_store.get_all_items()
    assert items[0]["title"] == "New Title"


def test_update_item_persists_manual_update(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    added = s.add_manual_item({"title": "Orig"})
    s.update_item(added["id"], {"status": "done"})
    saved = json.loads((tmp_path / "manual_items.json").read_text()).get("items", [])
    assert saved[0]["status"] == "done"


def test_update_item_creates_override_for_disk_item(isolated_store):
    isolated_store.update_disk_items([{"id": "disk_001", "title": "Disk Proj", "source": "disk"}])
    isolated_store.update_item("disk_001", {"status": "paused"})
    items = isolated_store.get_all_items()
    disk_item = next(i for i in items if i["id"] == "disk_001")
    assert disk_item["status"] == "paused"


def test_update_item_persists_override(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    s.update_disk_items([{"id": "disk_001", "title": "X", "source": "disk"}])
    s.update_item("disk_001", {"priority": "p0"})
    saved = json.loads((tmp_path / "overrides.json").read_text())
    assert saved["disk_001"]["priority"] == "p0"


# ── delete_item ───────────────────────────────────────────────────────────────

def test_delete_item_removes_manual_item(isolated_store):
    added = isolated_store.add_manual_item({"title": "Delete me"})
    isolated_store.delete_item(added["id"])
    items = isolated_store.get_all_items()
    assert not any(i["id"] == added["id"] for i in items)


def test_delete_item_hides_disk_item_via_override(isolated_store):
    isolated_store.update_disk_items([{"id": "disk_999", "title": "Auto", "source": "disk"}])
    isolated_store.delete_item("disk_999")
    assert isolated_store._overrides.get("disk_999", {}).get("_hidden") is True


def test_delete_item_excluded_from_filtered(isolated_store):
    isolated_store.update_disk_items([{"id": "disk_999", "title": "Auto", "source": "disk"}])
    isolated_store.delete_item("disk_999")
    filtered = isolated_store.get_all_items_filtered()
    assert not any(i["id"] == "disk_999" for i in filtered)


# ── get_all_items ─────────────────────────────────────────────────────────────

def test_get_all_items_merges_all_sources(isolated_store):
    isolated_store.add_manual_item({"title": "Manual"})
    isolated_store.update_disk_items([{"id": "disk_1", "title": "Disk", "source": "disk"}])
    isolated_store.update_obsidian_items([{"id": "obs_1", "title": "Obs", "source": "obsidian"}])
    items = isolated_store.get_all_items()
    sources = {i["source"] for i in items}
    assert "manual" in sources
    assert "disk" in sources
    assert "obsidian" in sources


def test_get_all_items_deduplicates_by_id(isolated_store):
    isolated_store.update_disk_items([{"id": "dup_id", "title": "Disk", "source": "disk"}])
    isolated_store.update_obsidian_items([{"id": "dup_id", "title": "Obs", "source": "obsidian"}])
    items = isolated_store.get_all_items()
    assert sum(1 for i in items if i["id"] == "dup_id") == 1


def test_get_all_items_applies_overrides(isolated_store):
    isolated_store.update_disk_items([{"id": "disk_x", "title": "Original", "source": "disk", "status": "active"}])
    isolated_store._overrides["disk_x"] = {"status": "done"}
    items = isolated_store.get_all_items()
    assert items[0]["status"] == "done"


def test_get_all_items_manual_items_first(isolated_store):
    isolated_store.update_disk_items([{"id": "disk_first", "title": "Disk", "source": "disk"}])
    isolated_store.add_manual_item({"title": "Manual"})
    items = isolated_store.get_all_items()
    assert items[0]["source"] == "manual"


# ── get_all_items_filtered ────────────────────────────────────────────────────

def test_get_all_items_filtered_excludes_hidden(isolated_store):
    isolated_store.update_disk_items([
        {"id": "visible", "title": "Visible", "source": "disk"},
        {"id": "hidden_one", "title": "Hidden", "source": "disk"},
    ])
    isolated_store._overrides["hidden_one"] = {"_hidden": True}
    filtered = isolated_store.get_all_items_filtered()
    ids = [i["id"] for i in filtered]
    assert "visible" in ids
    assert "hidden_one" not in ids


def test_get_all_items_filtered_includes_non_hidden(isolated_store):
    isolated_store.add_manual_item({"title": "Keep me"})
    filtered = isolated_store.get_all_items_filtered()
    assert len(filtered) == 1


# ── get_stats ─────────────────────────────────────────────────────────────────

def test_get_stats_counts_by_status(isolated_store):
    isolated_store.update_disk_items([
        {"id": "d1", "title": "A", "source": "disk", "status": "active"},
        {"id": "d2", "title": "B", "source": "disk", "status": "done"},
        {"id": "d3", "title": "C", "source": "disk", "status": "backlog"},
        {"id": "d4", "title": "D", "source": "disk", "status": "paused"},
    ])
    stats = isolated_store.get_stats()
    assert stats["total"] == 4
    assert stats["active"] == 1
    assert stats["done"] == 1
    assert stats["backlog"] == 1
    assert stats["paused"] == 1


def test_get_stats_counts_by_source(isolated_store):
    isolated_store.add_manual_item({"title": "Manual"})
    isolated_store.update_disk_items([{"id": "d1", "title": "Disk", "source": "disk"}])
    isolated_store.update_obsidian_items([{"id": "o1", "title": "Obs", "source": "obsidian"}])
    stats = isolated_store.get_stats()
    assert stats["by_source"]["manual"] == 1
    assert stats["by_source"]["disk"] == 1
    assert stats["by_source"]["obsidian"] == 1


def test_get_stats_counts_focused(isolated_store):
    isolated_store.update_disk_items([
        {"id": "d1", "title": "A", "source": "disk", "focused": True},
        {"id": "d2", "title": "B", "source": "disk", "focused": False},
    ])
    stats = isolated_store.get_stats()
    assert stats["focused"] == 1


def test_get_stats_excludes_hidden(isolated_store):
    isolated_store.update_disk_items([
        {"id": "d1", "title": "A", "source": "disk", "status": "active"},
        {"id": "d2", "title": "B", "source": "disk", "status": "active"},
    ])
    isolated_store._overrides["d2"] = {"_hidden": True}
    stats = isolated_store.get_stats()
    assert stats["total"] == 1
    assert stats["active"] == 1


# ── Thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_adds_all_succeed(isolated_store):
    errors = []

    def add_item(n):
        try:
            isolated_store.add_manual_item({"title": f"Item {n}"})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add_item, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Errors during concurrent adds: {errors}"
    items = isolated_store.get_all_items()
    assert len(items) == 10


# ── TestAtomicWrites ──────────────────────────────────────────────────────────

class TestAtomicWrites:
    def test_atomic_write_creates_file(self, tmp_path, monkeypatch):
        """Atomic write produces valid JSON."""
        monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        s.add_manual_item({"title": "Atomic Item"})
        manual_file = tmp_path / "manual_items.json"
        assert manual_file.exists()
        data = json.loads(manual_file.read_text()).get("items", [])
        assert isinstance(data, list)
        assert any(i["title"] == "Atomic Item" for i in data)

    def test_atomic_write_creates_backup(self, tmp_path, monkeypatch):
        """Second save creates .bak of previous version."""
        monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        s.add_manual_item({"title": "First Item"})
        s.add_manual_item({"title": "Second Item"})
        backup = tmp_path / "manual_items.json.bak"
        assert backup.exists()


# ── TestBackupOnLoad ──────────────────────────────────────────────────────────

class TestBackupOnLoad:
    def test_loads_backup_on_corrupted_primary(self, tmp_path, monkeypatch):
        """If primary JSON is corrupted, fall back to .bak."""
        manual_file = tmp_path / "manual_items.json"
        backup_file = tmp_path / "manual_items.json.bak"
        manual_file.write_text("NOT VALID JSON {{{")
        backup_file.write_text(json.dumps([{"id": "bak_1", "title": "From Backup", "source": "manual"}]))
        monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        items = s.get_all_items()
        assert len(items) == 1
        assert items[0]["title"] == "From Backup"

    def test_empty_when_both_corrupted(self, tmp_path, monkeypatch):
        """If both primary and backup are corrupted, return empty."""
        manual_file = tmp_path / "manual_items.json"
        backup_file = tmp_path / "manual_items.json.bak"
        manual_file.write_text("BAD JSON")
        backup_file.write_text("ALSO BAD JSON")
        monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        assert s.get_all_items() == []


# ── TestDeepcopy ──────────────────────────────────────────────────────────────

class TestDeepcopy:
    def test_returns_independent_copy(self, tmp_path, monkeypatch):
        """Mutating returned items must not affect store internals."""
        monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        s.add_manual_item({"title": "Original"})
        items1 = s.get_all_items()
        items1[0]["title"] = "Mutated"
        items2 = s.get_all_items()
        assert items2[0]["title"] == "Original"


# ── TestDeleteItemFix ─────────────────────────────────────────────────────────

class TestDeleteItemFix:
    def test_delete_manual_only_saves_manual(self, tmp_path, monkeypatch):
        """Deleting manual item must not write overrides file."""
        monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        added = s.add_manual_item({"title": "Manual to Delete"})
        overrides_file = tmp_path / "overrides.json"
        # Remove overrides file so we can detect if it's written
        if overrides_file.exists():
            overrides_file.unlink()
        s.delete_item(added["id"])
        # Overrides file should NOT have been created for a manual item deletion
        assert not overrides_file.exists()

    def test_delete_auto_only_saves_overrides(self, tmp_path, monkeypatch):
        """Hiding auto item must not rewrite manual file."""
        manual_file = tmp_path / "manual_items.json"
        monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        s.update_disk_items([{"id": "disk_auto", "title": "Auto Item", "source": "disk"}])
        # Remove manual file to detect if it's written
        if manual_file.exists():
            manual_file.unlink()
        s.delete_item("disk_auto")
        # Manual file should NOT have been written for an auto item deletion
        assert not manual_file.exists()
        assert s._overrides.get("disk_auto", {}).get("_hidden") is True


# ── TestRLock ─────────────────────────────────────────────────────────────────

class TestRLock:
    def test_lock_is_rlock(self, tmp_path, monkeypatch):
        """Store must use RLock, not Lock."""
        monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
        monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
        monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
        s = DataStore()
        assert isinstance(s._lock, type(threading.RLock()))


# ── JSON Schema Versioning ─────────────────────────────────────────────────────

def test_schema_version_saved_in_manual_items(tmp_path, monkeypatch):
    """manual_items.json must contain _schema_version: 1 after saving."""
    manual_file = tmp_path / "manual_items.json"
    monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    s.add_manual_item({"title": "Versioned Task"})
    raw = json.loads(manual_file.read_text())
    assert raw.get("_schema_version") == 1


def test_schema_version_saved_in_overrides(tmp_path, monkeypatch):
    """overrides.json must contain _schema_version: 1 after saving."""
    overrides_file = tmp_path / "overrides.json"
    monkeypatch.setattr(store_module, "MANUAL_FILE", tmp_path / "manual_items.json")
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", overrides_file)
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    s.update_disk_items([{"id": "disk_v", "title": "Disk", "source": "disk"}])
    s.update_item("disk_v", {"status": "done"})
    raw = json.loads(overrides_file.read_text())
    assert raw.get("_schema_version") == 1


def test_versionless_file_migrated(tmp_path, monkeypatch):
    """Old plain-list manual_items.json (v0) must load and re-save with version."""
    manual_file = tmp_path / "manual_items.json"
    manual_file.write_text(json.dumps([{"id": "old_1", "title": "Legacy", "source": "manual"}]))
    monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    items = s.get_all_items()
    assert len(items) == 1
    assert items[0]["title"] == "Legacy"
    # After adding an item, file should be re-saved with version
    s.add_manual_item({"title": "New Item"})
    raw = json.loads(manual_file.read_text())
    assert raw.get("_schema_version") == 1


def test_downgrade_refusal_read_only(tmp_path, monkeypatch):
    """A file with _schema_version > CURRENT_SCHEMA_VERSION causes read-only mode; writes raise RuntimeError."""
    manual_file = tmp_path / "manual_items.json"
    manual_file.write_text(json.dumps({"_schema_version": 999, "items": []}))
    monkeypatch.setattr(store_module, "MANUAL_FILE", manual_file)
    monkeypatch.setattr(store_module, "OVERRIDES_FILE", tmp_path / "overrides.json")
    monkeypatch.setattr(store_module, "DATA_FILE", tmp_path / "items.json")
    s = DataStore()
    assert s._read_only is True
    with pytest.raises(RuntimeError):
        s.add_manual_item({"title": "Should Fail"})
