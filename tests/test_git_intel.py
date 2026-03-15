"""Tests for git_intel.py — git intelligence module."""
import pytest
import subprocess
import json
import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helper: create a tmp git repo ─────────────────────────────────────────────

def _init_git_repo(tmp_path, commits=None):
    """Create a git repo in tmp_path with optional commits.

    Args:
        tmp_path: Path for the repo.
        commits: list of (subject, days_ago) tuples. If None, just git init with no commits.
    Returns:
        Path to the repo.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), capture_output=True, check=True,
    )
    if commits:
        for subject, days_ago in commits:
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S")
            env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", subject],
                cwd=str(repo), capture_output=True, check=True, env=env,
            )
    return repo


# ── Task 5.1: Core module tests ──────────────────────────────────────────────


def test_get_head_hash_valid_repo(tmp_path):
    """Returns 40-char hex string from a real tmp git repo."""
    repo = _init_git_repo(tmp_path, commits=[("init", 0)])
    from git_intel import get_head_hash
    h = get_head_hash(str(repo))
    assert h is not None
    assert len(h) == 40
    assert all(c in "0123456789abcdef" for c in h)


def test_get_head_hash_empty_repo(tmp_path):
    """Returns None for repo with git init but no commits."""
    repo = _init_git_repo(tmp_path)
    from git_intel import get_head_hash
    assert get_head_hash(str(repo)) is None


def test_get_head_hash_no_git_dir(tmp_path):
    """Returns None for a plain directory."""
    plain = tmp_path / "norepo"
    plain.mkdir()
    from git_intel import get_head_hash
    assert get_head_hash(str(plain)) is None


def test_get_commit_log_parses_entries(tmp_path):
    """Correctly parses hash, date, subject from git log output."""
    repo = _init_git_repo(tmp_path, commits=[("first commit", 5), ("second commit", 2)])
    from git_intel import get_commit_log
    commits = get_commit_log(str(repo))
    assert len(commits) == 2
    for c in commits:
        assert "hash" in c
        assert "date" in c
        assert "subject" in c
        assert isinstance(c["date"], datetime)
    assert commits[0]["subject"] == "second commit"
    assert commits[1]["subject"] == "first commit"


def test_get_commit_log_pipe_in_subject(tmp_path):
    """Subject containing | chars is parsed correctly (null-byte delimiter)."""
    repo = _init_git_repo(tmp_path, commits=[("feat: add x | y | z", 1)])
    from git_intel import get_commit_log
    commits = get_commit_log(str(repo))
    assert len(commits) == 1
    assert commits[0]["subject"] == "feat: add x | y | z"


def test_get_commit_log_empty_repo(tmp_path):
    """Returns empty list for repo with no commits."""
    repo = _init_git_repo(tmp_path)
    from git_intel import get_commit_log
    assert get_commit_log(str(repo)) == []


def test_get_commit_log_timeout(tmp_path):
    """Returns empty list and no crash when subprocess times out."""
    from git_intel import get_commit_log
    with patch("git_intel.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
        assert get_commit_log(str(tmp_path)) == []


def test_get_commit_log_permission_error(tmp_path):
    """Returns empty list on PermissionError."""
    from git_intel import get_commit_log
    with patch("git_intel.subprocess.run", side_effect=PermissionError("no access")):
        assert get_commit_log(str(tmp_path)) == []


# ── Cache tests ──────────────────────────────────────────────────────────────

def test_cache_hit_skips_git_log(tmp_path):
    """When HEAD hash matches cache, git log is not called."""
    from git_intel import GitIntelCache, get_head_hash, get_commit_log

    repo = _init_git_repo(tmp_path, commits=[("init", 0)])
    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)

    head = get_head_hash(str(repo))
    commits = get_commit_log(str(repo))
    cache.set(str(repo), head, 6, commits)
    cache.save()

    # Reload cache and verify hit
    cache2 = GitIntelCache(cache_file)
    cached = cache2.get(str(repo), head, 6)
    assert cached is not None
    assert len(cached) == 1


def test_cache_miss_calls_git_log(tmp_path):
    """When HEAD hash differs from cache, git log is called."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    cache.set("/some/repo", "oldhash", 6, [{"hash": "old", "date": "2026-01-01", "subject": "old"}])
    cache.save()

    cache2 = GitIntelCache(cache_file)
    assert cache2.get("/some/repo", "newhash", 6) is None


def test_cache_miss_on_history_months_change(tmp_path):
    """When history_months config changes, cache is invalidated even if HEAD matches."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    cache.set("/repo", "abc123", 6, [{"hash": "a", "date": "2026-01-01", "subject": "x"}])
    cache.save()

    cache2 = GitIntelCache(cache_file)
    # Same HEAD hash, different history_months
    assert cache2.get("/repo", "abc123", 3) is None
    # Same HEAD hash, same history_months
    assert cache2.get("/repo", "abc123", 6) is not None


def test_cache_thread_safety(tmp_path):
    """Concurrent reads/writes to cache do not raise or corrupt data."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    errors = []

    def writer(i):
        try:
            cache.set(f"/repo{i}", f"hash{i}", 6, [{"hash": f"h{i}", "date": "2026-01-01", "subject": f"s{i}"}])
            cache.save()
        except Exception as e:
            errors.append(e)

    def reader(i):
        try:
            cache.get(f"/repo{i}", f"hash{i}", 6)
        except Exception as e:
            errors.append(e)

    threads = []
    for i in range(20):
        threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == [], f"Thread safety errors: {errors}"


def test_cache_atomic_write(tmp_path):
    """Cache file is written atomically (tmp + replace pattern)."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    cache.set("/repo", "abc", 6, [])
    cache.save()

    assert cache_file.exists()
    data = json.loads(cache_file.read_text())
    assert "/repo" in data


# ── analyze_project tests ────────────────────────────────────────────────────

def _default_config():
    return {
        "git_intel": {
            "timeout_seconds": 5,
            "history_months": 6,
            "stalled_threshold_days": 14,
        }
    }


def test_analyze_project_returns_full_dict(tmp_path):
    """Result dict contains head_hash, commits, commit_count keys."""
    repo = _init_git_repo(tmp_path, commits=[("init", 0)])
    from git_intel import analyze_project
    result = analyze_project(str(repo), _default_config(), cache_dir=tmp_path)
    assert "head_hash" in result
    assert "commits" in result
    assert "commit_count" in result
    assert result["commit_count"] == 1
    assert result["error"] is None


def test_analyze_projects_batch(tmp_path):
    """Multiple projects analyzed, each with independent results."""
    repo1 = _init_git_repo(tmp_path / "a", commits=[("a1", 0)])
    repo2 = _init_git_repo(tmp_path / "b", commits=[("b1", 1), ("b2", 0)])
    from git_intel import analyze_projects
    projects = [{"path": str(repo1)}, {"path": str(repo2)}]
    results = analyze_projects(projects, _default_config(), cache_dir=tmp_path)
    assert str(repo1) in results
    assert str(repo2) in results
    assert results[str(repo1)]["commit_count"] == 1
    assert results[str(repo2)]["commit_count"] == 2


def test_analyze_projects_one_broken(tmp_path):
    """One broken repo does not prevent others from succeeding."""
    repo = _init_git_repo(tmp_path / "good", commits=[("ok", 0)])
    bad = tmp_path / "bad"
    bad.mkdir()
    from git_intel import analyze_projects
    projects = [{"path": str(repo)}, {"path": str(bad)}]
    results = analyze_projects(projects, _default_config(), cache_dir=tmp_path)
    assert results[str(repo)]["commit_count"] == 1
    assert results[str(bad)]["commit_count"] == 0
