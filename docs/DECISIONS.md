# Decisions: TaskTray

> Log of significant plan changes and the reasoning behind them.
> This file survives session restarts — it's the project's institutional memory.

## [2026-03-15] — Worktree grouping: frontend-only with post-filter approach

**Context**: Worktrees (TaskTray-phase3, phase4, etc.) appeared as separate standalone cards cluttering the dashboard. Needed grouping under parent projects.

**Old Plan**: Worktrees render as individual top-level cards with a purple "WT: parent-name" badge.

**New Plan**: Pre-render grouping via `buildGroupedItems()` partitions items into grouped/standalone/orphans. Parent cards get an expandable "N worktrees" count badge. Orphan worktrees (parent not in view) render standalone.

**Rationale**: Frontend-only change avoids backend API changes. Post-filter grouping (not pre-filter) treats grouping as visual convenience, not data coupling — worktrees with different statuses appear independently in their respective columns. `event.stopPropagation()` on badge prevents conflict with card expand. innerHTML rendering model requires pre-render grouping (post-render DOM manipulation would break inline event handlers).

**Impact**: static/index.html and tests/test_design_alignment.py modified. 10 new tests. No backend changes.

## [2026-03-15] — Git intelligence: dual auto-promote guard

**Context**: Phase 6 added git-recency auto-promote alongside existing filesystem auto-promote. Items promoted by filesystem activity were redundantly processed by the git-recency loop.

**Old Plan**: Two independent promotion passes without coordination.

**New Plan**: Git-recency loop skips items that already have `has_recent_activity` (filesystem-promoted). Also added `relativeTime()` NaN guard for malformed date strings.

**Rationale**: Prevents double-write to store for the same item. Architect review caught both issues.

**Impact**: server.py — added `not item.get("has_recent_activity")` guard. static/index.html — added `isNaN(then.getTime())` check.

## [2026-03-15] — Worktree rule: .claude/worktrees/ inside project only

**Context**: Previous worktrees were created as sibling directories outside the project root (e.g., /mnt/d/Projects/TaskTray-phase3), cluttering the parent directory and appearing as separate projects in the scanner.

**Old Plan**: Create worktrees anywhere (typically as sibling dirs).

**New Plan**: All worktrees must be created under `.claude/worktrees/` within the project directory. No merging to master without explicit user approval.

**Rationale**: Keeps worktrees contained, prevents them from being scanned as separate projects, and makes cleanup easier.

**Impact**: CLAUDE.md updated with new worktree rule.
