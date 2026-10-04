"""Shared pytest configuration."""
from __future__ import annotations

import platform

import pytest


@pytest.fixture(autouse=True, scope="session")
def _prime_platform_cache():
    """Resolve platform.uname() once, before any test patches subprocess.run.

    On Windows before Python 3.12, the first platform.system()/machine() call
    runs `cmd /c ver` through subprocess; a test that has replaced
    subprocess.run with a fake would receive that call instead.
    """
    platform.uname()


@pytest.fixture(autouse=True)
def _isolated_home(request, tmp_path_factory, monkeypatch):
    """Never read or write the real home: profile, config, installed
    templates, first-run marker, TinyTeX location all resolve under a fresh
    temporary HOME. Tests that need a specific HOME still set their own.
    Integration tests keep the real HOME: that's where TinyTeX is installed.
    """
    if request.node.get_closest_marker("integration"):
        return None
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("TINYTEX_DIR", raising=False)
    return home
