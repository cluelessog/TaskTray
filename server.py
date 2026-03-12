"""
TaskTray — Main Server
Flask API + System Tray + Background Sync

Run: python server.py
"""
from __future__ import annotations

import json
import time
import socket
import atexit
import threading
import logging
from logging.handlers import RotatingFileHandler
from typing import Any
import yaml
import sys
import webbrowser
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from scanner import scan_for_projects
from obsidian_reader import read_obsidian_items
from store import DataStore

try:
    import webview
    _HAS_WEBVIEW = True
except ImportError:
    _HAS_WEBVIEW = False
    # log is not yet configured here; warning is deferred to main()

# ── Logging ──────────────────────────────────────────────
_log_dir = Path(__file__).parent / "data"
_log_dir.mkdir(parents=True, exist_ok=True)

_log_fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
)

log = logging.getLogger("tasktray")
log.setLevel(logging.INFO)

_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(_log_fmt)
log.addHandler(_stream_handler)

_file_handler = RotatingFileHandler(
    _log_dir / "tasktray.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(_log_fmt)
log.addHandler(_file_handler)

# ── Config ───────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

config = load_config()

# ── Window State ─────────────────────────────────────────
_webview_window: "webview.Window | None" = None  # type: ignore[name-defined]
_is_quitting: bool = False

# ── Data Store ───────────────────────────────────────────
store = DataStore()

# ── Flask App ────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)

VALID_STATUSES = {"active", "paused", "backlog", "done"}
VALID_PRIORITIES = {"p0", "p1", "p2", "p3"}
ALLOWED_ITEM_FIELDS = {"title", "category", "status", "priority", "notes", "focused"}
MAX_TITLE_LENGTH = 200
MAX_NOTES_LENGTH = 2000


def _validate_item_fields(data: dict, require_title: bool = False) -> tuple[dict | None, str | None]:
    """Validate and filter item fields. Returns (filtered_data, error_message)."""
    if require_title and not data.get("title"):
        return None, "Title is required"
    filtered = {k: v for k, v in data.items() if k in ALLOWED_ITEM_FIELDS}
    if "title" in filtered:
        if not isinstance(filtered["title"], str) or len(filtered["title"]) > MAX_TITLE_LENGTH:
            return None, f"Title must be a string of max {MAX_TITLE_LENGTH} characters"
    if "notes" in filtered:
        if not isinstance(filtered["notes"], str) or len(filtered["notes"]) > MAX_NOTES_LENGTH:
            return None, f"Notes must be a string of max {MAX_NOTES_LENGTH} characters"
    if "status" in filtered and filtered["status"] not in VALID_STATUSES:
        return None, f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
    if "priority" in filtered and filtered["priority"] not in VALID_PRIORITIES:
        return None, f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
    if "focused" in filtered:
        filtered["focused"] = bool(filtered["focused"])
    return filtered, None


@app.route("/")
def index() -> Any:
    return send_from_directory("static", "index.html")


@app.route("/api/items", methods=["GET"])
def get_items() -> Any:
    """Get all dashboard items."""
    return jsonify(store.get_all_items_filtered())


@app.route("/api/items", methods=["POST"])
def add_item() -> Any:
    """Add a manual item."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    filtered, error = _validate_item_fields(data, require_title=True)
    if error or filtered is None:
        return jsonify({"error": error or "Invalid data"}), 400
    item = store.add_manual_item(filtered)
    return jsonify(item), 201


@app.route("/api/items/<item_id>", methods=["PATCH"])
def update_item(item_id: str) -> Any:
    """Update an item (manual or override)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    filtered, error = _validate_item_fields(data, require_title=False)
    if error:
        return jsonify({"error": error}), 400
    if not filtered:
        return jsonify({"error": "No valid fields provided"}), 400
    result = store.update_item(item_id, filtered)
    return jsonify(result)


@app.route("/api/items/<item_id>", methods=["DELETE"])
def delete_item(item_id: str) -> Any:
    """Delete/hide an item."""
    store.delete_item(item_id)
    return jsonify({"ok": True})


@app.route("/api/stats", methods=["GET"])
def get_stats() -> Any:
    """Get dashboard stats."""
    return jsonify(store.get_stats())


@app.route("/api/sync", methods=["POST"])
def trigger_sync() -> Any:
    """Manually trigger a full sync."""
    run_sync()
    return jsonify({"ok": True, "stats": store.get_stats()})


@app.route("/api/config", methods=["GET"])
def get_config() -> Any:
    """Get current config (sanitized)."""
    return jsonify({
        "scan_dirs": config.get("scanner", {}).get("scan_dirs", []),
        "vault_path": config.get("obsidian", {}).get("vault_path", ""),
        "categories": config.get("categories", {}),
    })


# ── Sync Logic ───────────────────────────────────────────

def run_sync() -> None:
    """Run disk scan + obsidian read."""
    log.info("Syncing...")
    t0 = time.time()

    # Scan disk
    try:
        disk_items = scan_for_projects(config)
        store.update_disk_items(disk_items)
        log.info(f"  Disk: found {len(disk_items)} projects")
    except Exception as e:
        log.error(f"  Disk scan failed: {e}")

    # Read Obsidian
    try:
        obs_items = read_obsidian_items(config)
        store.update_obsidian_items(obs_items)
        log.info(f"  Obsidian: found {len(obs_items)} items")
    except Exception as e:
        log.error(f"  Obsidian read failed: {e}")

    elapsed = time.time() - t0
    log.info(f"  Sync complete in {elapsed:.1f}s — {store.get_stats()['total']} total items")


def background_sync(interval_seconds: int = 30) -> None:
    """Background thread that periodically syncs."""
    while True:
        try:
            run_sync()
        except Exception as e:
            log.error(f"Background sync error: {e}")
        time.sleep(interval_seconds)


def _wait_for_flask(host: str, port: int, timeout: float = 5.0) -> bool:
    """Block until Flask is accepting TCP connections, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                log.info("Flask ready on %s:%d", host, port)
                return True
        finally:
            sock.close()
        time.sleep(0.05)
    log.warning("Flask did not become ready within %.1fs", timeout)
    return False


# ── System Tray ──────────────────────────────────────────

def run_tray() -> None:
    """Run system tray icon (Windows)."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        log.warning("pystray/Pillow not installed — skipping system tray. Install with: pip install pystray Pillow")
        return

    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 9876)
    url = f"http://{host}:{port}"

    # Create a simple icon
    def create_icon():
        img = Image.new("RGBA", (64, 64), (11, 17, 32, 255))
        draw = ImageDraw.Draw(img)
        # Draw a diamond shape
        draw.polygon([(32, 4), (60, 32), (32, 60), (4, 32)], fill=(34, 211, 238, 255))
        draw.polygon([(32, 14), (50, 32), (32, 50), (14, 32)], fill=(11, 17, 32, 255))
        return img

    def on_open(icon, item):
        webbrowser.open(url)

    def on_sync(icon, item):
        run_sync()

    def on_quit(icon, item):
        icon.stop()
        log.info("Tray icon stopped. Server still running — press Ctrl+C to exit.")
        sys.exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open, default=True),
        pystray.MenuItem("Sync Now", on_sync),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon("tasktray", create_icon(), "TaskTray", menu)
    log.info("System tray icon ready — double-click to open dashboard")
    icon.run()


# ── Native Window Handlers ───────────────────────────────

def _on_window_closing() -> bool:
    """Intercept window close. Hide to tray unless quitting.

    IMPORTANT: pywebview checks `return_value is False` (identity check).
    Must return the literal `False`, not a falsy value.
    This handler is synchronous -- do NOT perform expensive work here.
    """
    if _is_quitting:
        return True
    if _webview_window is not None:
        _webview_window.hide()
    return False  # Prevent window destruction


def _run_tray_detached() -> None:
    """Run system tray icon via run_detached() for native window mode."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        log.warning("pystray/Pillow not installed — skipping system tray.")
        return

    def create_icon():
        img = Image.new("RGBA", (64, 64), (11, 17, 32, 255))
        draw = ImageDraw.Draw(img)
        draw.polygon([(32, 4), (60, 32), (32, 60), (4, 32)], fill=(34, 211, 238, 255))
        draw.polygon([(32, 14), (50, 32), (32, 50), (14, 32)], fill=(11, 17, 32, 255))
        return img

    def on_open(icon, item):
        if _webview_window is not None:
            _webview_window.show()

    def on_sync(icon, item):
        run_sync()

    def on_quit(icon, item):
        global _is_quitting
        _is_quitting = True
        if _webview_window is not None:
            _webview_window.destroy()
        icon.stop()
        # Process exits naturally when webview.start() returns after window destruction

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", on_open, default=True),
        pystray.MenuItem("Sync Now", on_sync),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon("tasktray", create_icon(), "TaskTray", menu)
    log.info("System tray icon ready")

    # Register cleanup for unexpected exits
    atexit.register(lambda: icon.stop())

    icon.run_detached()


def _start_services(window: Any) -> None:
    """Called by webview.start() on a background thread.
    Launches Flask, background sync, and pystray.
    """
    global _webview_window
    _webview_window = window

    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 9876)

    # Initial sync
    run_sync()

    # Start background sync thread
    watch_interval = config.get("obsidian", {}).get("watch_interval_seconds", 30)
    sync_thread = threading.Thread(target=background_sync, args=(watch_interval,), daemon=True)
    sync_thread.start()

    # Start Flask in a background thread
    flask_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    log.info("Dashboard running at http://%s:%d", host, port)

    # Wait for Flask to be ready before the window loads
    _wait_for_flask(host, port)

    # Start system tray (detached -- runs its own message loop)
    _run_tray_detached()


# ── Main ─────────────────────────────────────────────────

def main() -> None:
    if not _HAS_WEBVIEW:
        log.warning("pywebview not installed — will open in browser. Install with: pip install pywebview")

    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 9876)
    url = f"http://{host}:{port}"

    if _HAS_WEBVIEW:
        # ── Native window mode ──
        window = webview.create_window(
            "TaskTray",
            url,
            width=1200,
            height=800,
        )
        assert window is not None, "webview.create_window() returned None"
        # Wire closing event via window.events (not a create_window kwarg)
        window.events.closing += _on_window_closing
        webview.start(func=_start_services, args=(window,))
    else:
        # ── Fallback: browser mode (current behavior) ──
        run_sync()
        watch_interval = config.get("obsidian", {}).get("watch_interval_seconds", 30)
        sync_thread = threading.Thread(target=background_sync, args=(watch_interval,), daemon=True)
        sync_thread.start()
        flask_thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
            daemon=True,
        )
        flask_thread.start()
        log.info("Dashboard running at http://%s:%d", host, port)
        webbrowser.open(url)
        run_tray()  # pystray on main thread (original behavior)


if __name__ == "__main__":
    main()
