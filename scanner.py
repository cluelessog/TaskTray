"""
Disk Scanner — discovers projects by looking for marker files/folders.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime


def scan_for_projects(config: dict) -> list[dict]:
    """
    Walk configured directories up to max_depth looking for project markers.
    Returns a list of discovered project dicts.
    """
    scanner_cfg = config.get("scanner", {})
    scan_dirs = scanner_cfg.get("scan_dirs", [])
    max_depth = scanner_cfg.get("max_depth", 3)
    markers = set(scanner_cfg.get("markers", [".git"]))
    ignore_dirs = set(scanner_cfg.get("ignore_dirs", []))

    projects = []
    seen_paths = set()

    for base_dir in scan_dirs:
        base = Path(base_dir).expanduser().resolve()
        if not base.exists():
            continue

        for root, dirs, files in os.walk(base):
            root_path = Path(root)
            depth = len(root_path.relative_to(base).parts)

            if depth > max_depth:
                dirs.clear()
                continue

            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            # Check if this directory contains any project marker
            entries = set(dirs + files)
            found_markers = entries & markers

            if found_markers and str(root_path) not in seen_paths:
                seen_paths.add(str(root_path))
                project = _build_project_info(root_path, found_markers)
                projects.append(project)
                # Don't recurse into this project's subdirs
                dirs.clear()

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
        "id": f"disk_{hash(str(path)) & 0xFFFFFFFF:08x}",
        "title": path.name,
        "path": str(path),
        "source": "disk",
        "type": project_type,
        "category": category,
        "status": "active",
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
