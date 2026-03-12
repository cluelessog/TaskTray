"""Tests for pywebview native window integration.

Verifies that server.py uses the correct pywebview API:
- create_window() is called only with valid parameters
- closing event is wired via window.events, not create_window kwarg
- _start_services receives window and stores it
- _on_window_closing returns literal False to prevent destruction
- _wait_for_flask polls TCP port correctly
"""

import inspect
import socket
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest
webview = pytest.importorskip("webview")


# ── Helpers to import server with mocked dependencies ────────────

@pytest.fixture(autouse=True)
def _reset_server():
    """Ensure server module is fresh for each test."""
    # Remove cached module so each test gets a clean import
    if "server" in sys.modules:
        mod = sys.modules["server"]
        # Reset mutable state
        mod._webview_window = None
        mod._is_quitting = False
    yield
    if "server" in sys.modules:
        mod = sys.modules["server"]
        mod._webview_window = None
        mod._is_quitting = False


def _import_server():
    """Import server module (handles first import vs cached)."""
    import server
    return server


class TestCreateWindowAPI:
    """Ensure we only pass valid kwargs to webview.create_window."""

    def test_closing_is_not_a_create_window_param(self):
        """The 'closing' kwarg does NOT exist on create_window.
        If our code passes it, pywebview raises TypeError."""
        sig = inspect.signature(webview.create_window)
        assert "closing" not in sig.parameters, \
            "If pywebview adds 'closing' param in the future, update this test"

    def test_create_window_accepts_width_height(self):
        sig = inspect.signature(webview.create_window)
        assert "width" in sig.parameters
        assert "height" in sig.parameters

    def test_server_does_not_pass_closing_to_create_window(self):
        """Verify server.main() does not pass 'closing' kwarg."""
        server = _import_server()

        mock_window = MagicMock()
        mock_events = MagicMock()
        mock_window.events = mock_events

        with patch.object(webview, 'create_window', return_value=mock_window) as mock_create, \
             patch.object(webview, 'start'):
            server._HAS_WEBVIEW = True
            try:
                server.main()
            except Exception:
                pass  # May fail on webview.start, that's fine

            # The critical check: 'closing' must NOT be in the kwargs
            if mock_create.called:
                _, kwargs = mock_create.call_args
                assert "closing" not in kwargs, \
                    "server.py must NOT pass 'closing' to create_window — use window.events.closing instead"


class TestWindowClosingHandler:
    """Test _on_window_closing returns correct values."""

    def test_returns_false_when_not_quitting(self):
        """Must return literal False (identity-checked by pywebview)."""
        server = _import_server()
        server._is_quitting = False
        server._webview_window = MagicMock()
        result = server._on_window_closing()
        assert result is False, "Must be literal False, not just falsy"
        server._webview_window.hide.assert_called_once()

    def test_returns_true_when_quitting(self):
        server = _import_server()
        server._is_quitting = True
        server._webview_window = MagicMock()
        result = server._on_window_closing()
        assert result is True

    def test_handles_none_window_gracefully(self):
        server = _import_server()
        server._is_quitting = False
        server._webview_window = None
        result = server._on_window_closing()
        assert result is False


class TestWaitForFlask:
    """Test _wait_for_flask TCP polling."""

    def test_returns_true_when_port_open(self):
        """Start a temporary server, verify _wait_for_flask detects it."""
        server = _import_server()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        try:
            result = server._wait_for_flask("127.0.0.1", port, timeout=2.0)
            assert result is True
        finally:
            sock.close()

    def test_returns_false_on_timeout(self):
        """Port that nobody is listening on should timeout."""
        server = _import_server()
        result = server._wait_for_flask("127.0.0.1", 59123, timeout=0.2)
        assert result is False


class TestStartServices:
    """Test _start_services stores window ref and starts threads."""

    def test_stores_window_reference(self):
        server = _import_server()
        mock_window = MagicMock()

        with patch.object(server, 'run_sync'), \
             patch.object(server, 'background_sync'), \
             patch.object(server, '_wait_for_flask', return_value=True), \
             patch.object(server, '_run_tray_detached'), \
             patch.object(server.app, 'run'):
            t = threading.Thread(target=server._start_services, args=(mock_window,))
            t.daemon = True
            t.start()
            t.join(timeout=5)

        assert server._webview_window is mock_window


class TestMainFallback:
    """Test that main() falls back to browser when pywebview is absent."""

    def test_fallback_uses_webbrowser(self):
        server = _import_server()
        original = server._HAS_WEBVIEW
        server._HAS_WEBVIEW = False

        with patch.object(server, 'run_sync'), \
             patch.object(server, 'background_sync'), \
             patch('webbrowser.open') as mock_browser, \
             patch.object(server, 'run_tray'), \
             patch.object(server.app, 'run'):
            t = threading.Thread(target=server.main)
            t.daemon = True
            t.start()
            t.join(timeout=5)

        server._HAS_WEBVIEW = original
        mock_browser.assert_called_once()
