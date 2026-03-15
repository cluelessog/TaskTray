"""
Disk Scanner — discovers projects by looking for marker files/folders.
"""
from __future__ import annotations

import os
import json
import hashlib
import logging
import threading
import time
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def _detect_worktree(path: Path) -> "dict | None":
    """Detect if path is a git worktree (not a regular repo).

    Worktrees have a `.git` **file** (not directory) containing a ``gitdir:`` line
    pointing to ``<parent>/.git/worktrees/<branch>``.

    Returns ``{"is_worktree": True, "parent_path": str, "worktree_branch": str}``
    or ``None`` if not a worktree.
    """
    git_path = path / ".git"
    try:
        if not git_path.exists() or git_path.is_dir():
            return None
        content = git_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None

    if not content.startswith("gitdir:"):
        return None

    gitdir = content[len("gitdir:"):].strip()
    # Normalise Windows backslashes
    gitdir = gitdir.replace("\\", "/")

    # Expected: <parent>/.git/worktrees/<branch-name>
    parts = gitdir.replace("\\", "/").split("/")
    try:
        wt_idx = parts.index("worktrees")
    except ValueError:
        return None

    if wt_idx < 2 or wt_idx + 1 >= len(parts):
        return None

    branch_name = parts[wt_idx + 1]
    # Parent path is everything before ".git/worktrees/..."
    # .git is at wt_idx - 1
    parent_path = "/".join(parts[: wt_idx - 1])
    if not parent_path:
        return None

    return {
        "is_worktree": True,
        "parent_path": parent_path,
        "worktree_branch": branch_name,
    }


def _resolve_git_index(path: Path) -> Path:
    """Return the path to the git index file, resolving worktree gitdir if needed."""
    git_path = path / ".git"
    if git_path.is_file():
        try:
            content = git_path.read_text(encoding="utf-8", errors="replace").strip()
            if content.startswith("gitdir:"):
                gitdir = content[len("gitdir:"):].strip().replace("\\", "/")
                return Path(gitdir) / "index"
        except OSError:
            pass
    return git_path / "index"


def detect_recent_activity(path: Path, threshold_minutes: int) -> bool:
    """Check if a project directory has recently modified files (depth 1 + .git/index).

    Returns False if threshold_minutes <= 0 (disabled) or on any error.
    For worktrees, resolves the actual gitdir path to find the real index file.
    """
    if threshold_minutes <= 0:
        return False
    cutoff = time.time() - (threshold_minutes * 60)
    try:
        # Check top-level files
        for entry in path.iterdir():
            if entry.is_file():
                try:
                    if entry.stat().st_mtime > cutoff:
                        return True
                except OSError:
                    continue
        # Check git index (resolves worktree gitdir)
        git_index = _resolve_git_index(path)
        if git_index.exists():
            try:
                if git_index.stat().st_mtime > cutoff:
                    return True
            except OSError:
                pass
    except OSError:
        logger.debug("Cannot read directory %s for activity detection", path)
        return False
    return False


class ScanCache:
    """Cache for scan results, keyed by directory path with NTFS-safe staleness detection.

    Thread-safe: all public methods are protected by a lock.
    """

    def __init__(self, cache_path: Path):
        self._cache_path = cache_path
        self._lock = threading.Lock()
        self._cache: dict = {}  # dir_path -> {"staleness_key": str, "projects": list, "timestamp": float}
        self._config_hash: str | None = None  # stored separately from cache entries
        self._load()

    def _load(self):
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # Extract config hash from legacy format (stored in same dict)
                self._config_hash = raw.pop("__config_hash__", None)
                self._cache = raw
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save(self):
        """Atomic write: write to temp file then rename."""
        tmp_path = self._cache_path.with_suffix(".tmp")
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Merge config hash into persisted data (separate from cache entries in memory)
            persisted = dict(self._cache)
            if self._config_hash is not None:
                persisted["__config_hash__"] = self._config_hash
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(persisted, f, indent=2)
            tmp_path.replace(self._cache_path)
        except OSError as e:
            logger.warning("Failed to save scan cache: %s", e)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _compute_staleness_key(self, dir_path: Path) -> str:
        """Hash of child entry names + mtimes at depth 1 (NTFS-safe)."""
        entries = []
        try:
            for entry in sorted(dir_path.iterdir()):
                try:
                    st = entry.stat()
                    entries.append(f"{entry.name}:{st.st_mtime}")
                except OSError:
                    entries.append(f"{entry.name}:error")
        except OSError:
            return ""
        return hashlib.md5("|".join(entries).encode()).hexdigest()

    def get_cached(self, dir_path: str, staleness_key: str) -> "list[dict] | None":
        """Return cached projects if staleness key matches, else None."""
        with self._lock:
            entry = self._cache.get(dir_path)
            if entry and entry.get("staleness_key") == staleness_key:
                return entry["projects"]
            return None

    def update(self, dir_path: str, staleness_key: str, projects: "list[dict]"):
        """Update cache for a directory."""
        with self._lock:
            self._cache[dir_path] = {
                "staleness_key": staleness_key,
                "projects": projects,
                "timestamp": time.time(),
            }
            self._save()

    def get_config_hash(self) -> "str | None":
        """Return the stored config hash."""
        with self._lock:
            return self._config_hash

    def set_config_hash(self, config_hash: str) -> None:
        """Store the config hash."""
        with self._lock:
            self._config_hash = config_hash
            self._save()

    def invalidate_all(self):
        """Clear cache entries (preserves config hash)."""
        with self._lock:
            self._cache = {}
            self._save()


# Module-level cache instance (lazy-initialised on first use)
_scan_cache: "ScanCache | None" = None
_CACHE_PATH = Path(__file__).parent / "data" / "scan_cache.json"


def _get_module_cache() -> ScanCache:
    global _scan_cache
    if _scan_cache is None:
        _scan_cache = ScanCache(_CACHE_PATH)
    return _scan_cache


def _scan_with_timeout(
    base: Path,
    max_depth: int,
    markers: set,
    ignore_dirs: set,
    timeout_seconds: int,
    activity_threshold_minutes: int = 30,
) -> list[dict]:
    """Scan a single base directory with a timeout. Returns projects found or empty list on timeout."""
    results: list[dict] = []

    def _do_scan():
        seen_paths: set[str] = set()
        for root, dirs, files in os.walk(base):
            root_path = Path(root)
            depth = len(root_path.relative_to(base).parts)

            if depth > max_depth:
                dirs.clear()
                continue

            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            entries = set(dirs + files)
            found_markers = entries & markers

            if found_markers and str(root_path) not in seen_paths:
                seen_paths.add(str(root_path))
                project = _build_project_info(root_path, found_markers, activity_threshold_minutes)
                results.append(project)
                dirs.clear()

    thread = threading.Thread(target=_do_scan, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        logger.warning(
            "Scan of '%s' exceeded timeout of %ds — skipping directory.",
            base,
            timeout_seconds,
        )
        return []

    return results


def scan_for_projects(
    config: dict,
    force_refresh: bool = False,
    _cache: "ScanCache | None" = None,
) -> list[dict]:
    """
    Walk configured directories up to max_depth looking for project markers.
    Returns a list of discovered project dicts.

    Args:
        config: Application config dict.
        force_refresh: If True, skip cache and re-scan all directories.
        _cache: Optional ScanCache instance (uses module-level cache if None).
    """
    scanner_cfg = config.get("scanner", {})
    scan_dirs = scanner_cfg.get("scan_dirs", [])
    max_depth = scanner_cfg.get("max_depth", 3)
    markers = set(scanner_cfg.get("markers", [".git"]))
    ignore_dirs = set(scanner_cfg.get("ignore_dirs", []))
    timeout_seconds = scanner_cfg.get("timeout_seconds", 10)
    activity_threshold_minutes = scanner_cfg.get("activity_threshold_minutes", 30)

    cache = _cache if _cache is not None else _get_module_cache()

    # Detect config changes: invalidate cache if config fingerprint changed
    config_hash = hashlib.md5(
        json.dumps(
            {"scan_dirs": scan_dirs, "markers": sorted(markers), "ignore_dirs": sorted(ignore_dirs)},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    stored_config_hash = cache.get_config_hash()
    if stored_config_hash is not None and stored_config_hash != config_hash:
        logger.info("Config changed — invalidating scan cache.")
        cache.invalidate_all()
    cache.set_config_hash(config_hash)

    projects = []

    for base_dir in scan_dirs:
        base = Path(base_dir).expanduser().resolve()
        if not base.exists():
            continue

        dir_key = str(base)

        if not force_refresh:
            staleness_key = cache._compute_staleness_key(base)
            cached = cache.get_cached(dir_key, staleness_key)
            if cached is not None:
                logger.debug("Cache hit for %s", dir_key)
                projects.extend(cached)
                continue

        # Cache miss or force_refresh: compute staleness key BEFORE scan
        # to avoid TOCTOU where filesystem changes during the scan
        staleness_key = cache._compute_staleness_key(base)
        found = _scan_with_timeout(base, max_depth, markers, ignore_dirs, timeout_seconds, activity_threshold_minutes)
        cache.update(dir_key, staleness_key, found)
        projects.extend(found)

    return projects


def _build_project_info(path: Path, markers: set, activity_threshold_minutes: int = 30) -> dict:
    """Build a project info dict from a discovered path."""
    # Detect project type from markers
    project_type = _detect_type(markers, path)

    # Get last modified time
    try:
        mtime = path.stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime).isoformat()
    except OSError:
        last_modified = None

    # Try to get description from common files
    description = _extract_description(path)

    # Detect category heuristically
    category = _guess_category(path, project_type)

    info = {
        "id": f"disk_{hashlib.md5(str(path).encode()).hexdigest()[:8]}",
        "title": path.name,
        "path": str(path),
        "source": "disk",
        "type": project_type,
        "category": category,
        "status": "backlog",
        "priority": "p2",
        "notes": description or f"{project_type} project at {path}",
        "last_modified": last_modified,
        "markers": list(markers),
        "focused": False,
        "created_at": datetime.now().isoformat(),
        "has_recent_activity": detect_recent_activity(path, activity_threshold_minutes),
        "is_worktree": False,
    }

    wt = _detect_worktree(path)
    if wt:
        info["is_worktree"] = True
        info["parent_path"] = wt["parent_path"]
        info["worktree_branch"] = wt["worktree_branch"]

    return info


def _detect_type(markers: set, path: Path) -> str:
    """Detect project type from markers."""
    if "Cargo.toml" in markers or "tauri.conf.json" in markers:
        return "rust"
    if "package.json" in markers:
        # Check if it's a specific framework
        pkg_path = path / "package.json"
        if pkg_path.exists():
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "@angular/core" in deps:
                    return "angular"
                if "react" in deps:
                    return "react"
                if "vue" in deps:
                    return "vue"
                if "next" in deps:
                    return "nextjs"
                if "@tauri-apps/api" in deps:
                    return "tauri"
            except (json.JSONDecodeError, OSError):
                pass
        return "node"
    if "pyproject.toml" in markers or "setup.py" in markers:
        return "python"
    if "go.mod" in markers:
        return "go"
    if "pom.xml" in markers:
        return "java"
    if "docker-compose.yml" in markers:
        return "docker"
    return "unknown"


def _extract_description(path: Path) -> str | None:
    """Try to extract a description from README or package.json."""
    # Try README
    for readme_name in ["README.md", "readme.md", "README.txt", "README"]:
        readme = path / readme_name
        if readme.exists():
            try:
                with open(readme, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                # Get first non-header, non-empty line
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("="):
                        return stripped[:200]
            except OSError:
                pass

    # Try package.json description
    pkg = path / "package.json"
    if pkg.exists():
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "description" in data and data["description"]:
                return data["description"][:200]
        except (json.JSONDecodeError, OSError):
            pass

    return None


def _guess_category(path: Path, project_type: str) -> str:
    """Heuristically guess the category."""
    name_lower = str(path).lower()

    if any(kw in name_lower for kw in ["trad", "stock", "market", "kite", "stark", "angel"]):
        return "trading"
    if any(kw in name_lower for kw in ["teach", "angular", "learn", "course", "tutorial"]):
        return "teaching"
    if any(kw in name_lower for kw in ["idea", "experiment", "poc", "prototype"]):
        return "ideas"
    if any(kw in name_lower for kw in ["personal", "home", "dotfile"]):
        return "personal"

    return "dev"
