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


class ScanCache:
    """Cache for scan results, keyed by directory path with NTFS-safe staleness detection."""

    def __init__(self, cache_path: Path):
        self._cache_path = cache_path
        self._cache: dict = {}  # dir_path -> {"staleness_key": str, "projects": list, "timestamp": float}
        self._load()

    def _load(self):
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save(self):
        """Atomic write: write to temp file then rename."""
        tmp_path = self._cache_path.with_suffix(".tmp")
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
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
        entry = self._cache.get(dir_path)
        if entry and entry.get("staleness_key") == staleness_key:
            return entry["projects"]
        return None

    def update(self, dir_path: str, staleness_key: str, projects: "list[dict]"):
        """Update cache for a directory."""
        self._cache[dir_path] = {
            "staleness_key": staleness_key,
            "projects": projects,
            "timestamp": time.time(),
        }
        self._save()

    def invalidate_all(self):
        """Clear entire cache."""
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
                project = _build_project_info(root_path, found_markers)
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

    cache = _cache if _cache is not None else _get_module_cache()

    # Detect config changes: invalidate cache if config fingerprint changed
    config_hash = hashlib.md5(
        json.dumps(
            {"scan_dirs": scan_dirs, "markers": sorted(markers), "ignore_dirs": sorted(ignore_dirs)},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    stored_config_hash = cache._cache.get("__config_hash__")
    if stored_config_hash is not None and stored_config_hash != config_hash:
        logger.info("Config changed — invalidating scan cache.")
        cache.invalidate_all()
    cache._cache["__config_hash__"] = config_hash

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

        # Cache miss or force_refresh: perform actual scan
        found = _scan_with_timeout(base, max_depth, markers, ignore_dirs, timeout_seconds)
        staleness_key = cache._compute_staleness_key(base)
        cache.update(dir_key, staleness_key, found)
        projects.extend(found)

    return projects


def _build_project_info(path: Path, markers: set) -> dict:
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

    return {
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
    }


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
