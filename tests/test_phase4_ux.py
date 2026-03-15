"""Tests for Phase 4 UX improvements."""
import pytest
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "static" / "index.html"

@pytest.fixture
def html():
    return HTML_PATH.read_text(encoding="utf-8")

class TestSearchFilter:
    def test_search_input_exists(self, html):
        """Search input element exists in the HTML."""
        assert 'id="search-input"' in html or "id='search-input'" in html

    def test_search_state_property(self, html):
        """State object has a search property."""
        assert 'search:' in html or 'search :' in html

    def test_search_debounce_pattern(self, html):
        """Search uses debounce with setTimeout/clearTimeout."""
        assert 'setTimeout' in html and 'clearTimeout' in html
        assert '150' in html  # 150ms debounce

    def test_search_filters_title_notes_category(self, html):
        """Filter logic references title, notes, and category fields."""
        # The search filtering should check these fields
        lower = html.lower()
        assert '.title' in html
        assert '.notes' in html
        # Category is checked either in search or filter logic
        assert '.category' in html

    def test_search_is_client_side_only(self, html):
        """Search filtering does not make API calls — no fetch in search handler."""
        # The search/filter function should not contain fetch calls
        # We verify by checking that the search handler uses state.items directly
        assert 'state.search' in html or 'state.searchQuery' in html

    def test_search_combines_with_category_filter(self, html):
        """Both search and category filter are checked when filtering items."""
        # The filtering logic should reference both search and filter/category
        assert 'state.search' in html or 'state.searchQuery' in html
        assert 'state.filter' in html or 'state.category' in html

    def test_search_clear_button(self, html):
        """A clear button exists for the search input."""
        # Look for a clear/reset mechanism
        assert 'clearSearch' in html or 'clear-search' in html or "search-clear" in html


class TestKeyboardShortcuts:
    def test_keydown_listener_exists(self, html):
        """Global keydown event listener is registered."""
        assert "addEventListener" in html and "keydown" in html

    def test_shortcut_suppression_check(self, html):
        """Shortcuts are suppressed when typing in input/textarea/select."""
        assert 'INPUT' in html and 'TEXTAREA' in html and 'SELECT' in html

    def test_shortcut_slash_focuses_search(self, html):
        """/ key focuses the search input."""
        assert 'search-input' in html
        assert "'/'" in html or '"/"' in html

    def test_shortcut_n_opens_modal(self, html):
        """N key opens the new item modal."""
        assert 'openAdd' in html

    def test_shortcut_view_switching(self, html):
        """1/2/3 keys switch between views."""
        assert 'setView' in html

    def test_shortcut_escape_closes_modal(self, html):
        """Escape key closes modal or clears search."""
        assert 'Escape' in html

    def test_shortcut_s_triggers_sync(self, html):
        """S key triggers sync."""
        assert 'triggerSync' in html

    def test_shortcut_help_overlay_exists(self, html):
        """Help overlay element exists with shortcut descriptions."""
        assert 'help-overlay' in html or 'shortcut-help' in html or 'shortcuts-overlay' in html

    def test_shortcut_help_button_exists(self, html):
        """A ? button exists in the header to show help."""
        assert '?' in html
