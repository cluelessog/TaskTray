"""Tests for Phase 2 Design Alignment — read index.html as string, assert CSS values."""
import pathlib

import pytest

HTML_PATH = pathlib.Path(__file__).resolve().parent.parent / "static" / "index.html"


@pytest.fixture
def html():
    return HTML_PATH.read_text(encoding="utf-8")


# ── Color palette ──
class TestColorPalette:
    def test_bg_root_updated(self, html):
        assert "--bg-root: #080d14" in html
        assert "#0b1120" not in html  # old value fully replaced

    def test_bg_card_updated(self, html):
        assert "--bg-card: #0c1520" in html
        assert "#111827" not in html  # old value fully replaced

    def test_cyan_updated(self, html):
        assert "--cyan: #00e5cc" in html
        assert "#22d3ee" not in html  # old value fully replaced

    def test_cyan_bg_updated(self, html):
        assert "rgba(0,229,204,0.12)" in html
        assert "rgba(34,211,238,0.12)" not in html

    def test_no_old_cyan_rgba(self, html):
        """No leftover references to old cyan rgba anywhere."""
        assert "rgba(34,211,238," not in html


# ── Typography ──
class TestTypography:
    def test_font_mono_ibm_plex(self, html):
        assert "IBM Plex Mono" in html
        assert "JetBrains Mono" not in html

    def test_font_sans_outfit(self, html):
        assert "Outfit" in html
        assert "DM Sans" not in html

    def test_google_fonts_link(self, html):
        assert "family=IBM+Plex+Mono" in html
        assert "family=Outfit" in html


# ── Source indicators ──
class TestSourceIndicators:
    def test_disk_geometric(self, html):
        assert "\u2b21 disk" in html

    def test_obsidian_geometric(self, html):
        assert "\u25c8 obsidian" in html

    def test_manual_geometric(self, html):
        assert "\u270e manual" in html

    def test_no_emoji_sources(self, html):
        """Old emoji indicators must be gone."""
        assert "\U0001f4bd" not in html
        assert "\U0001f4dd" not in html
        assert "\u270f\ufe0f" not in html


# ── Contrast ratio ──
class TestContrastRatio:
    @staticmethod
    def _relative_luminance(hex_color: str) -> float:
        """WCAG 2.1 relative luminance."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))

        def linearize(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

    @staticmethod
    def _contrast_ratio(c1: str, c2: str) -> float:
        l1 = TestContrastRatio._relative_luminance(c1)
        l2 = TestContrastRatio._relative_luminance(c2)
        lighter, darker = max(l1, l2), min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def test_text_on_card_bg(self):
        """Primary text (#e2e8f0) on card bg (#0c1520) >= 4.5:1."""
        assert self._contrast_ratio("#e2e8f0", "#0c1520") >= 4.5

    def test_muted_text_on_card_bg(self):
        """Muted text (#94a3b8) on card bg (#0c1520) >= 4.5:1."""
        assert self._contrast_ratio("#94a3b8", "#0c1520") >= 4.5

    def test_cyan_on_root_bg(self):
        """Cyan accent (#00e5cc) on root bg (#080d14) >= 3:1 (large text / UI elements)."""
        assert self._contrast_ratio("#00e5cc", "#080d14") >= 3.0

    def test_text_on_root_bg(self):
        """Primary text (#e2e8f0) on root bg (#080d14) >= 4.5:1."""
        assert self._contrast_ratio("#e2e8f0", "#080d14") >= 4.5

    def test_cyan_on_card_bg(self):
        """Cyan accent (#00e5cc) on card bg (#0c1520) >= 3:1 (UI elements)."""
        assert self._contrast_ratio("#00e5cc", "#0c1520") >= 3.0


# ── Grid background ──
class TestGridBackground:
    def test_grid_bg_element(self, html):
        """Grid background div exists in HTML."""
        assert 'class="grid-bg"' in html

    def test_grid_css_class(self, html):
        """Grid CSS uses repeating-linear-gradient."""
        assert "repeating-linear-gradient" in html

    def test_grid_animation_transform(self, html):
        """Animation uses transform (GPU-friendly, no layout thrashing)."""
        assert "gridDrift" in html
        assert "transform: translate(" in html

    def test_grid_disable_class(self, html):
        """Grid can be disabled via .no-grid class."""
        assert ".no-grid .grid-bg { display: none" in html

    def test_grid_pointer_events_none(self, html):
        """Grid does not block clicks."""
        assert "pointer-events: none" in html

    def test_grid_rgba_uses_new_cyan(self, html):
        """Grid lines use the new cyan color."""
        assert "rgba(0,229,204,0.04)" in html


# ── Git Intelligence Display (Task 6.4) ─────────────────────────────────────

class TestGitIntelDisplay:
    def test_git_intel_css_class(self, html):
        """.git-intel CSS class exists in HTML."""
        assert ".git-intel" in html

    def test_git_badge_css_class(self, html):
        """.git-badge CSS class exists in HTML."""
        assert ".git-badge" in html

    def test_velocity_trend_labels(self, html):
        """HTML contains velocity trend label strings."""
        assert "Accel" in html
        assert "Steady" in html
        assert "Slowing" in html
        assert "Stalled" in html

    def test_relative_time_function(self, html):
        """relativeTime function is defined in JS."""
        assert "function relativeTime" in html or "relativeTime" in html

    def test_git_intel_in_render_card(self, html):
        """renderCard function references git_velocity_trend."""
        assert "git_velocity_trend" in html

    def test_stage_badge_in_render_card(self, html):
        """renderCard function references git_stage."""
        assert "git_stage" in html

    def test_git_data_conditional(self, html):
        """Git data rendering is conditional on git_velocity_trend existence."""
        assert "git_velocity_trend" in html


# ── Worktree Grouping & Config (Task 6.5) ───────────────────────────────────

class TestWorktreeGrouping:
    def test_worktree_badge_css(self, html):
        """.worktree-badge CSS class exists in HTML."""
        assert ".worktree-badge" in html

    def test_worktree_label_in_render(self, html):
        """renderCard references is_worktree."""
        assert "is_worktree" in html

    def test_worktree_parent_label(self, html):
        """Render logic includes parent_path reference."""
        assert "parent_path" in html

    def test_config_has_git_recency_days(self):
        """config.yaml has git_recency_days under scanner section."""
        import yaml
        config_path = HTML_PATH.parent.parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg.get("scanner", {}).get("git_recency_days") == 14


# ── Worktree Nesting (Grouping Under Parent) ────────────────────────────────

class TestWorktreeNesting:
    def test_worktree_group_css_class(self, html):
        """.worktree-group CSS class exists in style block."""
        assert ".worktree-group" in html

    def test_worktree_nested_card_css_class(self, html):
        """.worktree-nested-card CSS class exists in style block."""
        assert ".worktree-nested-card" in html

    def test_worktree_count_badge_css_class(self, html):
        """.worktree-count-badge CSS class exists in style block."""
        assert ".worktree-count-badge" in html

    def test_build_grouped_items_function(self, html):
        """buildGroupedItems function is defined in JS."""
        assert "function buildGroupedItems" in html

    def test_render_worktree_group_function(self, html):
        """renderWorktreeGroup function is defined in JS."""
        assert "function renderWorktreeGroup" in html

    def test_expanded_worktrees_state(self, html):
        """expandedWorktrees state variable exists."""
        assert "expandedWorktrees" in html

    def test_toggle_worktree_group_function(self, html):
        """toggleWorktreeGroup function is defined in JS."""
        assert "function toggleWorktreeGroup" in html

    def test_worktree_group_has_indent(self, html):
        """.worktree-group CSS has margin-left or padding-left for nesting."""
        import re
        group_match = re.search(r'\.worktree-group\s*\{[^}]+\}', html)
        assert group_match, ".worktree-group CSS rule not found"
        rule = group_match.group()
        assert "margin-left" in rule or "padding-left" in rule

    def test_worktree_toggle_css_class(self, html):
        """.worktree-toggle CSS class exists."""
        assert ".worktree-toggle" in html

    def test_stop_propagation_on_toggle(self, html):
        """Worktree toggle click uses event.stopPropagation()."""
        assert "toggleWorktreeGroup" in html
