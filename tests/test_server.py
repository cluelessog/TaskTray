"""Tests for server.py."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock


def test_webbrowser_available_at_module_level():
    """webbrowser must be importable from server module scope."""
    import importlib
    import server
    # webbrowser should be in server's global namespace after module-level import
    assert 'webbrowser' in dir(server) or hasattr(server, 'webbrowser')


def test_log_handler_is_rotating():
    """Log handler must be RotatingFileHandler, not plain FileHandler."""
    import logging
    from logging.handlers import RotatingFileHandler
    import server  # triggers logging setup
    log = logging.getLogger("tasktray")
    rotating = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) >= 1, f"Expected RotatingFileHandler, got: {[type(h).__name__ for h in log.handlers]}"


def test_rotating_handler_config():
    """RotatingFileHandler must have 5MB limit and 3 backups."""
    import logging
    from logging.handlers import RotatingFileHandler
    import server
    log = logging.getLogger("tasktray")
    handler = next(h for h in log.handlers if isinstance(h, RotatingFileHandler))
    assert handler.maxBytes == 5 * 1024 * 1024, f"Expected 5MB, got {handler.maxBytes}"
    assert handler.backupCount == 3, f"Expected 3 backups, got {handler.backupCount}"


# ── API Validation Tests ──────────────────────────────────

@pytest.fixture
def flask_client(tmp_path):
    """Create Flask test client with isolated data directory."""
    import server
    import store as store_module
    # Patch store data paths to use tmp directory
    original_manual = store_module.MANUAL_FILE
    original_overrides = store_module.OVERRIDES_FILE
    store_module.MANUAL_FILE = tmp_path / "manual_items.json"
    store_module.OVERRIDES_FILE = tmp_path / "overrides.json"
    store_module.DATA_DIR = tmp_path
    # Create fresh store
    server.store = store_module.DataStore()
    server.app.config['TESTING'] = True
    with server.app.test_client() as client:
        yield client
    # Restore
    store_module.MANUAL_FILE = original_manual
    store_module.OVERRIDES_FILE = original_overrides

def test_post_item_valid(flask_client):
    r = flask_client.post("/api/items", json={"title": "Test", "status": "active", "priority": "p1"})
    assert r.status_code == 201

def test_post_item_missing_title(flask_client):
    r = flask_client.post("/api/items", json={"status": "active"})
    assert r.status_code == 400
    assert "Title" in r.get_json()["error"] or "title" in r.get_json()["error"].lower()

def test_post_item_invalid_status(flask_client):
    r = flask_client.post("/api/items", json={"title": "X", "status": "invalid"})
    assert r.status_code == 400
    assert "status" in r.get_json()["error"].lower()

def test_post_item_invalid_priority(flask_client):
    r = flask_client.post("/api/items", json={"title": "X", "priority": "high"})
    assert r.status_code == 400
    assert "priority" in r.get_json()["error"].lower()

def test_post_item_title_too_long(flask_client):
    r = flask_client.post("/api/items", json={"title": "A" * 201})
    assert r.status_code == 400

def test_post_item_notes_too_long(flask_client):
    r = flask_client.post("/api/items", json={"title": "X", "notes": "A" * 2001})
    assert r.status_code == 400

def test_post_item_unknown_fields_stripped(flask_client):
    r = flask_client.post("/api/items", json={"title": "X", "evil_field": "hack"})
    assert r.status_code == 201
    assert "evil_field" not in r.get_json()

def test_patch_item_valid(flask_client):
    r1 = flask_client.post("/api/items", json={"title": "X"})
    item_id = r1.get_json()["id"]
    r2 = flask_client.patch(f"/api/items/{item_id}", json={"status": "done"})
    assert r2.status_code == 200

def test_patch_item_invalid_status(flask_client):
    r1 = flask_client.post("/api/items", json={"title": "X"})
    item_id = r1.get_json()["id"]
    r2 = flask_client.patch(f"/api/items/{item_id}", json={"status": "invalid"})
    assert r2.status_code == 400

def test_patch_item_empty_after_filter(flask_client):
    r1 = flask_client.post("/api/items", json={"title": "X"})
    item_id = r1.get_json()["id"]
    r2 = flask_client.patch(f"/api/items/{item_id}", json={"unknown_only": "val"})
    assert r2.status_code == 400
