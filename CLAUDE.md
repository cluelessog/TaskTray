<!-- CC-PROJECT-FRAMEWORK-INTEGRATED -->

## 🔴 MANDATORY: Read Before Any Work

Before starting ANY task, you MUST:

1. Read `docs/PLAN.md` — the current strategic plan and scope
2. Read `docs/STATUS.md` — what's done, in progress, and blocked
3. Read `docs/DECISIONS.md` — why things changed (if it exists)
4. Read any spec files in `docs/specs/` — SDD artifacts live here

If any of these files don't exist, create them.

## 🔵 Status Reporting (AUTOMATIC — DO THIS ALWAYS)

After completing any meaningful unit of work (feature, fix, task, subtask), you MUST
update `docs/STATUS.md` by appending an entry in this format:

```
### [YYYY-MM-DD HH:MM] — {{summary}}
- **Type**: feature | fix | refactor | research | planning
- **Status**: completed | in-progress | blocked
- **Files changed**: list of key files
- **What was done**: 1-2 sentence description
- **What's next**: 1-2 sentence description of immediate next step
- **Blockers**: none | description of what's blocking
```

This is NON-NEGOTIABLE. The project dashboard depends on this file being current.

## 🟡 Plan Hierarchy (IMPORTANT)

```
docs/PLAN.md              ← STRATEGIC (master, human-updated)
  │                          Project direction, scope, phases, milestones.
  │
  └── .omc/plans/*        ← TACTICAL (per-feature, OMC-created)
                             Implementation plans for specific features/tasks.
```

Rules:
- ALWAYS read `docs/PLAN.md` first to understand project direction
- NEVER contradict `docs/PLAN.md` in an OMC tactical plan — if conflict, PLAN.md wins
- If the user gives a strategic change (scope, pivot, dropped feature), update `docs/PLAN.md`
- `docs/PLAN.md` feeds the cross-project dashboard. `.omc/plans/` do not.

## 🟠 Plan Change Protocol

When new information arrives that changes the plan:

1. Update `docs/PLAN.md` with the new plan
2. Add an entry to `docs/DECISIONS.md` explaining what/why/impact
3. Update `docs/STATUS.md` to reflect any tasks now invalid/blocked
4. If tasks are in progress that conflict with the new plan, STOP and flag in STATUS.md

<!-- END CC-PROJECT-FRAMEWORK -->
# TaskTray — Project Rules

## Worktree Rule
Start all work in a new git worktree under `.claude/worktrees/` within the project directory. Never create worktrees outside the project root. Commit only to the worktree branch — do not merge to master without explicit user approval.

## Test-First Rule
When fixing any bug or issue:
1. Write a failing test that reproduces the problem FIRST
2. Then fix the code until all tests pass
3. Never skip this — no fix without a test
