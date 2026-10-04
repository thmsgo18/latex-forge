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
