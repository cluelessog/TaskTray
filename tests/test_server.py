"""Tests for server.py."""
import pytest
from unittest.mock import patch, MagicMock


def test_webbrowser_available_at_module_level():
    """webbrowser must be importable from server module scope."""
    import importlib
    import server
    # webbrowser should be in server's global namespace after module-level import
    assert 'webbrowser' in dir(server) or hasattr(server, 'webbrowser')


def test_log_handler_is_rotating():
    """Log handler must be RotatingFileHandler, not plain FileHandler."""
    import logging
    from logging.handlers import RotatingFileHandler
    import server  # triggers logging setup
    log = logging.getLogger("tasktray")
    rotating = [h for h in log.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) >= 1, f"Expected RotatingFileHandler, got: {[type(h).__name__ for h in log.handlers]}"


def test_rotating_handler_config():
    """RotatingFileHandler must have 5MB limit and 3 backups."""
    import logging
    from logging.handlers import RotatingFileHandler
    import server
    log = logging.getLogger("tasktray")
    handler = next(h for h in log.handlers if isinstance(h, RotatingFileHandler))
    assert handler.maxBytes == 5 * 1024 * 1024, f"Expected 5MB, got {handler.maxBytes}"
    assert handler.backupCount == 3, f"Expected 3 backups, got {handler.backupCount}"
