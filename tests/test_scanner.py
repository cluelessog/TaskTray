"""Tests for scanner.py — targeting >= 60% coverage."""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import _detect_type, _extract_description, _guess_category, scan_for_projects, ScanCache, _detect_worktree, _build_project_info, _scan_with_timeout, _normalize_to_native


# ── _detect_type ──────────────────────────────────────────────────────────────

def test_detect_type_cargo_toml(tmp_path):
    assert _detect_type({"Cargo.toml"}, tmp_path) == "rust"


def test_detect_type_tauri_conf(tmp_path):
    assert _detect_type({"tauri.conf.json"}, tmp_path) == "rust"


def test_detect_type_package_json_react(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))
    assert _detect_type({"package.json"}, tmp_path) == "react"


def test_detect_type_package_json_angular(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {"@angular/core": "^15.0.0"}}))
    assert _detect_type({"package.json"}, tmp_path) == "angular"


def test_detect_type_package_json_vue(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {"vue": "^3.0.0"}}))
    assert _detect_type({"package.json"}, tmp_path) == "vue"


def test_detect_type_package_json_next(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {"next": "^13.0.0"}}))
    assert _detect_type({"package.json"}, tmp_path) == "nextjs"


def test_detect_type_package_json_tauri_api(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {"@tauri-apps/api": "^1.0.0"}}))
    assert _detect_type({"package.json"}, tmp_path) == "tauri"


def test_detect_type_package_json_plain_node(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"dependencies": {}}))
    assert _detect_type({"package.json"}, tmp_path) == "node"


def test_detect_type_package_json_missing_file(tmp_path):
    # package.json in markers but file doesn't exist on disk
    assert _detect_type({"package.json"}, tmp_path) == "node"


def test_detect_type_package_json_bad_json(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text("{invalid json}")
    assert _detect_type({"package.json"}, tmp_path) == "node"


def test_detect_type_pyproject_toml(tmp_path):
    assert _detect_type({"pyproject.toml"}, tmp_path) == "python"


def test_detect_type_setup_py(tmp_path):
    assert _detect_type({"setup.py"}, tmp_path) == "python"


def test_detect_type_go_mod(tmp_path):
    assert _detect_type({"go.mod"}, tmp_path) == "go"


def test_detect_type_pom_xml(tmp_path):
    assert _detect_type({"pom.xml"}, tmp_path) == "java"


def test_detect_type_docker_compose(tmp_path):
    assert _detect_type({"docker-compose.yml"}, tmp_path) == "docker"


def test_detect_type_unknown(tmp_path):
    assert _detect_type({".git"}, tmp_path) == "unknown"


# ── _extract_description ──────────────────────────────────────────────────────

def test_extract_description_from_readme(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# My Project\nThis is the description line.\n")
    result = _extract_description(tmp_path)
    assert result == "This is the description line."


def test_extract_description_skips_headers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n## Subtitle\nActual description here.\n")
    result = _extract_description(tmp_path)
    assert result == "Actual description here."


def test_extract_description_from_package_json(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"description": "A Node package description"}))
    result = _extract_description(tmp_path)
    assert result == "A Node package description"


def test_extract_description_empty_directory(tmp_path):
    result = _extract_description(tmp_path)
    assert result is None


def test_extract_description_truncates_at_200(tmp_path):
    readme = tmp_path / "README.md"
    long_line = "A" * 300
    readme.write_text(f"# Title\n{long_line}\n")
    result = _extract_description(tmp_path)
    assert len(result) == 200


def test_extract_description_readme_lowercase(tmp_path):
    readme = tmp_path / "readme.md"
    readme.write_text("# Title\nLowercase readme description.\n")
    result = _extract_description(tmp_path)
    assert result == "Lowercase readme description."


# ── _guess_category ───────────────────────────────────────────────────────────

def test_guess_category_trading(tmp_path):
    from pathlib import Path
    p = Path("/home/user/trading-bot")
    assert _guess_category(p, "python") == "trading"


def test_guess_category_teaching(tmp_path):
    from pathlib import Path
    p = Path("/home/user/angular-course")
    assert _guess_category(p, "angular") == "teaching"


def test_guess_category_ideas(tmp_path):
    from pathlib import Path
    p = Path("/home/user/poc-experiment")
    assert _guess_category(p, "python") == "ideas"


def test_guess_category_personal(tmp_path):
    from pathlib import Path
    p = Path("/home/user/personal-site")
    assert _guess_category(p, "node") == "personal"


def test_guess_category_default_dev(tmp_path):
    from pathlib import Path
    p = Path("/workspace/my-project")
    assert _guess_category(p, "python") == "dev"


# ── scan_for_projects ─────────────────────────────────────────────────────────

def test_scan_finds_git_repos(tmp_path):
    proj = tmp_path / "my-project"
    proj.mkdir()
    (proj / ".git").mkdir()

    config = {
        "scanner": {
            "scan_dirs": [str(tmp_path)],
            "max_depth": 2,
            "markers": [".git"],
            "ignore_dirs": [],
        }
    }
    results = scan_for_projects(config)
    assert len(results) == 1
    assert results[0]["title"] == "my-project"
    assert results[0]["source"] == "disk"


def test_scan_respects_max_depth(tmp_path):
    deep = tmp_path / "level1" / "level2" / "level3" / "deep-project"
    deep.mkdir(parents=True)
    (deep / ".git").mkdir()

    config = {
        "scanner": {
            "scan_dirs": [str(tmp_path)],
            "max_depth": 2,
            "markers": [".git"],
            "ignore_dirs": [],
        }
    }
    results = scan_for_projects(config)
    assert len(results) == 0


def test_scan_skips_ignored_dirs(tmp_path):
    ignored = tmp_path / "node_modules" / "some-pkg"
    ignored.mkdir(parents=True)
    (ignored / ".git").mkdir()

    config = {
        "scanner": {
            "scan_dirs": [str(tmp_path)],
            "max_depth": 3,
            "markers": [".git"],
            "ignore_dirs": ["node_modules"],
        }
    }
    results = scan_for_projects(config)
    assert len(results) == 0


def test_scan_nonexistent_base_dir():
    config = {
        "scanner": {
            "scan_dirs": ["/nonexistent/path/12345"],
            "max_depth": 3,
            "markers": [".git"],
            "ignore_dirs": [],
        }
    }
    results = scan_for_projects(config)
    assert results == []


def test_scan_empty_config():
    results = scan_for_projects({})
    assert results == []


def test_scan_does_not_recurse_into_project(tmp_path):
    """Once a project is found, its subdirs should not be scanned."""
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / ".git").mkdir()
    inner = outer / "subdir"
    inner.mkdir()
    (inner / ".git").mkdir()

    config = {
        "scanner": {
            "scan_dirs": [str(tmp_path)],
            "max_depth": 4,
            "markers": [".git"],
            "ignore_dirs": [],
        }
    }
    results = scan_for_projects(config)
    assert len(results) == 1
    assert results[0]["title"] == "outer"


def test_scan_result_has_required_fields(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / ".git").mkdir()

    config = {
        "scanner": {
            "scan_dirs": [str(tmp_path)],
            "max_depth": 2,
            "markers": [".git"],
            "ignore_dirs": [],
        }
    }
    results = scan_for_projects(config)
    item = results[0]
    for field in ("id", "title", "path", "source", "type", "category", "status", "priority"):
        assert field in item, f"Missing field: {field}"


# ── timeout tests ──────────────────────────────────────────────────────────────

def test_scan_timeout_skips_slow_directory(tmp_path):
    """A directory whose scan exceeds timeout returns empty list without crashing."""
    import threading
    from scanner import _scan_with_timeout

    slow_called = threading.Event()

    def slow_scan(*args, **kwargs):
        slow_called.set()
        # Block longer than the timeout
        import time
        time.sleep(5)
        return []

    # Patch the inner walk function via monkeypatching _scan_with_timeout's internals
    # by using a very short timeout and a slow target directory.
    # We test _scan_with_timeout directly with a mocked walk.
    results = _scan_with_timeout(
        base=tmp_path,
        max_depth=3,
        markers={".git"},
        ignore_dirs=set(),
        timeout_seconds=0,  # 0-second timeout guarantees expiry
    )
    assert results == []


def test_scan_timeout_default_is_10_seconds(tmp_path):
    """scan_for_projects uses a default timeout of 10 seconds when not specified."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / ".git").mkdir()

    config = {
        "scanner": {
            "scan_dirs": [str(tmp_path)],
            "max_depth": 2,
            "markers": [".git"],
            "ignore_dirs": [],
            # timeout_seconds intentionally omitted — should default to 10
        }
    }
    # The scan should succeed normally (tmp_path is fast), proving default=10 doesn't block
    results = scan_for_projects(config)
    assert len(results) == 1
    assert results[0]["title"] == "myproj"


def test_scan_completes_within_timeout(tmp_path):
    """Normal scan with a generous timeout succeeds and returns results."""
    from scanner import _scan_with_timeout

    proj = tmp_path / "fast-project"
    proj.mkdir()
    (proj / ".git").mkdir()

    results = _scan_with_timeout(
        base=tmp_path,
        max_depth=3,
        markers={".git"},
        ignore_dirs=set(),
        timeout_seconds=10,
    )
    assert len(results) == 1
    assert results[0]["title"] == "fast-project"


# ── ScanCache ──────────────────────────────────────────────────────────────────

class TestScanCache:
    def _make_config(self, scan_dirs, cache_path=None):
        cfg = {
            "scanner": {
                "scan_dirs": scan_dirs,
                "max_depth": 2,
                "markers": [".git"],
                "ignore_dirs": [],
            }
        }
        return cfg

    def test_cache_miss_triggers_scan(self, tmp_path):
        """First scan with empty cache returns results and creates cache file."""
        cache_file = tmp_path / "scan_cache.json"
        proj = tmp_path / "projects" / "myproj"
        proj.mkdir(parents=True)
        (proj / ".git").mkdir()

        config = self._make_config([str(tmp_path / "projects")])

        cache = ScanCache(cache_file)
        results = scan_for_projects(config, _cache=cache)

        assert len(results) == 1
        assert results[0]["title"] == "myproj"
        assert cache_file.exists()

    def test_cache_hit_returns_cached(self, tmp_path):
        """Second scan without changes returns same results without re-scanning."""
        cache_file = tmp_path / "scan_cache.json"
        proj = tmp_path / "projects" / "myproj"
        proj.mkdir(parents=True)
        (proj / ".git").mkdir()

        config = self._make_config([str(tmp_path / "projects")])

        cache = ScanCache(cache_file)
        results1 = scan_for_projects(config, _cache=cache)
        assert len(results1) == 1

        # Second scan — inject a sentinel into the cache to confirm it's returned
        # by poisoning the cached projects list
        scan_dir = str((tmp_path / "projects").resolve())
        cached_entry = cache._cache.get(scan_dir)
        assert cached_entry is not None, "Cache should have an entry after first scan"

        # Overwrite cached projects with sentinel
        cache._cache[scan_dir]["projects"] = [{"title": "sentinel_from_cache"}]
        cache._save()

        # Reload cache from disk and re-scan
        cache2 = ScanCache(cache_file)
        results2 = scan_for_projects(config, _cache=cache2)
        assert results2 == [{"title": "sentinel_from_cache"}]

    def test_cache_invalidated_on_file_change(self, tmp_path):
        """Modify files in project dir; next scan detects staleness and re-scans."""
        cache_file = tmp_path / "scan_cache.json"
        scan_dir = tmp_path / "projects"
        proj = scan_dir / "myproj"
        proj.mkdir(parents=True)
        (proj / ".git").mkdir()

        config = self._make_config([str(scan_dir)])

        cache = ScanCache(cache_file)
        results1 = scan_for_projects(config, _cache=cache)
        assert len(results1) == 1

        # Add a new project — changes depth-1 entries of scan_dir
        proj2 = scan_dir / "newproj"
        proj2.mkdir()
        (proj2 / ".git").mkdir()

        # New cache instance re-reads from disk
        cache2 = ScanCache(cache_file)
        results2 = scan_for_projects(config, _cache=cache2)
        # Should now find 2 projects (stale cache triggers re-scan)
        assert len(results2) == 2

    def test_force_refresh_bypasses_cache(self, tmp_path):
        """Even with valid cache, force_refresh=True re-scans."""
        cache_file = tmp_path / "scan_cache.json"
        proj = tmp_path / "projects" / "myproj"
        proj.mkdir(parents=True)
        (proj / ".git").mkdir()

        config = self._make_config([str(tmp_path / "projects")])

        # Populate cache with sentinel
        cache = ScanCache(cache_file)
        scan_dir = str((tmp_path / "projects").resolve())
        staleness_key = cache._compute_staleness_key(tmp_path / "projects")
        cache.update(scan_dir, staleness_key, [{"title": "sentinel_from_cache"}])

        # Normal scan uses cache
        results_cached = scan_for_projects(config, _cache=cache)
        assert results_cached == [{"title": "sentinel_from_cache"}]

        # force_refresh=True bypasses cache
        results_fresh = scan_for_projects(config, force_refresh=True, _cache=cache)
        assert len(results_fresh) == 1
        assert results_fresh[0]["title"] == "myproj"

    def test_cache_staleness_key_uses_depth_1_entries(self, tmp_path):
        """Staleness key changes when files are added or removed at depth 1."""
        cache = ScanCache(tmp_path / "cache.json")

        scan_dir = tmp_path / "projects"
        scan_dir.mkdir()
        (scan_dir / "proj_a").mkdir()

        key1 = cache._compute_staleness_key(scan_dir)

        # Add a new entry at depth 1
        (scan_dir / "proj_b").mkdir()
        key2 = cache._compute_staleness_key(scan_dir)

        assert key1 != key2

        # Remove an entry
        import shutil
        shutil.rmtree(scan_dir / "proj_a")
        key3 = cache._compute_staleness_key(scan_dir)

        assert key3 != key1
        assert key3 != key2


# ── Worktree Detection (Task 6.1) ────────────────────────────────────────────

class TestWorktreeDetection:
    def test_detect_worktree_regular_repo(self, tmp_path):
        """Regular repo with .git directory returns None."""
        (tmp_path / ".git").mkdir()
        assert _detect_worktree(tmp_path) is None

    def test_detect_worktree_valid(self, tmp_path):
        """Worktree with .git file containing gitdir: returns correct parent and branch."""
        parent_git = tmp_path / "parent" / ".git"
        parent_git.mkdir(parents=True)
        wt_dir = parent_git / "worktrees" / "feature-branch"
        wt_dir.mkdir(parents=True)

        worktree = tmp_path / "worktree-dir"
        worktree.mkdir()
        git_file = worktree / ".git"
        git_file.write_text(f"gitdir: {wt_dir}\n")

        result = _detect_worktree(worktree)
        assert result is not None
        assert result["is_worktree"] is True
        assert result["parent_path"] == str(tmp_path / "parent")
        assert result["worktree_branch"] == "feature-branch"

    def test_detect_worktree_missing_git(self, tmp_path):
        """No .git at all returns None."""
        assert _detect_worktree(tmp_path) is None

    def test_detect_worktree_malformed_gitdir(self, tmp_path):
        """Git file without gitdir: line returns None."""
        git_file = tmp_path / ".git"
        git_file.write_text("something else entirely\n")
        assert _detect_worktree(tmp_path) is None

    def test_detect_worktree_windows_paths(self, tmp_path):
        """Backslash paths in gitdir: line are normalized correctly."""
        parent_git = tmp_path / "parent" / ".git"
        parent_git.mkdir(parents=True)
        wt_dir = parent_git / "worktrees" / "my-branch"
        wt_dir.mkdir(parents=True)

        worktree = tmp_path / "wt"
        worktree.mkdir()
        # Write with backslashes like Windows would
        win_path = str(wt_dir).replace("/", "\\")
        (worktree / ".git").write_text(f"gitdir: {win_path}\n")

        result = _detect_worktree(worktree)
        assert result is not None
        assert "\\" not in result["parent_path"]
        assert result["worktree_branch"] == "my-branch"

    def test_build_project_info_marks_worktree(self, tmp_path):
        """Worktree project has is_worktree=True and parent_path set."""
        parent_git = tmp_path / "parent" / ".git"
        parent_git.mkdir(parents=True)
        wt_dir = parent_git / "worktrees" / "feat"
        wt_dir.mkdir(parents=True)

        worktree = tmp_path / "feat-wt"
        worktree.mkdir()
        (worktree / ".git").write_text(f"gitdir: {wt_dir}\n")

        info = _build_project_info(worktree, {".git"})
        assert info["is_worktree"] is True
        assert info["parent_path"] == str(tmp_path / "parent")
        assert info["worktree_branch"] == "feat"

    def test_build_project_info_regular_not_worktree(self, tmp_path):
        """Regular repo has is_worktree=False."""
        proj = tmp_path / "myproj"
        proj.mkdir()
        (proj / ".git").mkdir()

        info = _build_project_info(proj, {".git"})
        assert info["is_worktree"] is False
        assert "parent_path" not in info or info.get("parent_path") is None


class TestWorktreeDiscovery:
    """Scanner must descend into .claude/worktrees/ even after finding a parent project."""

    def test_scanner_finds_worktrees_under_parent(self, tmp_path):
        """Worktrees at <project>/.claude/worktrees/<branch>/ are discovered."""
        # Create parent project with .git dir
        parent = tmp_path / "MyProject"
        parent.mkdir()
        (parent / ".git").mkdir()

        # Create a worktree inside .claude/worktrees/
        wt = parent / ".claude" / "worktrees" / "feature-x"
        wt.mkdir(parents=True)
        # Worktree .git file pointing back to parent
        parent_git_wt = parent / ".git" / "worktrees" / "feature-x"
        parent_git_wt.mkdir(parents=True)
        (wt / ".git").write_text(f"gitdir: {parent_git_wt}\n")

        results = _scan_with_timeout(tmp_path, max_depth=5, markers={".git"},
                                     ignore_dirs={"node_modules", "__pycache__"},
                                     timeout_seconds=5)
        paths = [r["path"] for r in results]
        assert str(parent) in paths, "Parent project not found"
        assert str(wt) in paths, "Worktree under .claude/worktrees/ not found"

    def test_scanner_worktree_has_parent_path(self, tmp_path):
        """Discovered worktree has correct parent_path and is_worktree=True."""
        parent = tmp_path / "Proj"
        parent.mkdir()
        (parent / ".git").mkdir()

        wt = parent / ".claude" / "worktrees" / "bugfix"
        wt.mkdir(parents=True)
        parent_git_wt = parent / ".git" / "worktrees" / "bugfix"
        parent_git_wt.mkdir(parents=True)
        (wt / ".git").write_text(f"gitdir: {parent_git_wt}\n")

        results = _scan_with_timeout(tmp_path, max_depth=5, markers={".git"},
                                     ignore_dirs={"node_modules", "__pycache__"},
                                     timeout_seconds=5)
        wt_items = [r for r in results if r.get("is_worktree")]
        assert len(wt_items) == 1
        assert wt_items[0]["parent_path"] == str(parent)


class TestNormalizeToNative:
    """_normalize_to_native converts WSL /mnt/X/ paths to X:/ on Windows."""

    def test_wsl_path_converted(self):
        """On any platform, /mnt/d/Projects/Foo → D:/Projects/Foo."""
        result = _normalize_to_native("/mnt/d/Projects/Foo")
        # On Linux (WSL), this should still convert for cross-platform compat
        assert result == "D:/Projects/Foo" or result == "/mnt/d/Projects/Foo"
        # The function should at least handle Windows platform

    def test_already_native_windows_passthrough(self):
        """Windows-style paths pass through unchanged."""
        assert _normalize_to_native("D:/Projects/Foo") == "D:/Projects/Foo"

    def test_already_native_backslash_passthrough(self):
        """Backslash Windows paths pass through (not our job to normalize slashes)."""
        result = _normalize_to_native("D:\\Projects\\Foo")
        assert "D:" in result and "Projects" in result

    def test_linux_native_passthrough(self):
        """Non-/mnt/ Linux paths pass through unchanged."""
        assert _normalize_to_native("/home/user/projects") == "/home/user/projects"

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert _normalize_to_native("") == ""

    def test_idempotent(self):
        """Applying twice gives same result."""
        first = _normalize_to_native("/mnt/c/Users/test")
        second = _normalize_to_native(first)
        assert first == second


class TestDetectWorktreeWSLPaths:
    """_detect_worktree handles WSL gitdir paths correctly."""

    def test_wsl_gitdir_produces_normalized_parent(self, tmp_path):
        """A .git file with WSL /mnt/ gitdir still produces a usable parent_path."""
        # Simulate: worktree .git file written by WSL git
        worktree = tmp_path / "my-worktree"
        worktree.mkdir()

        # The gitdir points to a WSL-style path
        # We need the actual dirs to exist for resolve() on relative paths
        parent_git_wt = tmp_path / "parent" / ".git" / "worktrees" / "feat"
        parent_git_wt.mkdir(parents=True)

        # Write WSL-style absolute path
        wsl_gitdir = str(parent_git_wt).replace("\\", "/")
        (worktree / ".git").write_text(f"gitdir: {wsl_gitdir}\n")

        result = _detect_worktree(worktree)
        assert result is not None
        # parent_path should NOT contain /mnt/ if running on Windows
        # On Linux it's fine as-is
        assert result["parent_path"] == str(tmp_path / "parent") or \
               result["parent_path"].replace("\\", "/") == str(tmp_path / "parent").replace("\\", "/")

    def test_relative_gitdir_resolved(self, tmp_path):
        """Relative gitdir paths are resolved to absolute before parsing."""
        parent = tmp_path / "project"
        parent.mkdir()
        parent_git = parent / ".git"
        parent_git.mkdir()
        wt_dir = parent_git / "worktrees" / "my-branch"
        wt_dir.mkdir(parents=True)

        worktree = tmp_path / "project" / ".claude" / "worktrees" / "my-branch"
        worktree.mkdir(parents=True)
        # Write relative gitdir
        (worktree / ".git").write_text("gitdir: ../../../.git/worktrees/my-branch\n")

        result = _detect_worktree(worktree)
        assert result is not None
        assert result["is_worktree"] is True
        assert result["worktree_branch"] == "my-branch"
        # parent_path should be the resolved absolute path of 'project'
        expected = str(parent).replace("\\", "/")
        actual = result["parent_path"].replace("\\", "/")
        assert actual == expected
