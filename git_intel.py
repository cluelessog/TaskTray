"""
Git Intelligence — extracts commit history, computes velocity metrics,
and infers project lifecycle stages from git repositories.

Standalone module: ``from git_intel import analyze_projects``
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("tasktray")

_DEFAULT_TIMEOUT = 5
_DEFAULT_HISTORY_MONTHS = 6
_DEFAULT_CACHE_FILE = Path(__file__).parent / "data" / "git_intel_cache.json"


# ── Cache ────────────────────────────────────────────────────────────────────


class GitIntelCache:
    """HEAD-hash-keyed cache for git intelligence results.

    Thread-safe: all public methods protected by a lock.
    """

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, repo_path: str, head_hash: str, history_months: int) -> list[dict] | None:
        """Return cached commits if HEAD hash and history_months match, else None."""
        with self._lock:
            entry = self._data.get(repo_path)
            if (
                entry
                and entry.get("head_hash") == head_hash
                and entry.get("history_months") == history_months
            ):
                return entry.get("commits")
            return None

    def set(self, repo_path: str, head_hash: str, history_months: int, commits: list[dict]) -> None:
        """Store commits for a repo."""
        with self._lock:
            self._data[repo_path] = {
                "head_hash": head_hash,
                "history_months": history_months,
                "commits": commits,
                "timestamp": datetime.now().timestamp(),
            }

    def save(self) -> None:
        """Atomic write: tempfile + os.replace."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=self._path.parent, suffix=".tmp", prefix=self._path.stem,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, default=str)
                os.replace(tmp, self._path)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise


# ── Core git operations ──────────────────────────────────────────────────────


def get_head_hash(repo_path: str, timeout: int = _DEFAULT_TIMEOUT) -> str | None:
    """Return the HEAD commit hash, or None for non-git / empty repos."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError):
        return None


def get_commit_log(
    repo_path: str,
    since_months: int = _DEFAULT_HISTORY_MONTHS,
    timeout: int = _DEFAULT_TIMEOUT,
) -> list[dict]:
    """Return list of commit dicts parsed from git log.

    Each dict: ``{"hash": str, "date": datetime, "subject": str}``
    Uses null-byte delimiter to handle pipe chars in subjects.
    """
    try:
        r = subprocess.run(
            [
                "git", "log",
                f"--since={since_months} months ago",
                "--format=%H%x00%ai%x00%s",
            ],
            cwd=repo_path, capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode != 0:
            return []

        commits = []
        for line in r.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\x00")
            if len(parts) < 3:
                continue
            commit_hash = parts[0]
            try:
                # git %ai gives "2026-03-15 10:30:00 +0530" — Python 3.8
                # fromisoformat can't handle the timezone, so strip it
                date_str = parts[1].strip()
                # Remove trailing timezone offset (e.g. " +0530" or " -0400")
                if len(date_str) > 5 and date_str[-5] in "+-" and date_str[-6] == " ":
                    date_str = date_str[:-6]
                date = datetime.fromisoformat(date_str)
            except (ValueError, IndexError):
                continue
            subject = parts[2]
            commits.append({"hash": commit_hash, "date": date, "subject": subject})
        return commits

    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError):
        return []


# ── Public API ───────────────────────────────────────────────────────────────


def analyze_project(
    repo_path: str,
    config: dict,
    cache_dir: Path | None = None,
) -> dict:
    """Analyze a single project. Returns result dict with head_hash, commits, commit_count, error."""
    git_cfg = config.get("git_intel", {})
    timeout = git_cfg.get("timeout_seconds", _DEFAULT_TIMEOUT)
    history_months = git_cfg.get("history_months", _DEFAULT_HISTORY_MONTHS)

    cache_path = (
        (cache_dir / "git_intel_cache.json")
        if cache_dir
        else Path(git_cfg.get("cache_file", str(_DEFAULT_CACHE_FILE)))
    )
    cache = GitIntelCache(cache_path)

    result: dict[str, Any] = {
        "head_hash": None,
        "commits": [],
        "commit_count": 0,
        "error": None,
    }

    try:
        head = get_head_hash(repo_path, timeout=timeout)
        result["head_hash"] = head

        if head is None:
            return result

        # Check cache
        cached = cache.get(repo_path, head, history_months)
        if cached is not None:
            result["commits"] = cached
            result["commit_count"] = len(cached)
            return result

        # Cache miss — run git log
        commits = get_commit_log(repo_path, since_months=history_months, timeout=timeout)
        # Serialize dates for cache storage
        serialized = [
            {"hash": c["hash"], "date": c["date"].isoformat(), "subject": c["subject"]}
            for c in commits
        ]
        cache.set(repo_path, head, history_months, serialized)
        cache.save()

        result["commits"] = serialized
        result["commit_count"] = len(commits)

    except Exception as e:
        log.warning("Error analyzing %s: %s", repo_path, e)
        result["error"] = str(e)

    return result


def analyze_projects(
    project_list: list[dict],
    config: dict,
    cache_dir: Path | None = None,
) -> dict[str, dict]:
    """Batch-analyze projects. Returns {path: result_dict}.

    One broken repo never prevents others from succeeding.
    """
    results = {}
    for proj in project_list:
        path = proj.get("path", "")
        try:
            results[path] = analyze_project(path, config, cache_dir=cache_dir)
        except Exception as e:
            log.warning("Unexpected error for %s: %s", path, e)
            results[path] = {
                "head_hash": None,
                "commits": [],
                "commit_count": 0,
                "error": str(e),
            }
    return results
