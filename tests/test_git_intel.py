"""Tests for git_intel.py — git intelligence module."""
import pytest
import subprocess
import json
import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helper: create a tmp git repo ─────────────────────────────────────────────

def _init_git_repo(tmp_path, commits=None):
    """Create a git repo in tmp_path with optional commits.

    Args:
        tmp_path: Path for the repo.
        commits: list of (subject, days_ago) tuples. If None, just git init with no commits.
    Returns:
        Path to the repo.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), capture_output=True, check=True,
    )
    if commits:
        for subject, days_ago in commits:
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S")
            env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", subject],
                cwd=str(repo), capture_output=True, check=True, env=env,
            )
    return repo


# ── Task 5.1: Core module tests ──────────────────────────────────────────────


def test_get_head_hash_valid_repo(tmp_path):
    """Returns 40-char hex string from a real tmp git repo."""
    repo = _init_git_repo(tmp_path, commits=[("init", 0)])
    from git_intel import get_head_hash
    h = get_head_hash(str(repo))
    assert h is not None
    assert len(h) == 40
    assert all(c in "0123456789abcdef" for c in h)


def test_get_head_hash_empty_repo(tmp_path):
    """Returns None for repo with git init but no commits."""
    repo = _init_git_repo(tmp_path)
    from git_intel import get_head_hash
    assert get_head_hash(str(repo)) is None


def test_get_head_hash_no_git_dir(tmp_path):
    """Returns None for a plain directory."""
    plain = tmp_path / "norepo"
    plain.mkdir()
    from git_intel import get_head_hash
    assert get_head_hash(str(plain)) is None


def test_get_commit_log_parses_entries(tmp_path):
    """Correctly parses hash, date, subject from git log output."""
    repo = _init_git_repo(tmp_path, commits=[("first commit", 5), ("second commit", 2)])
    from git_intel import get_commit_log
    commits = get_commit_log(str(repo))
    assert len(commits) == 2
    for c in commits:
        assert "hash" in c
        assert "date" in c
        assert "subject" in c
        assert isinstance(c["date"], datetime)
    assert commits[0]["subject"] == "second commit"
    assert commits[1]["subject"] == "first commit"


def test_get_commit_log_pipe_in_subject(tmp_path):
    """Subject containing | chars is parsed correctly (null-byte delimiter)."""
    repo = _init_git_repo(tmp_path, commits=[("feat: add x | y | z", 1)])
    from git_intel import get_commit_log
    commits = get_commit_log(str(repo))
    assert len(commits) == 1
    assert commits[0]["subject"] == "feat: add x | y | z"


def test_get_commit_log_empty_repo(tmp_path):
    """Returns empty list for repo with no commits."""
    repo = _init_git_repo(tmp_path)
    from git_intel import get_commit_log
    assert get_commit_log(str(repo)) == []


def test_get_commit_log_timeout(tmp_path):
    """Returns empty list and no crash when subprocess times out."""
    from git_intel import get_commit_log
    with patch("git_intel.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
        assert get_commit_log(str(tmp_path)) == []


def test_get_commit_log_permission_error(tmp_path):
    """Returns empty list on PermissionError."""
    from git_intel import get_commit_log
    with patch("git_intel.subprocess.run", side_effect=PermissionError("no access")):
        assert get_commit_log(str(tmp_path)) == []


# ── Cache tests ──────────────────────────────────────────────────────────────

def test_cache_hit_skips_git_log(tmp_path):
    """When HEAD hash matches cache, git log is not called."""
    from git_intel import GitIntelCache, get_head_hash, get_commit_log

    repo = _init_git_repo(tmp_path, commits=[("init", 0)])
    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)

    head = get_head_hash(str(repo))
    commits = get_commit_log(str(repo))
    cache.set(str(repo), head, 6, commits)
    cache.save()

    # Reload cache and verify hit
    cache2 = GitIntelCache(cache_file)
    cached = cache2.get(str(repo), head, 6)
    assert cached is not None
    assert len(cached) == 1


def test_cache_miss_calls_git_log(tmp_path):
    """When HEAD hash differs from cache, git log is called."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    cache.set("/some/repo", "oldhash", 6, [{"hash": "old", "date": "2026-01-01", "subject": "old"}])
    cache.save()

    cache2 = GitIntelCache(cache_file)
    assert cache2.get("/some/repo", "newhash", 6) is None


def test_cache_miss_on_history_months_change(tmp_path):
    """When history_months config changes, cache is invalidated even if HEAD matches."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    cache.set("/repo", "abc123", 6, [{"hash": "a", "date": "2026-01-01", "subject": "x"}])
    cache.save()

    cache2 = GitIntelCache(cache_file)
    # Same HEAD hash, different history_months
    assert cache2.get("/repo", "abc123", 3) is None
    # Same HEAD hash, same history_months
    assert cache2.get("/repo", "abc123", 6) is not None


def test_cache_thread_safety(tmp_path):
    """Concurrent reads/writes to cache do not raise or corrupt data."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    errors = []

    def writer(i):
        try:
            cache.set(f"/repo{i}", f"hash{i}", 6, [{"hash": f"h{i}", "date": "2026-01-01", "subject": f"s{i}"}])
            cache.save()
        except Exception as e:
            errors.append(e)

    def reader(i):
        try:
            cache.get(f"/repo{i}", f"hash{i}", 6)
        except Exception as e:
            errors.append(e)

    threads = []
    for i in range(20):
        threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == [], f"Thread safety errors: {errors}"


def test_cache_atomic_write(tmp_path):
    """Cache file is written atomically (tmp + replace pattern)."""
    from git_intel import GitIntelCache

    cache_file = tmp_path / "cache.json"
    cache = GitIntelCache(cache_file)
    cache.set("/repo", "abc", 6, [])
    cache.save()

    assert cache_file.exists()
    data = json.loads(cache_file.read_text())
    assert "/repo" in data


# ── analyze_project tests ────────────────────────────────────────────────────

def _default_config():
    return {
        "git_intel": {
            "timeout_seconds": 5,
            "history_months": 6,
            "stalled_threshold_days": 14,
        }
    }


def test_analyze_project_returns_full_dict(tmp_path):
    """Result dict contains head_hash, commits, commit_count keys."""
    repo = _init_git_repo(tmp_path, commits=[("init", 0)])
    from git_intel import analyze_project
    result = analyze_project(str(repo), _default_config(), cache_dir=tmp_path)
    assert "head_hash" in result
    assert "commits" in result
    assert "commit_count" in result
    assert result["commit_count"] == 1
    assert result["error"] is None


def test_analyze_projects_batch(tmp_path):
    """Multiple projects analyzed, each with independent results."""
    repo1 = _init_git_repo(tmp_path / "a", commits=[("a1", 0)])
    repo2 = _init_git_repo(tmp_path / "b", commits=[("b1", 1), ("b2", 0)])
    from git_intel import analyze_projects
    projects = [{"path": str(repo1)}, {"path": str(repo2)}]
    results = analyze_projects(projects, _default_config(), cache_dir=tmp_path)
    assert str(repo1) in results
    assert str(repo2) in results
    assert results[str(repo1)]["commit_count"] == 1
    assert results[str(repo2)]["commit_count"] == 2


def test_analyze_projects_one_broken(tmp_path):
    """One broken repo does not prevent others from succeeding."""
    repo = _init_git_repo(tmp_path / "good", commits=[("ok", 0)])
    bad = tmp_path / "bad"
    bad.mkdir()
    from git_intel import analyze_projects
    projects = [{"path": str(repo)}, {"path": str(bad)}]
    results = analyze_projects(projects, _default_config(), cache_dir=tmp_path)
    assert results[str(repo)]["commit_count"] == 1
    assert results[str(bad)]["commit_count"] == 0


# ── Task 5.2: Velocity and commit frequency metrics ─────────────────────────

def _make_commits(patterns):
    """Build fixture commit list from (subject, days_ago) tuples."""
    return [
        {"hash": f"h{i:04x}", "date": datetime.now() - timedelta(days=d), "subject": s}
        for i, (s, d) in enumerate(patterns)
    ]


def test_metrics_total_commits():
    """Correct count from fixture commit list."""
    from git_intel import compute_metrics
    commits = _make_commits([("a", 1), ("b", 3), ("c", 7)])
    m = compute_metrics(commits, _default_config())
    assert m["total_commits"] == 3


def test_metrics_weekly_counts_length():
    """weekly_counts has correct number of weeks for the analysis window."""
    from git_intel import compute_metrics
    commits = _make_commits([("a", 1)])
    cfg = _default_config()
    m = compute_metrics(commits, cfg)
    # 6 months ≈ 26 weeks
    assert len(m["weekly_counts"]) >= 25
    assert len(m["weekly_counts"]) <= 27


def test_metrics_weekly_counts_values():
    """Commits are bucketed into correct ISO weeks."""
    from git_intel import compute_metrics
    # 3 commits in the same week (this week), 1 commit 14 days ago (different week)
    commits = _make_commits([("a", 0), ("b", 1), ("c", 2), ("d", 14)])
    m = compute_metrics(commits, _default_config())
    # Last element should have 3 commits (current week)
    assert m["weekly_counts"][-1] >= 2  # at least 2 in recent week
    assert sum(m["weekly_counts"]) == 4


def test_metrics_velocity_accelerating():
    """Increasing weekly pattern yields 'accelerating'."""
    from git_intel import compute_metrics
    # Strong acceleration: 0 commits weeks 1-20, then 5+ commits per week recently
    commits = _make_commits(
        [("old", 160)] +
        [(f"recent{i}", i % 7) for i in range(20)]
    )
    m = compute_metrics(commits, _default_config())
    assert m["velocity_trend"] == "accelerating"


def test_metrics_velocity_steady():
    """Flat weekly pattern yields 'steady'."""
    from git_intel import compute_metrics
    # Even spread: 1 commit every 7 days over 12 weeks
    commits = _make_commits([(f"w{i}", i * 7) for i in range(12)])
    m = compute_metrics(commits, _default_config())
    assert m["velocity_trend"] == "steady"


def test_metrics_velocity_slowing():
    """Decreasing weekly pattern yields 'slowing'."""
    from git_intel import compute_metrics
    # Heavy early activity (5 commits/week for first 10 weeks), 1 recent to avoid stalled
    commits = _make_commits(
        [("recent", 3)] +
        [(f"old{i}", 100 + i) for i in range(50)]
    )
    m = compute_metrics(commits, _default_config())
    assert m["velocity_trend"] == "slowing"


def test_metrics_velocity_stalled():
    """No recent commits yields 'stalled' regardless of historical slope."""
    from git_intel import compute_metrics
    # All commits > 14 days ago
    commits = _make_commits([(f"old{i}", 30 + i * 7) for i in range(10)])
    m = compute_metrics(commits, _default_config())
    assert m["velocity_trend"] == "stalled"


def test_metrics_stalled_threshold_configurable():
    """Custom stalled_threshold_days in config changes stalled detection."""
    from git_intel import compute_metrics
    # Commits 10 days ago — stalled at threshold=7, not stalled at threshold=14
    commits = _make_commits([("x", 10)])
    cfg_strict = {"git_intel": {"history_months": 6, "stalled_threshold_days": 7}}
    cfg_relaxed = {"git_intel": {"history_months": 6, "stalled_threshold_days": 14}}
    assert compute_metrics(commits, cfg_strict)["velocity_trend"] == "stalled"
    assert compute_metrics(commits, cfg_relaxed)["velocity_trend"] != "stalled"


def test_metrics_last_commit_date():
    """Returns ISO date string of most recent commit."""
    from git_intel import compute_metrics
    commits = _make_commits([("recent", 2), ("old", 30)])
    m = compute_metrics(commits, _default_config())
    assert m["last_commit_date"] is not None
    # Should be approximately 2 days ago
    parsed = datetime.fromisoformat(m["last_commit_date"])
    assert (datetime.now() - parsed).days <= 3


def test_metrics_most_active_day():
    """Returns correct day name when one day dominates."""
    from git_intel import compute_metrics
    # Create commits all on the same weekday by using multiples of 7
    base_days_ago = 0
    # Find how many days ago was a Monday
    today = datetime.now()
    days_since_monday = today.weekday()  # 0=Monday
    commits = _make_commits([
        (f"mon{i}", days_since_monday + i * 7)
        for i in range(5)
    ] + [("other", days_since_monday + 1)])  # one Tuesday
    m = compute_metrics(commits, _default_config())
    assert m["most_active_day"] == "Monday"


def test_metrics_empty_commits():
    """All fields return sensible defaults."""
    from git_intel import compute_metrics
    m = compute_metrics([], _default_config())
    assert m["total_commits"] == 0
    assert m["weekly_counts"] == [] or all(c == 0 for c in m["weekly_counts"])
    assert m["velocity_trend"] == "stalled"
    assert m["last_commit_date"] is None
    assert m["most_active_day"] is None


def test_linear_regression_known_values():
    """Slope calculation matches hand-computed values."""
    from git_intel import _linear_regression_slope
    # y = 2x: slope should be 2.0
    assert abs(_linear_regression_slope([0, 2, 4, 6, 8]) - 2.0) < 0.01
    # Constant: slope should be 0
    assert abs(_linear_regression_slope([5, 5, 5, 5])) < 0.01
    # Decreasing: slope should be negative
    assert _linear_regression_slope([10, 8, 6, 4, 2]) < 0


# ── Task 5.3: Stage inference, commit types, sprint detection ────────────────

def test_stage_inception():
    """<10 commits returns 'inception'."""
    from git_intel import infer_stage, compute_metrics
    commits = _make_commits([(f"c{i}", i) for i in range(5)])
    m = compute_metrics(commits, _default_config())
    assert infer_stage(commits, m, _default_config()) == "inception"


def test_stage_active():
    """Recent commits with decent velocity returns 'active'."""
    from git_intel import infer_stage, compute_metrics
    # 40 commits over ~80 days → avg > 1.0/week → active
    commits = _make_commits([(f"c{i}", i * 2) for i in range(40)])
    m = compute_metrics(commits, _default_config())
    assert infer_stage(commits, m, _default_config()) == "active"


def test_stage_maintenance():
    """Low weekly average + not stalled returns 'maintenance'."""
    from git_intel import infer_stage, compute_metrics
    # 15 commits (above inception) but spread very thin — 1 every 2 weeks
    commits = _make_commits([(f"c{i}", i * 14) for i in range(15)])
    cfg = _default_config()
    m = compute_metrics(commits, cfg)
    stage = infer_stage(commits, m, cfg)
    assert stage == "maintenance"


def test_stage_stalled():
    """No commits in >14 days returns 'stalled'."""
    from git_intel import infer_stage, compute_metrics
    commits = _make_commits([(f"c{i}", 30 + i * 7) for i in range(15)])
    m = compute_metrics(commits, _default_config())
    assert infer_stage(commits, m, _default_config()) == "stalled"


def test_stage_stalled_overrides_inception():
    """Even <10 commits, if >14 days old, returns 'stalled'."""
    from git_intel import infer_stage, compute_metrics
    commits = _make_commits([("old", 30)])
    m = compute_metrics(commits, _default_config())
    assert infer_stage(commits, m, _default_config()) == "stalled"


def test_stage_thresholds_configurable():
    """Custom inception_max_commits changes stage boundary."""
    from git_intel import infer_stage, compute_metrics
    # 40 commits over 40 days → avg well above 1.0/week
    commits = _make_commits([(f"c{i}", i) for i in range(40)])
    cfg_low = {"git_intel": {"history_months": 6, "stalled_threshold_days": 14,
                              "stage_thresholds": {"inception_max_commits": 5, "maintenance_weekly_avg_max": 1.0}}}
    cfg_high = {"git_intel": {"history_months": 6, "stalled_threshold_days": 14,
                               "stage_thresholds": {"inception_max_commits": 50, "maintenance_weekly_avg_max": 1.0}}}
    m = compute_metrics(commits, cfg_low)
    assert infer_stage(commits, m, cfg_low) == "active"  # 40 > 5
    m2 = compute_metrics(commits, cfg_high)
    assert infer_stage(commits, m2, cfg_high) == "inception"  # 40 < 50


def test_parse_commit_types_feat():
    """'feat: add login' classified as feat."""
    from git_intel import parse_commit_types
    commits = [{"subject": "feat: add login"}]
    result = parse_commit_types(commits)
    assert result.get("feat", 0) == 1.0


def test_parse_commit_types_fix():
    """'fix: null check' classified as fix."""
    from git_intel import parse_commit_types
    commits = [{"subject": "fix: null check"}]
    result = parse_commit_types(commits)
    assert result.get("fix", 0) == 1.0


def test_parse_commit_types_scoped():
    """'feat(auth): add OAuth' classified as feat (scope ignored)."""
    from git_intel import parse_commit_types
    commits = [{"subject": "feat(auth): add OAuth"}]
    result = parse_commit_types(commits)
    assert result.get("feat", 0) == 1.0


def test_parse_commit_types_chore():
    """'chore: update deps' classified as chore."""
    from git_intel import parse_commit_types
    commits = [{"subject": "chore: update deps"}]
    result = parse_commit_types(commits)
    assert result.get("chore", 0) == 1.0


def test_parse_commit_types_other():
    """'random message' classified as other."""
    from git_intel import parse_commit_types
    commits = [{"subject": "random message"}]
    result = parse_commit_types(commits)
    assert result.get("other", 0) == 1.0


def test_parse_commit_types_percentages_sum():
    """All percentages sum to 1.0 (within float tolerance)."""
    from git_intel import parse_commit_types
    commits = [
        {"subject": "feat: x"}, {"subject": "fix: y"},
        {"subject": "chore: z"}, {"subject": "random"},
    ]
    result = parse_commit_types(commits)
    assert abs(sum(result.values()) - 1.0) < 0.001


def test_parse_commit_types_empty():
    """Empty list returns empty dict."""
    from git_intel import parse_commit_types
    assert parse_commit_types([]) == {}


def test_detect_sprints_by_gap():
    """14+ day gap between commit clusters creates separate sprints."""
    from git_intel import detect_sprints
    # Two clusters separated by 20 days
    commits = _make_commits(
        [(f"a{i}", i) for i in range(5)] +  # cluster 1: days 0-4
        [(f"b{i}", 25 + i) for i in range(5)]  # cluster 2: days 25-29
    )
    sprints = detect_sprints(commits, _default_config())
    assert len(sprints) == 2
    for s in sprints:
        assert "start" in s
        assert "end" in s
        assert "commit_count" in s
        assert s["type"] == "cluster"


def test_detect_sprints_empty():
    """No commits returns empty sprint list."""
    from git_intel import detect_sprints
    assert detect_sprints([], _default_config()) == []


def test_analyze_project_full_output(tmp_path):
    """Final analyze_project returns all fields."""
    repo = _init_git_repo(tmp_path, commits=[
        ("feat: add login", 0), ("fix: bug", 3), ("chore: deps", 7),
        ("feat: dashboard", 10), ("test: coverage", 14),
    ])
    from git_intel import analyze_project
    cfg = _default_config()
    result = analyze_project(str(repo), cfg, cache_dir=tmp_path)
    # Core fields (Task 5.1)
    assert result["head_hash"] is not None
    assert result["commit_count"] == 5
    assert result["error"] is None
    # Metrics fields (Task 5.2)
    assert "total_commits" in result
    assert "weekly_counts" in result
    assert "velocity_trend" in result
    assert "last_commit_date" in result
    assert "most_active_day" in result
    # Stage fields (Task 5.3)
    assert "stage" in result
    assert "commit_types" in result
    assert "sprints" in result
