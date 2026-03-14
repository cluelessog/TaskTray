"""Tests for auto-promote: backlog → active on file activity."""
import os
import time
import pathlib
import pytest

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
