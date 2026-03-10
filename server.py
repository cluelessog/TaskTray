"""
TaskTray — Main Server
Flask API + System Tray + Background Sync

Run: python server.py
"""

import json
import time
import webbrowser
import threading
import logging
import yaml
import sys
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from scanner import scan_for_projects
from obsidian_reader import read_obsidian_items
from store import DataStore

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tasktray")

# ── Config ───────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

config = load_config()

# ── Data Store ───────────────────────────────────────────
store = DataStore()

# ── Flask App ────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/items", methods=["GET"])
def get_items():
    """Get all dashboard items."""
    return jsonify(store.get_all_items_filtered())


@app.route("/api/items", methods=["POST"])
def add_item():
    """Add a manual item."""
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "Title is required"}), 400
    item = store.add_manual_item(data)
    return jsonify(item), 201


@app.route("/api/items/<item_id>", methods=["PATCH"])
def update_item(item_id):
    """Update an item (manual or override)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    result = store.update_item(item_id, data)
    return jsonify(result)


@app.route("/api/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    """Delete/hide an item."""
    store.delete_item(item_id)
    return jsonify({"ok": True})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get dashboard stats."""
    return jsonify(store.get_stats())


@app.route("/api/sync", methods=["POST"])
def trigger_sync():
    """Manually trigger a full sync."""
    run_sync()
    return jsonify({"ok": True, "stats": store.get_stats()})


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current config (sanitized)."""
    return jsonify({
        "scan_dirs": config.get("scanner", {}).get("scan_dirs", []),
        "vault_path": config.get("obsidian", {}).get("vault_path", ""),
        "categories": config.get("categories", {}),
    })


# ── Sync Logic ───────────────────────────────────────────

def run_sync():
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


def background_sync(interval_seconds=30):
    """Background thread that periodically syncs."""
    while True:
        try:
            run_sync()
        except Exception as e:
            log.error(f"Background sync error: {e}")
        time.sleep(interval_seconds)


# ── System Tray ──────────────────────────────────────────

def run_tray():
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


# ── Main ─────────────────────────────────────────────────

def main():
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 9876)

    # Initial sync
    run_sync()

    # Start background sync thread
    watch_interval = config.get("obsidian", {}).get("watch_interval_seconds", 30)
    sync_thread = threading.Thread(target=background_sync, args=(watch_interval,), daemon=True)
    sync_thread.start()

    # Start Flask in a background thread (so main thread is free for tray)
    flask_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    log.info(f"Dashboard running at http://{host}:{port}")
    log.info("System tray icon active — double-click to open")

    # Open browser on first run
    webbrowser.open(f"http://{host}:{port}")

    # Run system tray on main thread (required on Windows for Win32 message pump)
    run_tray()


if __name__ == "__main__":
    main()
