from __future__ import annotations

"""
cc_status_reader.py — Claude Code project status reader for TaskTray.

Drop this file into your TaskTray project root alongside server.py.
It reads docs/STATUS.md and docs/PLAN.md from configured projects
and returns structured data that TaskTray can merge into its dashboard.

Usage in server.py:
    from cc_status_reader import CCStatusReader

    cc_reader = CCStatusReader(config)

    # In your sync function:
    cc_items = cc_reader.read_all()

    # New API endpoint:
    @app.route("/api/cc-status")
    def get_cc_status():
        return jsonify(cc_reader.read_all())
"""

import re
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("tasktray.cc_status")


class CCStatusReader:
    """Reads Claude Code project status files and returns structured data."""

    def __init__(self, config: dict):
        """
        Initialize with TaskTray config.

        Expects config to have a 'claude_code' section:

            claude_code:
              projects_file: "path/to/projects.json"
              # OR inline:
              projects:
                - name: "Stark Trading"
                  path: "~/projects/StarkTrading"
                - name: "TaskTray"
                  path: "~/projects/task-tray"
        """
        self.config = config.get("claude_code", {})
        self._projects = self._load_projects()

    def _load_projects(self) -> list[dict]:
        """Load project list from config or external file."""
        # Option 1: Inline in config.yaml
        if "projects" in self.config:
            return self.config["projects"]

        # Option 2: External projects.json file
        projects_file = self.config.get("projects_file")
        if projects_file:
            path = Path(projects_file).expanduser().resolve()
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            log.warning(f"Projects file not found: {path}")

        return []

    def _make_id(self, name: str) -> str:
        """Generate a stable ID for a Claude Code project."""
        return "cc_" + hashlib.md5(name.encode()).hexdigest()[:8]

    def _parse_status_md(self, filepath: Path) -> dict:
        """Parse a STATUS.md file into structured data."""
        if not filepath.exists():
            return {"error": f"Not found: {filepath}"}

        text = filepath.read_text(encoding="utf-8")
        result = {
            "phase": "unknown",
            "health": "unknown",
            "health_icon": "⚪",
            "last_activity": None,
            "in_progress": [],
            "blocked": [],
            "recent_entries": [],
        }

        # --- Quick Summary ---
        phase_match = re.search(r"\*\*Phase\*\*:\s*(.+)", text)
        if phase_match:
            raw = phase_match.group(1).strip()
            # Strip emoji health indicators that might be mixed in
            result["phase"] = re.sub(r"[🟢🟡🔴⚪]", "", raw).strip()

        health_match = re.search(r"\*\*Health\*\*:\s*(.+)", text)
        if health_match:
            raw = health_match.group(1).strip()
            result["health"] = raw
            # Extract icon
            icon_match = re.match(r"([🟢🟡🔴⚪])", raw)
            if icon_match:
                result["health_icon"] = icon_match.group(1)

        activity_match = re.search(r"\*\*Last activity\*\*:\s*(.+)", text)
        if activity_match:
            result["last_activity"] = activity_match.group(1).strip()

        # --- Activity Log entries (last 10) ---
        entries = re.findall(
            r"###\s*\[(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})\]\s*[—–\-]\s*(.+?)(?=\n###|\n---|\Z)",
            text, re.DOTALL
        )

        for ts, body in entries[-10:]:
            entry = {
                "timestamp": ts.strip(),
                "summary": body.split("\n")[0].strip(),
                "type": "",
                "status": "",
                "what_done": "",
                "what_next": "",
                "blockers": "none",
                "files_changed": "",
            }

            for key, pattern in [
                ("type", r"\*\*Type\*\*:\s*(.+)"),
                ("status", r"\*\*Status\*\*:\s*(.+)"),
                ("what_done", r"\*\*What was done\*\*:\s*(.+)"),
                ("what_next", r"\*\*What'?s next\*\*:\s*(.+)"),
                ("blockers", r"\*\*Blockers?\*\*:\s*(.+)"),
                ("files_changed", r"\*\*Files changed\*\*:\s*(.+)"),
            ]:
                m = re.search(pattern, body)
                if m:
                    entry[key] = m.group(1).strip()

            result["recent_entries"].append(entry)

        # Newest first
        result["recent_entries"] = list(reversed(result["recent_entries"]))

        # Separate in-progress and blocked from entries
        for entry in result["recent_entries"]:
            if entry["status"] == "in-progress":
                result["in_progress"].append(entry["summary"])
            if entry["status"] == "blocked" or (
                entry["blockers"] and entry["blockers"].lower() not in ("none", "")
            ):
                result["blocked"].append({
                    "task": entry["summary"],
                    "reason": entry["blockers"],
                })

        return result

    def _parse_plan_md(self, filepath: Path) -> dict:
        """Parse PLAN.md for objective and current phase."""
        if not filepath.exists():
            return {"objective": "", "current_phase": ""}

        text = filepath.read_text(encoding="utf-8")
        result = {"objective": "", "current_phase": ""}

        # Objective
        obj_match = re.search(r"## Objective\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        if obj_match:
            obj = obj_match.group(1).strip()
            obj = re.sub(r"<!--.*?-->", "", obj, flags=re.DOTALL).strip()
            if obj:
                result["objective"] = obj

        # Current Phase
        phase_match = re.search(r"## Current Phase\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
        if phase_match:
            result["current_phase"] = phase_match.group(1).strip()

        return result

    def _parse_decisions_md(self, filepath: Path) -> list[dict]:
        """Parse DECISIONS.md for recent plan changes."""
        if not filepath.exists():
            return []

        text = filepath.read_text(encoding="utf-8")
        decisions = []

        entries = re.findall(
            r"##\s*\[(\d{4}-\d{2}-\d{2})\]\s*[—–\-]\s*(.+?)(?=\n##[^#]|\Z)",
            text, re.DOTALL
        )

        for date, body in entries[-5:]:
            decision = {
                "date": date.strip(),
                "title": body.split("\n")[0].strip(),
            }
            context_match = re.search(r"\*\*Context\*\*:\s*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL)
            if context_match:
                decision["context"] = context_match.group(1).strip()
            decisions.append(decision)

        return list(reversed(decisions))  # newest first

    def read_project(self, project: dict) -> dict:
        """Read full status for a single project. Returns a TaskTray-compatible item."""
        path = Path(project["path"]).expanduser().resolve()
        name = project["name"]
        proj_id = self._make_id(name)

        item = {
            "id": proj_id,
            "title": name,
            "subtitle": "",
            "path": str(path),
            "source": "claude_code",
            "source_method": "status_md",
            "type": "",
            "category": project.get("category", "dev"),
            "status": "active",
            "priority": project.get("priority", "p1"),
            "notes": "",
            "focused": project.get("focused", False),
            "last_modified": None,
            "created_at": None,
            # Claude Code specific fields
            "cc": {
                "phase": "unknown",
                "health": "unknown",
                "health_icon": "⚪",
                "last_activity": None,
                "objective": "",
                "in_progress": [],
                "blocked": [],
                "recent_entries": [],
                "recent_decisions": [],
                "error": None,
            }
        }

        if not path.exists():
            item["cc"]["error"] = f"Project directory not found: {path}"
            item["status"] = "unknown"
            return item

        # Find STATUS.md (try docs/ first, then root)
        status_file = path / "docs" / "STATUS.md"
        if not status_file.exists():
            status_file = path / "STATUS.md"

        # Find PLAN.md
        plan_file = path / "docs" / "PLAN.md"
        if not plan_file.exists():
            plan_file = path / "PLAN.md"

        # Find DECISIONS.md
        decisions_file = path / "docs" / "DECISIONS.md"
        if not decisions_file.exists():
            decisions_file = path / "DECISIONS.md"

        # Parse STATUS.md
        status_data = self._parse_status_md(status_file)
        if "error" in status_data:
            item["cc"]["error"] = status_data["error"]
        else:
            item["cc"]["phase"] = status_data["phase"]
            item["cc"]["health"] = status_data["health"]
            item["cc"]["health_icon"] = status_data["health_icon"]
            item["cc"]["last_activity"] = status_data["last_activity"]
            item["cc"]["in_progress"] = status_data["in_progress"]
            item["cc"]["blocked"] = status_data["blocked"]
            item["cc"]["recent_entries"] = status_data["recent_entries"]

            # Map health to TaskTray status
            if "🔴" in status_data.get("health", ""):
                item["status"] = "blocked"
            elif "🟡" in status_data.get("health", ""):
                item["status"] = "active"
            elif "🟢" in status_data.get("health", ""):
                item["status"] = "active"

            # Set last_modified from most recent entry
            if status_data["recent_entries"]:
                latest = status_data["recent_entries"][0]
                item["last_modified"] = latest["timestamp"]
                item["notes"] = latest.get("what_next", "")

        # Parse PLAN.md
        plan_data = self._parse_plan_md(plan_file)
        item["subtitle"] = plan_data.get("objective", "")[:100]
        item["cc"]["objective"] = plan_data.get("objective", "")

        # Parse DECISIONS.md
        item["cc"]["recent_decisions"] = self._parse_decisions_md(decisions_file)

        return item

    def read_all(self) -> list[dict]:
        """Read status from all configured projects."""
        results = []
        for project in self._projects:
            try:
                item = self.read_project(project)
                results.append(item)
            except Exception as e:
                log.error(f"Error reading project {project.get('name', '?')}: {e}")
                results.append({
                    "id": self._make_id(project.get("name", "unknown")),
                    "title": project.get("name", "Unknown"),
                    "source": "claude_code",
                    "status": "unknown",
                    "cc": {"error": str(e)},
                })
        return results

    def get_summary(self) -> dict:
        """Get a cross-project summary for the dashboard header."""
        items = self.read_all()
        return {
            "total": len(items),
            "on_track": sum(1 for i in items if "🟢" in i.get("cc", {}).get("health", "")),
            "at_risk": sum(1 for i in items if "🟡" in i.get("cc", {}).get("health", "")),
            "blocked": sum(1 for i in items if "🔴" in i.get("cc", {}).get("health", "")),
            "unknown": sum(1 for i in items if "⚪" in i.get("cc", {}).get("health_icon", "⚪")),
            "all_blockers": [
                {"project": i["title"], "task": b["task"], "reason": b["reason"]}
                for i in items
                for b in i.get("cc", {}).get("blocked", [])
            ],
            "active_work": [
                {"project": i["title"], "tasks": i.get("cc", {}).get("in_progress", [])}
                for i in items
                if i.get("cc", {}).get("in_progress")
            ],
        }
