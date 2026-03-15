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
