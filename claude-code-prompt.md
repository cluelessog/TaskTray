# CMD Center — Claude Code Session Prompt

Paste everything below into your Claude Code session:

---

I'm building **CMD Center** — a local-first personal dashboard that runs as a Windows system tray app. The project is already scaffolded and I need your help iterating on it.

## What it does
- **Disk Scanner**: Auto-discovers projects by walking configured directories looking for markers (`.git`, `package.json`, `Cargo.toml`, `pyproject.toml`, `tauri.conf.json`, etc.)
- **Obsidian Integration** (3 methods simultaneously):
  1. **Dashboard folder**: Any `.md` file in `Dashboard/` folder becomes an item
  2. **Tags**: Notes with `#dashboard/project`, `#dashboard/idea`, `#dashboard/task`, `#dashboard/learning`
  3. **YAML frontmatter**: Notes with `dashboard: true` plus optional `status`, `priority`, `category`, `focused` fields
- **Manual items**: Quick capture bar + full form in the UI
- **System tray**: `pystray` icon on Windows taskbar, double-click to open dashboard
- **Background sync**: Re-scans disk + Obsidian every 30 seconds
- **REST API**: Flask server at `localhost:9876`

## Tech Stack
- Python 3.10+ (Flask, flask-cors, pyyaml, pystray, Pillow)
- Vanilla HTML/CSS/JS frontend (single `static/index.html`)
- JSON file persistence (`data/manual_items.json`, `data/overrides.json`)
- No database — flat file storage

## File Structure
```
cmd-center/
├── config.yaml          # User configuration (scan dirs, vault path, categories)
├── server.py            # Flask server + system tray + background sync orchestration
├── scanner.py           # Disk project discovery (walks dirs, detects project types)
├── obsidian_reader.py   # Obsidian vault reader (folder + tags + frontmatter)
├── store.py             # DataStore class — merges all sources, persists manual items + overrides
├── static/
│   └── index.html       # Full dashboard UI (vanilla JS, no framework)
├── data/                # Auto-created at runtime
│   ├── manual_items.json
│   └── overrides.json
├── setup.bat            # One-time setup (venv + deps)
├── start.bat            # Launch script
├── add-to-startup.bat   # Adds to Windows startup via VBS
└── requirements.txt
```

## API Endpoints
- `GET  /api/items`       — All items (merged, filtered)
- `POST /api/items`       — Add manual item
- `PATCH /api/items/:id`  — Update item (direct for manual, override for auto-discovered)
- `DELETE /api/items/:id`  — Delete/hide item
- `GET  /api/stats`       — Dashboard statistics
- `POST /api/sync`        — Force re-sync
- `GET  /api/config`      — Current config (sanitized)

## Data Model (per item)
```json
{
  "id": "disk_a1b2c3d4",
  "title": "Stark",
  "subtitle": "Trading Intelligence System",
  "path": "D:/Projects/stark",
  "source": "disk|obsidian|manual",
  "source_method": "folder|tag|frontmatter",  // obsidian only
  "type": "tauri|python|rust|node|react|angular",
  "category": "dev|trading|teaching|ideas|personal|learning",
  "status": "active|paused|backlog|done",
  "priority": "p0|p1|p2|p3",
  "notes": "Free text",
  "focused": true,
  "last_modified": "ISO datetime",
  "created_at": "ISO datetime"
}
```

## Design Aesthetic
Dark terminal/industrial theme:
- Background: `#080d14` with subtle animated CSS grid lines in cyan
- Cards: `#0c1520` with colored left border per category
- Accent: `#00e5cc` (cyan) primary, `#ff9f43` (orange), `#b088f9` (purple), `#0be881` (green), `#fdcb6e` (yellow)
- Fonts: IBM Plex Mono (monospace UI elements) + Outfit (body text)
- Source indicators on each card: ⬡ disk / ◈ obsidian / ✎ manual

## Obsidian Integration — Full Specification

### Overview
The dashboard reads from my Obsidian vault using three methods simultaneously. Notes can be picked up by any method — if a note matches multiple methods, it's deduplicated by file path. The `obsidian_reader.py` module handles all three.

### config.yaml — Obsidian Section
```yaml
obsidian:
  vault_path: "D:/Obsidian/MyVault"       # Absolute path to vault root
  dashboard_folder: "Dashboard"             # Folder name for Method 1
  tags:                                     # Tags for Method 2
    - "#dashboard/project"
    - "#dashboard/idea"
    - "#dashboard/task"
    - "#dashboard/learning"
  frontmatter_key: "dashboard"             # Key for Method 3
  watch: true
  watch_interval_seconds: 5
```

### Method 1: Dashboard Folder
Any `.md` file placed inside `{vault_path}/Dashboard/` (or subfolders) automatically becomes a dashboard item. Title is extracted from frontmatter > first H1 > filename. This is the lowest-friction method — just drop a file.

**Expected vault structure:**
```
MyVault/
├── Dashboard/                    ← watched folder
│   ├── stark.md                  ← auto-discovered
│   ├── ideaengine.md             ← auto-discovered
│   ├── Projects/                 ← subfolders work too
│   │   └── angular-teaching.md
│   └── Ideas/
│       └── paid-signals.md
├── Daily Notes/                  ← NOT scanned (unless tagged)
├── Trading/                      ← NOT scanned (unless tagged)
└── .obsidian/                    ← always skipped
```

**Minimal Dashboard folder note:**
```markdown
# Stark — Trading Intelligence System

Automate binary scoring, reduce nightly prep to under 10 minutes.
Tauri + React + SQLite. Angel One Smart API integration.
```
That's it — no frontmatter needed. Title comes from H1, first paragraph becomes the notes/summary.

**Dashboard folder note with full frontmatter:**
```markdown
---
title: "Stark — Trading Intelligence System"
status: active
priority: p0
category: dev
focused: true
---

Automate binary scoring system across 12-13 subsections.
8+ point threshold for daily focus list.

## Current Sprint
- Pivot Location graduated scoring
- NSE public API integration
- 8 PM / 9 AM scheduled workflows
```

### Method 2: Tags
Notes anywhere in the vault with matching tags get picked up. Tags can be inline in the note body — no frontmatter required. This is useful for quick capture: just append a tag to any existing note.

**Supported tags:**
- `#dashboard/project` — maps to category: dev
- `#dashboard/idea` — maps to category: ideas  
- `#dashboard/task` — maps to category: dev
- `#dashboard/learning` — maps to category: learning

**Example — tag in an existing note:**
```markdown
# Explore Paid Signal Subscription

Had an idea while reviewing Stark's scoring output — could package
the daily focus list as a subscription product. Target: recurring
passive income from trading expertise.

Need to figure out delivery mechanism — Telegram bot? WhatsApp?

#dashboard/idea
```

**Example — multiple tags (first match wins for category):**
```markdown
# WhatsApp AI Receptionist

WhatsApp Business API + LLM agent for SMB appointment booking.
Indian market focus. Vernacular language support needed.

#dashboard/idea #dashboard/project
```

**Tag parsing rules:**
- Tags must start with `#` preceded by whitespace or start of line
- Nested tags supported: `#dashboard/project`, `#dashboard/idea`
- Tags inside code blocks (``` or `) are ignored
- Tag matching is exact — `#dashboard/projects` (with 's') would NOT match `#dashboard/project`

### Method 3: YAML Frontmatter
Most powerful method — gives full control over all fields. The reader looks for `dashboard: true` in frontmatter.

**Full frontmatter spec:**
```markdown
---
dashboard: true                # Required — triggers pickup
title: "IdeaEngine"            # Optional — overrides H1/filename
status: active                 # Optional — active|paused|backlog|done (default: backlog)
priority: p1                   # Optional — p0|p1|p2|p3 (default: p2)
category: dev                  # Optional — dev|trading|teaching|ideas|personal|learning (default: ideas)
focused: true                  # Optional — pins to Focus view (default: false)
---
```

**Example — project note with frontmatter:**
```markdown
---
dashboard: true
status: active
priority: p1
category: teaching
focused: true
---

# Angular Teaching Plan

12-week structured curriculum for my wife.

## Phase 1: Foundations (Weeks 1-4)
- Components as "design system pieces"
- Templates as "Figma frames that respond to data"
- Bindings as "smart layers"

## Phase 2: Build Something Real (Weeks 5-8)
- Build a portfolio site together
- Services as "shared design tokens"

## Phase 3: Polish & Level Up (Weeks 9-12)
- Routing, lazy loading, deployment
```

**Example — idea note with minimal frontmatter:**
```markdown
---
dashboard: true
category: ideas
---

# Regional Content Repurposing Engine

LLM-powered content repurposing for regional Indian languages.
Take English content → translate + culturally adapt → publish to
vernacular platforms. Target: Hindi, Tamil, Telugu, Marathi.
```

**Example — trading-specific note:**
```markdown
---
dashboard: true
status: active
priority: p1
category: trading
---

# Weekly Portfolio Risk Review

Every Sunday evening:
- Review all open positions in Kite
- Verify GTT stop-losses are in place
- Check position sizing against current capital
- Update Priority 0-3 watchlists
- Log observations in physical notebook
```

### Field Extraction Priority
When parsing a note, fields are resolved in this order:

| Field    | 1st Priority      | 2nd Priority         | 3rd Priority     | Default    |
|----------|-------------------|----------------------|------------------|------------|
| title    | frontmatter.title | First `# H1` in body | Filename (stem)  | —          |
| status   | frontmatter       | —                    | —                | `backlog`  |
| priority | frontmatter       | —                    | —                | `p2`       |
| category | frontmatter       | Inferred from tag    | —                | `ideas`    |
| focused  | frontmatter       | —                    | —                | `false`    |
| notes    | —                 | First paragraph      | —                | `""`       |

### Category Inference from Tags (when no frontmatter category)
- Tag contains "project" → `dev`
- Tag contains "idea" → `ideas`
- Tag contains "task" → `dev`
- Tag contains "learning" → `learning`

### Obsidian Sync Behavior
- `obsidian_reader.py` re-reads the entire vault every `watch_interval_seconds` (default: 5s in config, actual sync loop in server.py runs every 30s)
- Skips: `.obsidian/`, `.trash/`, hidden folders (starting with `.`), `node_modules`
- Deduplicates by file path — if a note is in Dashboard folder AND has a tag, it only appears once
- Dashboard folder items are found first, then tag scan, then frontmatter scan
- Edits made in the dashboard UI to auto-discovered items are stored as **overrides** in `data/overrides.json` — they persist even if the source note changes
- Deleting an auto-discovered item in the dashboard hides it (`_hidden: true` override) — it won't reappear on next sync

### Obsidian Plugin Compatibility
The system reads raw `.md` files — no Obsidian plugin needed. But for convenience, consider:
- **Templater plugin**: Create a template for new dashboard notes with pre-filled frontmatter
- **QuickAdd plugin**: Set up a macro to create a new note in `Dashboard/` folder with one hotkey
- **Dataview plugin**: You can query your dashboard notes within Obsidian itself (separate from CMD Center)

**Suggested Templater template (`Dashboard Note.md`):**
```markdown
---
dashboard: true
title: "{{VALUE:Title}}"
status: backlog
priority: p2
category: {{VALUE:Category (dev/trading/teaching/ideas/personal/learning)}}
focused: false
---

# {{VALUE:Title}}

{{cursor}}
```

### Bidirectional Sync (Future Enhancement)
Currently the sync is **one-way**: Obsidian → Dashboard. Changes made in the dashboard (status, priority, focus) are stored as overrides, NOT written back to the `.md` files. A future enhancement could write frontmatter updates back to the source notes. If implementing this:
- Only update frontmatter fields, never touch body content
- Use a safe YAML writer that preserves existing frontmatter keys
- Add a `last_synced` field to prevent write conflicts
- Make it opt-in via config: `obsidian.write_back: true`

## My Setup
- Windows with WSL support
- Obsidian vault for notes (I use it for trading logs, project notes, ideas, teaching materials)
- Active projects: Stark (Tauri/Rust+React trading app), IdeaEngine (Python), Angular teaching plan
- I use Kite for trading, TradingView/ChartsMaze for charting
- I maintain a physical notebook for trade logging alongside digital notes

## Current State
The full codebase is scaffolded and ready. I need to:
1. First, read all the files in the project to understand the current state
2. Then help me with whatever I ask next

Start by reading the project files so you have full context. The project should be in my current directory or I'll tell you where it is.

---
