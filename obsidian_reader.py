"""
Obsidian Reader — reads notes from an Obsidian vault using three methods:
1. Dashboard folder — any .md file in the configured folder
2. Tags — notes with specific tags anywhere in the vault
3. YAML frontmatter — notes with `dashboard: true` in frontmatter
"""
from __future__ import annotations

import os
import re
import hashlib
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any


def read_obsidian_items(config: dict) -> list[dict]:
    """
    Scan Obsidian vault and return dashboard items from all three sources.
    Deduplicates by file path.
    """
    obs_cfg = config.get("obsidian", {})
    vault_path = Path(obs_cfg.get("vault_path", "")).expanduser().resolve()

    if not vault_path.exists():
        return []

    items_by_path: dict[str, dict] = {}

    # Method 1: Dashboard folder
    dashboard_folder = obs_cfg.get("dashboard_folder", "Dashboard")
    folder_path = vault_path / dashboard_folder
    if folder_path.exists():
        for md_file in folder_path.rglob("*.md"):
            item = _parse_note(md_file, vault_path, source_method="folder")
            if item:
                items_by_path[str(md_file)] = item

    # Method 2 & 3: Scan all notes for tags and frontmatter
    target_tags = set(obs_cfg.get("tags", []))
    fm_key = obs_cfg.get("frontmatter_key", "dashboard")

    for md_file in vault_path.rglob("*.md"):
        str_path = str(md_file)

        # Skip if already found via folder
        if str_path in items_by_path:
            continue

        # Skip hidden folders and common non-note dirs
        parts = md_file.relative_to(vault_path).parts
        if any(p.startswith(".") or p in ("node_modules", ".obsidian", ".trash") for p in parts):
            continue

        content, frontmatter = _read_note(md_file)
        if content is None:
            continue

        # Method 2: Check for tags
        found_tags = _extract_tags(content)
        if found_tags & target_tags:
            item = _parse_note(md_file, vault_path, source_method="tag", content=content, frontmatter=frontmatter)
            if item:
                # Add the matched tags as extra info
                item["matched_tags"] = list(found_tags & target_tags)
                items_by_path[str_path] = item
                continue

        # Method 3: Check frontmatter
        if frontmatter and frontmatter.get(fm_key):
            item = _parse_note(md_file, vault_path, source_method="frontmatter", content=content, frontmatter=frontmatter)
            if item:
                items_by_path[str_path] = item

    return list(items_by_path.values())


def _read_note(file_path: Path) -> tuple[str | None, dict[str, Any] | None]:
    """Read a markdown file and extract frontmatter + content."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except (OSError, UnicodeDecodeError):
        return None, None

    frontmatter: dict[str, Any] = {}
    content = raw

    # Parse YAML frontmatter
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            content = parts[2].strip()

    return content, frontmatter


def _extract_tags(content: str) -> set[str]:
    """Extract #tags from note content (including nested tags like #dashboard/project)."""
    # Match #word and #word/word patterns, but not inside code blocks
    # Remove code blocks first
    cleaned = re.sub(r"```[\s\S]*?```", "", content)
    cleaned = re.sub(r"`[^`]*`", "", cleaned)

    tags = set(re.findall(r"(?:^|\s)(#[\w/\-]+)", cleaned))
    return tags


def _parse_note(file_path: Path, vault_path: Path, source_method: str,
                content: str | None = None, frontmatter: dict | None = None) -> dict | None:
    """Parse a markdown note into a dashboard item."""
    if content is None or frontmatter is None:
        content, frontmatter = _read_note(file_path)
        if content is None:
            return None

    # Title: frontmatter title > first H1 > filename
    title = None
    if frontmatter:
        title = frontmatter.get("title")
    if not title:
        h1_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
    if not title:
        title = file_path.stem.replace("-", " ").replace("_", " ")

    # Status from frontmatter
    status = "backlog"
    if frontmatter:
        fm_status = str(frontmatter.get("status", "")).lower()
        if fm_status in ("active", "paused", "backlog", "done"):
            status = fm_status

    # Priority from frontmatter
    priority = "p2"
    if frontmatter:
        fm_pri = str(frontmatter.get("priority", "")).lower()
        if fm_pri in ("p0", "p1", "p2", "p3"):
            priority = fm_pri

    # Category from frontmatter or tags or folder heuristic
    category = "ideas"
    if frontmatter:
        fm_cat = str(frontmatter.get("category", "")).lower()
        if fm_cat in ("dev", "trading", "teaching", "ideas", "personal", "learning"):
            category = fm_cat

    # Infer category from tag if not in frontmatter
    if not (frontmatter or {}).get("category"):
        tags = _extract_tags(content)
        if any("project" in t for t in tags):
            category = "dev"
        elif any("idea" in t for t in tags):
            category = "ideas"
        elif any("task" in t for t in tags):
            category = "dev"
        elif any("learning" in t for t in tags):
            category = "learning"

    # Focus from frontmatter
    focused = bool(frontmatter.get("focused", False)) if frontmatter else False

    # Extract a summary — first paragraph after title
    summary = _extract_summary(content)

    # Last modified
    try:
        mtime = file_path.stat().st_mtime
        last_modified = datetime.fromtimestamp(mtime).isoformat()
    except OSError:
        last_modified = None

    rel_path = str(file_path.relative_to(vault_path))

    return {
        "id": f"obs_{hashlib.md5(rel_path.encode()).hexdigest()[:8]}",
        "title": title,
        "path": str(file_path),
        "vault_relative_path": rel_path,
        "source": "obsidian",
        "source_method": source_method,
        "category": category,
        "status": status,
        "priority": priority,
        "notes": summary or "",
        "last_modified": last_modified,
        "focused": focused,
        "created_at": last_modified or datetime.now().isoformat(),
    }


def _extract_summary(content: str) -> str | None:
    """Extract first meaningful paragraph as summary."""
    lines = content.split("\n")
    summary_lines = []
    started = False

    for line in lines:
        stripped = line.strip()
        # Skip headers, tags, empty lines at start
        if not started:
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                started = True
                summary_lines.append(stripped)
        else:
            if not stripped:
                break
            summary_lines.append(stripped)

    summary = " ".join(summary_lines)
    if len(summary) > 300:
        summary = summary[:297] + "..."
    return summary or None
