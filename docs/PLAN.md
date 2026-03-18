# Plan: TaskTray

> Last updated: 2026-03-18
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
| 9 | Claude Code status integration (cc_status_reader, endpoints, UI) | completed |
| 10 | Scanner cross-platform fixes (WSL paths, depth, marker/ignore) | completed |
| 11 | UI Polish (phase colors, health dots, header, nesting) | completed |
| 12 | Milestones display (checklist, activity, sparklines, what's next) | completed |
| 13 | Phase 7a: Quick Wins (WIP gauge, streak, tray badge, context resume) | not-started |
| 14 | Phase 7b: AI Features (standup, drift alert, health score, focus mode) | not-started |

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

### Claude Code Integration (complete)
- [x] cc_status_reader.py: parses STATUS.md/PLAN.md/DECISIONS.md
- [x] Store merge: CC items merge with disk items by path
- [x] Server endpoints: /api/cc-status, /api/cc-summary, /api/cc-status/<name>
- [x] Frontend: CC summary strip, health dots, phase badges, working-on/blocked
- [x] WSL path normalization (_normalize_to_native)
- [x] read_project_by_name API

### Scanner Cross-Platform Fixes (complete)
- [x] WSL-to-Windows path normalization in _detect_worktree
- [x] Relative gitdir path resolution
- [x] Direct .claude/worktrees/ scan (bypasses depth limit)
- [x] Check markers before filtering ignore_dirs
- [x] Frontend buildGroupedItems path normalization
- [x] Header layout fix (.header-right flex)

### Milestones Display (complete)
- [x] Parse PLAN.md milestones table into cc.milestones
- [x] Pass git_weekly_counts, git_sprints, git_commits, git_most_active_day through server
- [x] Frontend: milestones checklist (✓/○), what's next on card surface
- [x] Frontend: recent activity log, git commit type tags, weekly sparkline
- [x] Worktree board column fix: attach to parent's column regardless of status

### UI Polish (complete)
- [x] Substring-based phase color mapping (getPhaseColor)
- [x] Consistent health dot sizing and alignment
- [x] Header dividers between source badges, CC strip, action buttons
- [x] CC info section with contained background/border
- [x] Softened worktree nesting border and flex gap

## Phase 7: Ambient Intelligence (planned)

> Research-backed features for daily retention. Prioritized by value/effort ratio.

### 7a: Quick Wins (low effort, high value)
- [ ] WIP count gauge — concurrent tasks/branches per project
- [ ] Coding streak counter — tray badge with streak count
- [ ] Tray icon health badge — color-coded by portfolio health (green/yellow/red)
- [ ] Blocker staleness alert — warn when STATUS.md "blocked" entries age >48h
- [ ] Context resume card — "Where was I?" last 3 commits + last STATUS.md entry

### 7b: AI-Powered Features (medium effort, unique moat)
- [ ] AI daily standup summary — "Generate Standup" button feeds docs to Claude API
- [ ] Plan vs reality drift alert — compare PLAN.md milestones against STATUS.md execution
- [ ] Portfolio health score — 4-signal composite (days since commit, milestone progress, WIP, blockers)
- [ ] 90-min focus mode — lock to one project, dim others, auto-log session

### 7c: Engagement & Notifications (medium effort)
- [ ] Morning briefing digest — single daily startup notification summarizing all projects
- [ ] Weekly health report — auto-generated cross-project summary
- [ ] Context switch alert — warn when >5 project switches/day
- [ ] Streak + milestone dual system — long-term retention anchor

### 7d: Strategic (higher effort, future)
- [ ] Agent activity feed — watch .omc/state/ for live Claude Code activity
- [ ] Natural language project query — "What's blocking X?" against local docs
- [ ] Coding hours heatmap — calendar view (needs IDE extension)

## Dependencies

- Python 3.8+, Flask, pystray, pywebview, PyYAML, GitPython
- Obsidian vault path configured in config.yaml
- 381 tests passing (pytest)
