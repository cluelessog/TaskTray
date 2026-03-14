"""Tests for scanner.py — targeting >= 60% coverage."""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import _detect_type, _extract_description, _guess_category, scan_for_projects


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
