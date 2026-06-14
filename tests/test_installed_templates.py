"""Tests for the installed_templates persistence layer."""
from __future__ import annotations

import json

import pytest

import latex_forge.installed_templates as meta


# ── Fixture ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_meta(tmp_path, monkeypatch):
    fake = tmp_path / "installed_templates.json"
    monkeypatch.setattr(meta, "metadata_path", lambda: fake)
    yield fake


# ── load_all ──────────────────────────────────────────────────────────────


def test_load_all_returns_empty_when_no_file():
    assert meta.load_all() == {}


def test_load_all_returns_empty_on_corrupt_json(isolated_meta):
    isolated_meta.parent.mkdir(parents=True, exist_ok=True)
    isolated_meta.write_text("NOT JSON", encoding="utf-8")
    assert meta.load_all() == {}


# ── record ────────────────────────────────────────────────────────────────


def test_record_creates_entry():
    meta.record("my-tpl", install_url="https://example.com/tpl.zip", version="1.2.3")
    data = meta.load_all()
    assert "my-tpl" in data
    entry = data["my-tpl"]
    assert entry["install_url"] == "https://example.com/tpl.zip"
    assert entry["installed_version"] == "1.2.3"
    assert "installed_at" in entry


def test_record_overwrites_existing():
    meta.record("my-tpl", install_url="https://old.com", version="1.0.0")
    meta.record("my-tpl", install_url="https://new.com", version="2.0.0")
    data = meta.load_all()
    assert data["my-tpl"]["install_url"] == "https://new.com"
    assert data["my-tpl"]["installed_version"] == "2.0.0"


def test_record_allows_none_version():
    meta.record("my-tpl", install_url="https://example.com", version=None)
    assert meta.load_all()["my-tpl"]["installed_version"] is None


def test_record_creates_parent_directories(tmp_path, monkeypatch):
    deep = tmp_path / "a" / "b" / "c" / "meta.json"
    monkeypatch.setattr(meta, "metadata_path", lambda: deep)
    meta.record("x", install_url=None, version=None)
    assert deep.exists()


# ── get ───────────────────────────────────────────────────────────────────


def test_get_returns_none_for_unknown():
    assert meta.get("unknown") is None


def test_get_returns_entry_when_present():
    meta.record("tpl", install_url="https://x.com", version="0.1.0")
    entry = meta.get("tpl")
    assert entry is not None
    assert entry["installed_version"] == "0.1.0"


# ── remove ────────────────────────────────────────────────────────────────


def test_remove_deletes_entry():
    meta.record("tpl", install_url="https://x.com", version="1.0.0")
    meta.remove("tpl")
    assert meta.get("tpl") is None


def test_remove_noop_when_not_present():
    # Should not raise
    meta.remove("nonexistent")


def test_remove_keeps_other_entries():
    meta.record("a", install_url=None, version="1.0.0")
    meta.record("b", install_url=None, version="2.0.0")
    meta.remove("a")
    assert meta.get("a") is None
    assert meta.get("b") is not None


# ── persistence ───────────────────────────────────────────────────────────


def test_persisted_file_is_valid_json(isolated_meta):
    meta.record("tpl", install_url="https://x.com", version="1.0.0")
    data = json.loads(isolated_meta.read_text(encoding="utf-8"))
    assert "tpl" in data
