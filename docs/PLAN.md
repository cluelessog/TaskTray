# Plan: TaskTray

> Last updated: 2026-03-15
> Version: 2.0

## Objective

A local-first personal dashboard that auto-discovers projects from disk, syncs with an Obsidian vault, and runs as a Windows system tray app. Merges items from disk scanning, Obsidian (3 methods: dashboard folder, tags, frontmatter), and manual entry into a unified view at localhost:9876. Enriches projects with git intelligence (velocity, stage, commit history) and groups worktrees under parent projects.

## Current Phase

maintenance / feature additions

## Scope

### In Scope
- Disk scanner for project auto-discovery (marker files: .git, package.json, etc.)
- Obsidian integration (dashboard folder, tags, YAML frontmatter)
- Manual item capture via UI
- Board/List/Focus views with source badges
- Background sync (30s interval)
- Windows system tray with auto-start
- Git intelligence enrichment (velocity trends, stage inference, commit parsing)
- Worktree detection and grouping under parent projects
- Search, filter, keyboard shortcuts, drag-and-drop
- JSON/CSV export

### Out of Scope
- Multi-user / network access
- Mobile app
- Cloud sync or remote storage
- Plugin system

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Core: Disk scanner + Flask server + system tray + Obsidian | completed |
| 2 | Phase 1: Critical Stability (thread safety, type hints, 124 tests) | completed |
| 3 | Phase 2: Design Alignment (color palette, typography, grid background) | completed |
| 4 | Phase 3: Robustness (health check, timeouts, caching, auto-promote) | completed |
| 5 | Phase 4: UX Improvements (search, shortcuts, drag-drop, export) | completed |
| 6 | Phase 5: Git Intelligence Core (git_intel module, velocity, stage) | completed |
| 7 | Phase 6: Git Intelligence Integration (worktree detect, frontend, config) | completed |
| 8 | Worktree Grouping (nest worktrees under parent cards) | completed |
| 9 | Claude Code status integration (cc_status_reader.py) | not-started |

## Task Breakdown

### Core Dashboard (complete)
- [x] Flask server + system tray (pystray)
- [x] Disk project scanner
- [x] Obsidian vault reader (3 methods)
- [x] Data store with persistence
- [x] Dashboard UI (board/list/focus views)
- [x] Native window via pywebview

### Phase 1: Critical Stability (complete)
- [x] UTF-8 handling with errors='replace'
- [x] RotatingFileHandler and API input validation
- [x] Comprehensive unit tests (124 tests)
- [x] Type hints and mypy compliance
- [x] Atomic writes, RLock, deepcopy in store.py

### Phase 2: Design Alignment (complete)
- [x] Color palette update (new cyan #00e5cc, card bg #0c1520)
- [x] Typography (IBM Plex Mono + Outfit)
- [x] Animated CSS grid background

### Phase 3: Robustness (complete)
- [x] Health check endpoint (/api/health)
- [x] Scan timeout per directory
- [x] Scan caching with staleness detection
- [x] JSON schema versioning
- [x] Auto-promote backlog items on file activity

### Phase 4: UX Improvements (complete)
- [x] Text search/filter
- [x] Keyboard shortcuts with help overlay
- [x] Drag-and-drop status changes in board view
- [x] JSON/CSV export with formula injection protection

### Phase 5: Git Intelligence Core (complete)
- [x] git_intel module with subprocess git log and HEAD-hash cache
- [x] Velocity metrics and commit frequency analysis
- [x] Stage inference, conventional commit parsing, sprint detection

### Phase 6: Git Intelligence Integration (complete)
- [x] Worktree detection (parent path resolution via .git file)
- [x] Git intel merge into sync pipeline
- [x] Git-recency auto-promote (configurable N days)
- [x] Frontend display (velocity badges, relative time, stage)
- [x] Config integration (git_recency_days in config.yaml)

### Worktree Grouping (complete)
- [x] buildGroupedItems() pre-render grouping logic
- [x] renderWorktreeGroup() with expand/collapse
- [x] All 3 views (board, list, focus) use grouping
- [x] Orphan worktrees render standalone with WT badge

### Next: Claude Code Integration (not started)
- [ ] Add cc_status_reader.py
- [ ] Wire into server.py sync loop
- [ ] Add /api/cc-status and /api/cc-summary endpoints
- [ ] Frontend: CC status panel with health dots, phase badges, activity log

## Open Questions

- How to handle projects found by both disk scanner AND CC reader (merge strategy)

## Dependencies

- Python 3.8+, Flask, pystray, pywebview, PyYAML, GitPython
- Obsidian vault path configured in config.yaml
- 307 tests passing (pytest)
