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


# ── Endpoint smoke tests ───────────────────────────────────────────────────────

def test_get_items_returns_200(flask_client):
    r = flask_client.get("/api/items")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_get_stats_returns_200(flask_client):
    r = flask_client.get("/api/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert "total" in data
    assert "by_source" in data


def test_delete_item_returns_200(flask_client):
    r = flask_client.delete("/api/items/some_nonexistent_id")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


# ── Health check tests ────────────────────────────────────────────────────────

def test_health_endpoint_returns_200(flask_client):
    r = flask_client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert "last_sync" in data
    assert "item_count" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


def test_health_endpoint_updates_after_sync(flask_client):
    import server as s
    old_sync = s._last_sync_time
    s._last_sync_time = "2026-01-01T00:00:00"
    r = flask_client.get("/api/health")
    assert r.get_json()["last_sync"] == "2026-01-01T00:00:00"
    s._last_sync_time = old_sync


# ── Export endpoint tests ──────────────────────────────────────────────────────

def test_export_json_returns_200(flask_client):
    r = flask_client.get("/api/export?format=json")
    assert r.status_code == 200

def test_export_json_content_type(flask_client):
    r = flask_client.get("/api/export?format=json")
    assert "application/json" in r.content_type

def test_export_json_content_disposition(flask_client):
    r = flask_client.get("/api/export?format=json")
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert ".json" in r.headers.get("Content-Disposition", "")

def test_export_json_excludes_hidden(flask_client):
    r1 = flask_client.post("/api/items", json={"title": "Visible"})
    r2 = flask_client.post("/api/items", json={"title": "Hidden"})
    hidden_id = r2.get_json()["id"]
    flask_client.delete(f"/api/items/{hidden_id}")
    r = flask_client.get("/api/export?format=json")
    data = r.get_json()
    titles = [item["title"] for item in data]
    assert "Visible" in titles
    assert "Hidden" not in titles

def test_export_json_includes_visible(flask_client):
    flask_client.post("/api/items", json={"title": "MyProject"})
    r = flask_client.get("/api/export?format=json")
    data = r.get_json()
    assert any(item["title"] == "MyProject" for item in data)

def test_export_csv_returns_200(flask_client):
    r = flask_client.get("/api/export?format=csv")
    assert r.status_code == 200

def test_export_csv_content_type(flask_client):
    r = flask_client.get("/api/export?format=csv")
    assert "text/csv" in r.content_type

def test_export_csv_has_headers(flask_client):
    r = flask_client.get("/api/export?format=csv")
    first_line = r.data.decode("utf-8").split("\n")[0].strip()
    assert "id" in first_line
    assert "title" in first_line
    assert "status" in first_line
    assert "notes" in first_line

def test_export_csv_excludes_hidden(flask_client):
    flask_client.post("/api/items", json={"title": "CSVVisible"})
    r2 = flask_client.post("/api/items", json={"title": "CSVHidden"})
    flask_client.delete(f"/api/items/{r2.get_json()['id']}")
    r = flask_client.get("/api/export?format=csv")
    body = r.data.decode("utf-8")
    assert "CSVVisible" in body
    assert "CSVHidden" not in body

def test_export_default_format_is_json(flask_client):
    r = flask_client.get("/api/export")
    assert r.status_code == 200
    assert "application/json" in r.content_type

def test_export_invalid_format_returns_400(flask_client):
    r = flask_client.get("/api/export?format=xml")
    assert r.status_code == 400


def test_export_csv_formula_injection_sanitized(flask_client):
    """CSV export sanitizes values that could be interpreted as formulas."""
    flask_client.post("/api/items", json={"title": '=HYPERLINK("http://evil.example","click")'})
    r = flask_client.get("/api/export?format=csv")
    body = r.data.decode("utf-8")
    # The formula-prefix title should be single-quote prefixed, not raw =
    lines = body.strip().split("\n")
    data_lines = [l for l in lines[1:] if l.strip()]
    assert any("'=" in l for l in data_lines), f"Expected formula prefix quoting in CSV: {data_lines}"
    assert not any(l.split(",")[1].startswith('=') for l in data_lines if l.strip())


def test_export_content_disposition_quoted_filename(flask_client):
    """Content-Disposition header has quoted filename per RFC 6266."""
    r = flask_client.get("/api/export?format=json")
    disp = r.headers.get("Content-Disposition", "")
    assert 'filename="tasktray-export-' in disp

    r2 = flask_client.get("/api/export?format=csv")
    disp2 = r2.headers.get("Content-Disposition", "")
    assert 'filename="tasktray-export-' in disp2


def test_index_serves_html(flask_client, tmp_path):
    import server as server_module
    # Point Flask static folder to a temp dir with a fake index.html
    original_static = server_module.app.static_folder
    fake_static = tmp_path / "static"
    fake_static.mkdir()
    (fake_static / "index.html").write_text("<html><body>TaskTray</body></html>")
    server_module.app.static_folder = str(fake_static)
    try:
        r = flask_client.get("/")
        assert r.status_code == 200
    finally:
        server_module.app.static_folder = original_static


# ── API docs endpoint tests ───────────────────────────────────────────────────

def test_api_docs_returns_200(flask_client):
    r = flask_client.get("/api/docs")
    assert r.status_code == 200

def test_api_docs_returns_html(flask_client):
    r = flask_client.get("/api/docs")
    assert "text/html" in r.content_type

def test_api_docs_contains_endpoints(flask_client):
    r = flask_client.get("/api/docs")
    body = r.data.decode("utf-8")
    assert "/api/items" in body
    assert "/api/stats" in body
    assert "/api/sync" in body
    assert "/api/health" in body
    assert "/api/config" in body
    assert "/api/export" in body

def test_api_docs_matches_dark_theme(flask_client):
    r = flask_client.get("/api/docs")
    body = r.data.decode("utf-8")
    # Should use the same dark theme CSS variables
    assert "--bg-root" in body or "#080d14" in body
