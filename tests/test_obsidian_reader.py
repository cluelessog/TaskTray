"""Tests for obsidian_reader.py encoding handling."""
import pytest
import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian_reader import _read_note

def test_read_note_with_valid_utf8(tmp_path):
    """Valid UTF-8 notes should be read normally."""
    note = tmp_path / "valid.md"
    note.write_text("# Hello\nWorld", encoding="utf-8")
    content, fm = _read_note(note)
    assert content is not None
    assert "Hello" in content

def test_read_note_with_non_utf8_bytes(tmp_path):
    """Notes with non-UTF-8 bytes should be read with replacement chars, not skipped."""
    note = tmp_path / "bad.md"
    note.write_bytes(b"# Title\nHello \xff\xfe world")
    content, fm = _read_note(note)
    assert content is not None, "Note with bad bytes must NOT return None"
    assert "\ufffd" in content, "Replacement character should be present"

def test_read_note_with_frontmatter_and_bad_bytes(tmp_path):
    """Frontmatter should parse even when body has bad bytes."""
    note = tmp_path / "mixed.md"
    note.write_bytes(b"---\ntitle: Test\nstatus: active\n---\nContent \xff here")
    content, fm = _read_note(note)
    assert content is not None
    assert fm is not None
    assert fm.get("title") == "Test"
