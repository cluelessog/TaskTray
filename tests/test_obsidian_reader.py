"""Tests for obsidian_reader.py — encoding handling + extended coverage."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian_reader import (
    _read_note,
    _extract_tags,
    _parse_note,
    _extract_summary,
    read_obsidian_items,
)


# ── _read_note (existing encoding tests) ─────────────────────────────────────

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


# ── _extract_tags ─────────────────────────────────────────────────────────────

def test_extract_tags_basic(tmp_path):
    tags = _extract_tags("Some text #project and #idea here")
    assert "#project" in tags
    assert "#idea" in tags


def test_extract_tags_nested(tmp_path):
    tags = _extract_tags("Note with #dashboard/project tag")
    assert "#dashboard/project" in tags


def test_extract_tags_ignores_code_blocks(tmp_path):
    content = "Normal text\n```\n#not-a-tag\n```\nAfter block"
    tags = _extract_tags(content)
    assert "#not-a-tag" not in tags


def test_extract_tags_ignores_inline_code(tmp_path):
    content = "Use `#not-a-tag` in code"
    tags = _extract_tags(content)
    assert "#not-a-tag" not in tags


def test_extract_tags_empty_content(tmp_path):
    tags = _extract_tags("")
    assert tags == set()


def test_extract_tags_no_tags(tmp_path):
    tags = _extract_tags("Just plain text without any tags")
    assert tags == set()


# ── _parse_note ───────────────────────────────────────────────────────────────

def test_parse_note_title_from_frontmatter(tmp_path):
    note = tmp_path / "test.md"
    note.write_text("---\ntitle: FM Title\n---\n# H1 Title\nBody", encoding="utf-8")
    vault = tmp_path
    item = _parse_note(note, vault, "folder")
    assert item["title"] == "FM Title"


def test_parse_note_title_from_h1(tmp_path):
    note = tmp_path / "test.md"
    note.write_text("# H1 Title\nBody text", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["title"] == "H1 Title"


def test_parse_note_title_from_filename(tmp_path):
    note = tmp_path / "my-cool-note.md"
    note.write_text("Just body text", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["title"] == "my cool note"


def test_parse_note_status_from_frontmatter(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\nstatus: active\n---\nBody", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["status"] == "active"


def test_parse_note_priority_from_frontmatter(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\npriority: p0\n---\nBody", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["priority"] == "p0"


def test_parse_note_category_from_frontmatter(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\ncategory: trading\n---\nBody", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["category"] == "trading"


def test_parse_note_default_status_is_backlog(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("Body only", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["status"] == "backlog"


def test_parse_note_invalid_status_falls_back_to_backlog(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\nstatus: invalid\n---\nBody", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["status"] == "backlog"


def test_parse_note_returns_none_for_unreadable_file(tmp_path):
    note = tmp_path / "ghost.md"
    # File doesn't exist
    item = _parse_note(note, tmp_path, "folder")
    assert item is None


def test_parse_note_source_method_stored(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("Body", encoding="utf-8")
    item = _parse_note(note, tmp_path, "tag")
    assert item["source_method"] == "tag"


def test_parse_note_focused_from_frontmatter(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("---\nfocused: true\n---\nBody", encoding="utf-8")
    item = _parse_note(note, tmp_path, "folder")
    assert item["focused"] is True


def test_parse_note_id_is_stable(tmp_path):
    note = tmp_path / "stable.md"
    note.write_text("Body", encoding="utf-8")
    item1 = _parse_note(note, tmp_path, "folder")
    item2 = _parse_note(note, tmp_path, "folder")
    assert item1["id"] == item2["id"]


# ── _extract_summary ──────────────────────────────────────────────────────────

def test_extract_summary_first_paragraph(tmp_path):
    content = "# Title\n\nFirst paragraph text.\nContinues here.\n\nSecond paragraph."
    summary = _extract_summary(content)
    assert "First paragraph text." in summary
    assert "Second paragraph" not in summary


def test_extract_summary_truncates_at_300(tmp_path):
    content = "A" * 400
    summary = _extract_summary(content)
    assert len(summary) == 300
    assert summary.endswith("...")


def test_extract_summary_skips_headers(tmp_path):
    content = "# Header\n## Sub\nActual content here"
    summary = _extract_summary(content)
    assert summary == "Actual content here"


def test_extract_summary_returns_none_for_empty(tmp_path):
    summary = _extract_summary("")
    assert summary is None


def test_extract_summary_returns_none_for_headers_only(tmp_path):
    summary = _extract_summary("# Header\n## Another")
    assert summary is None


# ── read_obsidian_items ───────────────────────────────────────────────────────

def test_read_obsidian_items_empty_vault(tmp_path):
    config = {"obsidian": {"vault_path": str(tmp_path)}}
    items = read_obsidian_items(config)
    assert items == []


def test_read_obsidian_items_nonexistent_vault():
    config = {"obsidian": {"vault_path": "/nonexistent/vault/path/12345"}}
    items = read_obsidian_items(config)
    assert items == []


def test_read_obsidian_items_dashboard_folder_method(tmp_path):
    dashboard = tmp_path / "Dashboard"
    dashboard.mkdir()
    note = dashboard / "my-project.md"
    note.write_text("# My Project\nSome description", encoding="utf-8")
    config = {
        "obsidian": {
            "vault_path": str(tmp_path),
            "dashboard_folder": "Dashboard",
            "tags": [],
            "frontmatter_key": "dashboard",
        }
    }
    items = read_obsidian_items(config)
    assert len(items) == 1
    assert items[0]["title"] == "My Project"
    assert items[0]["source"] == "obsidian"
    assert items[0]["source_method"] == "folder"


def test_read_obsidian_items_tag_method(tmp_path):
    note = tmp_path / "tagged.md"
    note.write_text("# Tagged Note\n#mytag Some content", encoding="utf-8")
    config = {
        "obsidian": {
            "vault_path": str(tmp_path),
            "dashboard_folder": "Dashboard",
            "tags": ["#mytag"],
            "frontmatter_key": "dashboard",
        }
    }
    items = read_obsidian_items(config)
    assert len(items) == 1
    assert items[0]["source_method"] == "tag"


def test_read_obsidian_items_frontmatter_method(tmp_path):
    note = tmp_path / "fm-note.md"
    note.write_text("---\ndashboard: true\ntitle: FM Note\n---\nBody", encoding="utf-8")
    config = {
        "obsidian": {
            "vault_path": str(tmp_path),
            "dashboard_folder": "Dashboard",
            "tags": [],
            "frontmatter_key": "dashboard",
        }
    }
    items = read_obsidian_items(config)
    assert len(items) == 1
    assert items[0]["source_method"] == "frontmatter"
    assert items[0]["title"] == "FM Note"


def test_read_obsidian_items_skips_hidden_dirs(tmp_path):
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    note = hidden / "settings.md"
    note.write_text("---\ndashboard: true\n---\nHidden", encoding="utf-8")
    config = {
        "obsidian": {
            "vault_path": str(tmp_path),
            "dashboard_folder": "Dashboard",
            "tags": [],
            "frontmatter_key": "dashboard",
        }
    }
    items = read_obsidian_items(config)
    assert items == []


def test_read_obsidian_items_deduplicates_folder_and_tag(tmp_path):
    """A note in Dashboard folder with a matching tag should appear only once."""
    dashboard = tmp_path / "Dashboard"
    dashboard.mkdir()
    note = dashboard / "dual.md"
    note.write_text("# Dual\n#mytag Some content", encoding="utf-8")
    config = {
        "obsidian": {
            "vault_path": str(tmp_path),
            "dashboard_folder": "Dashboard",
            "tags": ["#mytag"],
            "frontmatter_key": "dashboard",
        }
    }
    items = read_obsidian_items(config)
    assert len(items) == 1
