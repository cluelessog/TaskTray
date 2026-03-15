"""Tests for auto-promote: backlog → active on file activity."""
import os
import sys
import time
import pathlib
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def flask_client(tmp_path):
    """Create Flask test client with isolated data directory."""
    import server
    import store as store_module
    original_manual = store_module.MANUAL_FILE
    original_overrides = store_module.OVERRIDES_FILE
    store_module.MANUAL_FILE = tmp_path / "manual_items.json"
    store_module.OVERRIDES_FILE = tmp_path / "overrides.json"
    server.store = store_module.DataStore()
    server.app.config['TESTING'] = True
    with server.app.test_client() as client:
        yield client
    store_module.MANUAL_FILE = original_manual
    store_module.OVERRIDES_FILE = original_overrides

# Activity detection tests
class TestDetectRecentActivity:
    def test_recent_file_returns_true(self, tmp_path):
        """Project dir with recently modified file → True."""
        from scanner import detect_recent_activity
        (tmp_path / "main.py").write_text("code")
        assert detect_recent_activity(tmp_path, threshold_minutes=30) is True

    def test_old_files_returns_false(self, tmp_path):
        """Project dir with files modified 2 hours ago → False."""
        from scanner import detect_recent_activity
        f = tmp_path / "old.py"
        f.write_text("old")
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(f, (old_time, old_time))
        assert detect_recent_activity(tmp_path, threshold_minutes=30) is False

    def test_git_index_recent_returns_true(self, tmp_path):
        """Stale top-level files but recent .git/index → True."""
        from scanner import detect_recent_activity
        f = tmp_path / "old.py"
        f.write_text("old")
        old_time = time.time() - 7200
        os.utime(f, (old_time, old_time))
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "index").write_text("idx")  # just created = recent
        assert detect_recent_activity(tmp_path, threshold_minutes=30) is True

    def test_empty_dir_returns_false(self, tmp_path):
        """Empty directory → False."""
        from scanner import detect_recent_activity
        assert detect_recent_activity(tmp_path, threshold_minutes=30) is False

    def test_permission_error_returns_false(self, tmp_path):
        """Unreadable directory → False, no crash."""
        from scanner import detect_recent_activity
        bad = tmp_path / "noperm"
        bad.mkdir()
        # Use a path that doesn't exist to simulate error
        assert detect_recent_activity(tmp_path / "nonexistent", threshold_minutes=30) is False

    def test_threshold_zero_returns_false(self, tmp_path):
        """Threshold=0 always returns False (feature disabled)."""
        from scanner import detect_recent_activity
        (tmp_path / "new.py").write_text("code")
        assert detect_recent_activity(tmp_path, threshold_minutes=0) is False


# Auto-promote integration tests
class TestAutoPromote:
    def test_backlog_with_activity_becomes_active(self, tmp_path):
        """Item in backlog + has_recent_activity=True → promoted to active."""
        import store as store_module
        store_module.MANUAL_FILE = tmp_path / "manual.json"
        store_module.OVERRIDES_FILE = tmp_path / "overrides.json"
        s = store_module.DataStore()
        # Simulate a disk item in backlog with activity
        disk_item = {"id": "disk_abc", "title": "Test", "source": "disk", "status": "backlog", "has_recent_activity": True}
        s.update_disk_items([disk_item])
        # Auto-promote logic: check backlog + activity + no override
        items = s.get_all_items()
        for item in items:
            if item.get("has_recent_activity") and item.get("status") == "backlog" and item.get("source") == "disk":
                if not s.has_status_override(item["id"]):
                    s.update_item(item["id"], {"status": "active"})
        # Verify promoted
        result = s.get_all_items()
        assert result[0]["status"] == "active"

    def test_skips_when_override_exists(self, tmp_path):
        """Item with manual status override → NOT promoted."""
        import store as store_module
        store_module.MANUAL_FILE = tmp_path / "manual.json"
        store_module.OVERRIDES_FILE = tmp_path / "overrides.json"
        s = store_module.DataStore()
        disk_item = {"id": "disk_def", "title": "Test", "source": "disk", "status": "backlog", "has_recent_activity": True}
        s.update_disk_items([disk_item])
        # User manually set status to paused
        s.update_item("disk_def", {"status": "paused"})
        # Now has_status_override should be True
        assert s.has_status_override("disk_def") is True
        # Auto-promote should skip
        items = s.get_all_items()
        for item in items:
            if item.get("has_recent_activity") and item.get("status") == "backlog" and item.get("source") == "disk":
                if not s.has_status_override(item["id"]):
                    s.update_item(item["id"], {"status": "active"})
        result = s.get_all_items()
        assert result[0]["status"] == "paused"

    def test_skips_when_user_set_backlog(self, tmp_path):
        """User explicitly set status to backlog → NOT promoted even with activity."""
        import store as store_module
        store_module.MANUAL_FILE = tmp_path / "manual.json"
        store_module.OVERRIDES_FILE = tmp_path / "overrides.json"
        s = store_module.DataStore()
        disk_item = {"id": "disk_ghi", "title": "Test", "source": "disk", "status": "backlog", "has_recent_activity": True}
        s.update_disk_items([disk_item])
        # User explicitly sets to backlog (creates override)
        s.update_item("disk_ghi", {"status": "backlog"})
        assert s.has_status_override("disk_ghi") is True
        # Auto-promote should skip
        items = s.get_all_items()
        promoted = 0
        for item in items:
            if item.get("has_recent_activity") and item.get("status") == "backlog" and item.get("source") == "disk":
                if not s.has_status_override(item["id"]):
                    s.update_item(item["id"], {"status": "active"})
                    promoted += 1
        assert promoted == 0
        result = s.get_all_items()
        assert result[0]["status"] == "backlog"

    def test_skips_non_backlog_items(self, tmp_path):
        """Item with status=paused + activity → no change."""
        import store as store_module
        store_module.MANUAL_FILE = tmp_path / "manual.json"
        store_module.OVERRIDES_FILE = tmp_path / "overrides.json"
        s = store_module.DataStore()
        disk_item = {"id": "disk_jkl", "title": "Test", "source": "disk", "status": "active", "has_recent_activity": True}
        s.update_disk_items([disk_item])
        items = s.get_all_items()
        promoted = 0
        for item in items:
            if item.get("has_recent_activity") and item.get("status") == "backlog" and item.get("source") == "disk":
                if not s.has_status_override(item["id"]):
                    s.update_item(item["id"], {"status": "active"})
                    promoted += 1
        assert promoted == 0

    def test_disabled_when_threshold_zero(self, tmp_path):
        """Config threshold=0 → no promotions."""
        from scanner import detect_recent_activity
        (tmp_path / "new.py").write_text("code")
        # With threshold=0, detect_recent_activity returns False
        assert detect_recent_activity(tmp_path, threshold_minutes=0) is False


# ── Git-Recency Auto-Promote Tests (Task 6.3) ───────────────────────────────

from unittest.mock import patch
from datetime import datetime, timedelta


class TestGitRecencyPromote:
    def _run_sync_with_items(self, flask_client, disk_items, config_override=None):
        """Helper: run sync with mocked disk items and git intel."""
        import server as s
        cfg = dict(s.config)
        if config_override:
            for k, v in config_override.items():
                if isinstance(v, dict) and k in cfg:
                    cfg[k] = {**cfg[k], **v}
                else:
                    cfg[k] = v
        original_config = s.config
        s.config = cfg

        # Build git intel results from disk items' git_last_commit
        git_results = {}
        for item in disk_items:
            path = item.get("path", "")
            git_results[path] = {
                "velocity_trend": "steady",
                "total_commits": 10,
                "last_commit_date": item.get("git_last_commit"),
                "stage": "active",
                "commit_types": {},
            }

        with patch("server.scan_for_projects", return_value=disk_items), \
             patch("server.git_intel.analyze_projects", return_value=git_results):
            s.run_sync()
        s.config = original_config

    def test_git_recency_promotes_recent_commit(self, flask_client):
        """Project with git commit 5 days ago, no fs activity, promoted from backlog."""
        recent = (datetime.now() - timedelta(days=5)).isoformat()
        items = [{"id": "disk_r1", "title": "Recent", "path": "/recent", "source": "disk",
                  "status": "backlog", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": recent}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 14}})
        r = flask_client.get("/api/items")
        item = next(i for i in r.get_json() if i["id"] == "disk_r1")
        assert item["status"] == "active"

    def test_git_recency_skips_old_commit(self, flask_client):
        """Project with git commit 20 days ago stays in backlog."""
        old = (datetime.now() - timedelta(days=20)).isoformat()
        items = [{"id": "disk_r2", "title": "Old", "path": "/old", "source": "disk",
                  "status": "backlog", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": old}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 14}})
        r = flask_client.get("/api/items")
        item = next(i for i in r.get_json() if i["id"] == "disk_r2")
        assert item["status"] == "backlog"

    def test_git_recency_respects_override(self, flask_client):
        """User override prevents git-recency promotion."""
        import server as s
        # First set a manual override to paused
        s.store.update_item("disk_r3", {"status": "paused"})
        recent = (datetime.now() - timedelta(days=2)).isoformat()
        items = [{"id": "disk_r3", "title": "Override", "path": "/override", "source": "disk",
                  "status": "backlog", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": recent}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 14}})
        r = flask_client.get("/api/items")
        item = next(i for i in r.get_json() if i["id"] == "disk_r3")
        # Should NOT be promoted — override exists
        assert item["status"] == "paused"

    def test_git_recency_skips_manual_items(self, flask_client):
        """Manual items are not promoted by git recency."""
        import server as s
        s.store.add_manual_item({"id": "manual_r4", "title": "ManualGit", "status": "backlog"})
        recent = (datetime.now() - timedelta(days=1)).isoformat()
        # Even if a manual item had git_last_commit, it shouldn't be promoted
        items = [{"id": "disk_other", "title": "Other", "path": "/other", "source": "disk",
                  "status": "backlog", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": recent}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 14}})
        r = flask_client.get("/api/items")
        manual = next(i for i in r.get_json() if i["id"] == "manual_r4")
        assert manual["status"] == "backlog"

    def test_git_recency_disabled_when_zero(self, flask_client):
        """git_recency_days=0 disables git-based promotion."""
        recent = (datetime.now() - timedelta(days=1)).isoformat()
        items = [{"id": "disk_r5", "title": "Disabled", "path": "/disabled", "source": "disk",
                  "status": "backlog", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": recent}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 0}})
        r = flask_client.get("/api/items")
        item = next(i for i in r.get_json() if i["id"] == "disk_r5")
        assert item["status"] == "backlog"

    def test_git_recency_error_does_not_crash(self, flask_client):
        """Git error (None last_commit) skips promotion gracefully."""
        items = [{"id": "disk_r6", "title": "NoDate", "path": "/nodate", "source": "disk",
                  "status": "backlog", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": None}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 14}})
        r = flask_client.get("/api/items")
        item = next(i for i in r.get_json() if i["id"] == "disk_r6")
        assert item["status"] == "backlog"

    def test_git_recency_does_not_double_promote(self, flask_client):
        """Already-active item is not touched by git-recency promote."""
        recent = (datetime.now() - timedelta(days=1)).isoformat()
        items = [{"id": "disk_r7", "title": "Active", "path": "/active", "source": "disk",
                  "status": "active", "has_recent_activity": False, "is_worktree": False,
                  "git_last_commit": recent}]
        self._run_sync_with_items(flask_client, items, {"scanner": {"git_recency_days": 14}})
        r = flask_client.get("/api/items")
        item = next(i for i in r.get_json() if i["id"] == "disk_r7")
        assert item["status"] == "active"
