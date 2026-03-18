"""Tests for Claude Code status integration — reader, store, and server endpoints."""
import sys
import pathlib

import pytest

# Ensure project root is importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


# ── CCStatusReader unit tests ────────────────────────────────────────────────

class TestCCStatusReader:
    def test_reader_initializes_with_config(self):
        from cc_status_reader import CCStatusReader
        reader = CCStatusReader({"claude_code": {"projects": []}})
        assert reader is not None

    def test_read_all_returns_list(self):
        from cc_status_reader import CCStatusReader
        reader = CCStatusReader({"claude_code": {"projects": []}})
        result = reader.read_all()
        assert isinstance(result, list)

    def test_get_summary_returns_expected_keys(self):
        from cc_status_reader import CCStatusReader
        reader = CCStatusReader({"claude_code": {"projects": []}})
        summary = reader.get_summary()
        assert "total" in summary
        assert "on_track" in summary
        assert "blocked" in summary
        assert "all_blockers" in summary
        assert "active_work" in summary

    def test_handles_missing_project_path(self):
        from cc_status_reader import CCStatusReader
        reader = CCStatusReader({"claude_code": {"projects": [
            {"name": "NonExistent", "path": "/tmp/does-not-exist-xyz"}
        ]}})
        items = reader.read_all()
        assert len(items) == 1
        assert items[0]["cc"]["error"] is not None

    def test_read_project_with_real_status(self):
        """Read TaskTray's own docs/STATUS.md as a real integration test."""
        from cc_status_reader import CCStatusReader
        project_root = str(pathlib.Path(__file__).resolve().parent.parent)
        reader = CCStatusReader({"claude_code": {"projects": [
            {"name": "TaskTray", "path": project_root, "category": "dev"}
        ]}})
        items = reader.read_all()
        assert len(items) == 1
        item = items[0]
        assert item["title"] == "TaskTray"
        assert item["source"] == "claude_code"
        assert "cc" in item
        assert item["cc"]["phase"] != "unknown"  # STATUS.md has a phase

    def test_windows_path_normalized_on_wsl(self):
        """Windows paths like D:/Projects/X should resolve to /mnt/d/Projects/X on WSL."""
        from cc_status_reader import CCStatusReader
        project_root = str(pathlib.Path(__file__).resolve().parent.parent)
        # Use Windows-style path pointing to the same directory
        win_path = project_root.replace("/mnt/d/", "D:/")
        reader = CCStatusReader({"claude_code": {"projects": [
            {"name": "TaskTray", "path": win_path, "category": "dev"}
        ]}})
        items = reader.read_all()
        assert len(items) == 1
        item = items[0]
        # Should find the STATUS.md despite Windows path
        assert item["cc"]["phase"] != "unknown", \
            f"Windows path '{win_path}' was not normalized — phase is 'unknown'"
        assert item["cc"]["error"] is None

    def test_read_project_by_name(self):
        """read_project_by_name returns the right project or None."""
        from cc_status_reader import CCStatusReader
        project_root = str(pathlib.Path(__file__).resolve().parent.parent)
        reader = CCStatusReader({"claude_code": {"projects": [
            {"name": "TaskTray", "path": project_root, "category": "dev"}
        ]}})
        item = reader.read_project_by_name("TaskTray")
        assert item is not None
        assert item["title"] == "TaskTray"
        # Non-existent project returns None
        assert reader.read_project_by_name("NoSuchProject") is None

    def test_parse_milestones_table_returns_list(self, tmp_path):
        """_parse_plan_md returns a 'milestones' key with a list."""
        from cc_status_reader import CCStatusReader
        plan = tmp_path / "PLAN.md"
        plan.write_text(
            "## Milestones\n\n"
            "| # | Milestone | Status |\n"
            "|---|-----------|--------|\n"
            "| 1 | Core: Disk scanner + Flask server | completed |\n"
            "| 2 | Phase 1: Critical Stability | in_progress |\n"
        )
        reader = CCStatusReader({"claude_code": {"projects": []}})
        result = reader._parse_plan_md(plan)
        assert "milestones" in result
        assert isinstance(result["milestones"], list)

    def test_parse_milestones_table_extracts_fields(self, tmp_path):
        """Each milestone dict has number, name, and status."""
        from cc_status_reader import CCStatusReader
        plan = tmp_path / "PLAN.md"
        plan.write_text(
            "## Milestones\n\n"
            "| # | Milestone | Status |\n"
            "|---|-----------|--------|\n"
            "| 1 | Core: Disk scanner + Flask server | completed |\n"
            "| 2 | Phase 1: Critical Stability | in_progress |\n"
        )
        reader = CCStatusReader({"claude_code": {"projects": []}})
        milestones = reader._parse_plan_md(plan)["milestones"]
        assert len(milestones) == 2
        assert milestones[0] == {"number": 1, "name": "Core: Disk scanner + Flask server", "status": "completed"}
        assert milestones[1] == {"number": 2, "name": "Phase 1: Critical Stability", "status": "in_progress"}

    def test_parse_milestones_table_empty_when_absent(self, tmp_path):
        """Returns empty list when no milestones table in PLAN.md."""
        from cc_status_reader import CCStatusReader
        plan = tmp_path / "PLAN.md"
        plan.write_text("## Objective\n\nJust an objective.\n")
        reader = CCStatusReader({"claude_code": {"projects": []}})
        result = reader._parse_plan_md(plan)
        assert result["milestones"] == []

    def test_milestones_stored_in_cc_item(self):
        """read_project includes milestones in item['cc']['milestones']."""
        from cc_status_reader import CCStatusReader
        project_root = str(pathlib.Path(__file__).resolve().parent.parent)
        reader = CCStatusReader({"claude_code": {"projects": [
            {"name": "TaskTray", "path": project_root, "category": "dev"}
        ]}})
        item = reader.read_project_by_name("TaskTray")
        assert item is not None
        assert "milestones" in item["cc"]
        assert isinstance(item["cc"]["milestones"], list)
        # TaskTray's own PLAN.md has milestones
        assert len(item["cc"]["milestones"]) > 0
        # Each has number, name, status
        m = item["cc"]["milestones"][0]
        assert "number" in m
        assert "name" in m
        assert "status" in m


# ── Store integration tests ──────────────────────────────────────────────────

class TestCCStoreIntegration:
    def test_store_has_update_cc_items(self):
        from store import DataStore
        ds = DataStore()
        assert hasattr(ds, "update_cc_items")

    def test_cc_items_appear_in_get_all(self):
        from store import DataStore
        ds = DataStore()
        ds.update_cc_items([{
            "id": "cc_test1",
            "title": "TestProject",
            "path": "/tmp/test-cc-project",
            "source": "claude_code",
            "status": "active",
            "cc": {"phase": "implementation"},
        }])
        items = ds.get_all_items()
        cc_items = [i for i in items if i.get("source") == "claude_code"]
        assert len(cc_items) >= 1

    def test_cc_merges_with_disk_by_path(self):
        from store import DataStore
        ds = DataStore()
        ds.update_disk_items([{
            "id": "disk_abc",
            "title": "MyProject",
            "path": "/projects/MyProject",
            "source": "disk",
            "status": "active",
            "git_velocity_trend": "steady",
            "git_commit_count": 42,
        }])
        ds.update_cc_items([{
            "id": "cc_abc",
            "title": "MyProject",
            "path": "/projects/MyProject",
            "source": "claude_code",
            "status": "active",
            "cc": {"phase": "implementation", "health": "on-track"},
        }])
        items = ds.get_all_items()
        # Should be ONE item, not two
        my_items = [i for i in items if i.get("path") == "/projects/MyProject"]
        assert len(my_items) == 1
        merged = my_items[0]
        # Has both git and cc data
        assert merged.get("git_velocity_trend") == "steady"
        assert merged.get("cc", {}).get("phase") == "implementation"

    def test_stats_include_claude_code_source(self):
        from store import DataStore
        ds = DataStore()
        ds.update_cc_items([{
            "id": "cc_stat1",
            "title": "StatProject",
            "path": "/tmp/stat-project",
            "source": "claude_code",
            "status": "active",
            "cc": {},
        }])
        stats = ds.get_stats()
        assert "claude_code" in stats.get("by_source", {})


# ── Server endpoint tests ───────────────────────────────────────────────────

class TestCCServerEndpoints:
    @pytest.fixture
    def flask_client(self):
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_cc_status_endpoint(self, flask_client):
        resp = flask_client.get("/api/cc-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_cc_summary_endpoint(self, flask_client):
        resp = flask_client.get("/api/cc-summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data
        assert "on_track" in data
        assert "blocked" in data

    def test_cc_project_not_found(self, flask_client):
        resp = flask_client.get("/api/cc-status/nonexistent-project-xyz")
        assert resp.status_code == 404
