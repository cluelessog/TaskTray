# TaskTray — Project Rules

## Worktree Rule
Start all work in a new git worktree under `.claude/worktrees/` within the project directory. Never create worktrees outside the project root. Commit only to the worktree branch — do not merge to master without explicit user approval.

## Test-First Rule
When fixing any bug or issue:
1. Write a failing test that reproduces the problem FIRST
2. Then fix the code until all tests pass
3. Never skip this — no fix without a test
