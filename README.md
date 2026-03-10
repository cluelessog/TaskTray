# ◆ TASKTRAY

A local-first personal dashboard that auto-discovers projects from your disk and syncs with your Obsidian vault. Runs as a system tray app on Windows.

## Quick Start

```bash
# 1. Clone/copy this folder to your machine
# 2. Edit config.yaml (set your paths)
# 3. Run setup
setup.bat

# 4. Start the dashboard
start.bat
```

The dashboard opens at `http://127.0.0.1:9876` and a system tray icon (◆) appears — double-click it anytime to reopen.

## How It Works

TaskTray pulls items from **three sources** and merges them into one dashboard:

### 1. Disk Scanner
Automatically discovers projects by walking your configured directories and looking for marker files (`.git`, `package.json`, `Cargo.toml`, `pyproject.toml`, etc.).

Configure in `config.yaml`:
```yaml
scanner:
  scan_dirs:
    - "D:/Projects"
    - "D:/Code"
  max_depth: 3
```

### 2. Obsidian Integration (Three Methods)

#### Method A: Dashboard Folder
Drop any `.md` file into your vault's `Dashboard/` folder. It becomes a dashboard item automatically.

```
MyVault/
  Dashboard/
    stark-trading-system.md    ← auto-discovered
    angular-teaching-plan.md   ← auto-discovered
```

#### Method B: Tags
Add tags anywhere in any note:

```markdown
Working on the new scoring module for Stark.
#dashboard/project

Had an idea for monetizing signals.
#dashboard/idea
```

Supported tags: `#dashboard/project`, `#dashboard/idea`, `#dashboard/task`, `#dashboard/learning`

#### Method C: YAML Frontmatter
Add frontmatter to any note for full control:

```markdown
---
dashboard: true
title: "Stark — Trading Intelligence System"
status: active       # active | paused | backlog | done
priority: p0         # p0 | p1 | p2 | p3
category: dev        # dev | trading | teaching | ideas | personal | learning
focused: true        # pin to daily focus
---

## Current Sprint
Working on binary scoring automation...
```

**You can mix and match all three methods.** A note in the Dashboard folder with frontmatter gets the best of both worlds.

### 3. Manual Items
Add items directly through the dashboard UI — quick capture bar or full form.

## Obsidian Quickstart Templates

### Project Note
```markdown
---
dashboard: true
status: active
priority: p0
category: dev
---

# IdeaEngine

Automated business idea discovery and validation system.

## Current Focus
- Reddit mining pipeline
- Scoring algorithm refinement
```

### Idea Note
```markdown
---
dashboard: true
status: backlog
priority: p2
category: ideas
---

# Paid Signal Subscription

Monetize Stark's daily focus list as a subscription product.
```

### Quick Tag (no frontmatter needed)
```markdown
# Random Thought

Should explore building a VS Code extension for trade logging.
#dashboard/idea
```

## Dashboard Features

- **Board View** — Kanban columns by status (Active / Paused / Backlog)
- **List View** — Sorted by priority and status
- **Focus View** — Only starred items for today's priorities
- **Quick Capture** — Type + Enter to add items instantly
- **Source Badges** — See where each item came from (💽 disk / 📝 obsidian / ✏️ manual)
- **Status Cycling** — Click the status badge to rotate through states
- **Background Sync** — Auto-refreshes from disk and Obsidian every 30s
- **Manual Sync** — Hit ⟳ to force a refresh

## Auto-Start with Windows

Run `add-to-startup.bat` to launch TaskTray automatically when Windows boots (runs silently in the background).

## File Structure

```
TaskTray/
├── config.yaml          # Your configuration
├── server.py            # Main server (Flask + tray + sync)
├── scanner.py           # Disk project discovery
├── obsidian_reader.py   # Obsidian vault reader
├── store.py             # Data store + persistence
├── static/
│   └── index.html       # Dashboard UI
├── data/                # Auto-created, stores manual items + overrides
│   ├── manual_items.json
│   └── overrides.json
├── setup.bat            # One-time setup
├── start.bat            # Launch script
├── add-to-startup.bat   # Add to Windows startup
└── requirements.txt     # Python dependencies
```

## Configuration Reference

See `config.yaml` for all options. Key settings:

| Setting | Description |
|---|---|
| `scanner.scan_dirs` | Directories to scan for projects |
| `scanner.max_depth` | How deep to look (default: 3) |
| `scanner.markers` | Files that indicate a project root |
| `obsidian.vault_path` | Path to your Obsidian vault |
| `obsidian.dashboard_folder` | Folder name for method A (default: "Dashboard") |
| `obsidian.tags` | Tags to look for in method B |
| `obsidian.watch_interval_seconds` | How often to re-sync (default: 5) |
| `server.port` | Dashboard port (default: 9876) |
