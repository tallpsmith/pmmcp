"""Tests for session DB lifecycle and stale session purge."""

import os
import time

import pytest

from pmmcp import server
from pmmcp.server import _purge_stale_sessions, get_session_db


def test_get_session_db_raises_outside_lifespan():
    """get_session_db raises RuntimeError when server hasn't started."""
    original = server._session_db
    try:
        server._session_db = None
        with pytest.raises(RuntimeError, match="session DB not initialized"):
            get_session_db()
    finally:
        server._session_db = original


@pytest.mark.asyncio
async def test_purge_removes_old_files(tmp_path):
    """Purge deletes .db files older than TTL."""
    old_file = tmp_path / "old.db"
    old_file.touch()
    old_mtime = time.time() - (48 * 3600)
    os.utime(old_file, (old_mtime, old_mtime))

    fresh_file = tmp_path / "fresh.db"
    fresh_file.touch()

    await _purge_stale_sessions(tmp_path, ttl_hours=24)

    assert not old_file.exists(), "Old file should be purged"
    assert fresh_file.exists(), "Fresh file should be kept"


@pytest.mark.asyncio
async def test_purge_ignores_non_db_files(tmp_path):
    """Purge only touches .db files."""
    txt_file = tmp_path / "notes.txt"
    txt_file.touch()
    old_mtime = time.time() - (48 * 3600)
    os.utime(txt_file, (old_mtime, old_mtime))

    await _purge_stale_sessions(tmp_path, ttl_hours=24)

    assert txt_file.exists(), "Non-.db files should not be purged"


@pytest.mark.asyncio
async def test_purge_handles_empty_directory(tmp_path):
    """Purge does not crash on empty directory."""
    await _purge_stale_sessions(tmp_path, ttl_hours=24)
