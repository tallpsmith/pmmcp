"""Tests for session-related config fields."""

from pathlib import Path

from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


def test_session_dir_defaults_to_home():
    """session_dir defaults to ~/.pmmcp/sessions."""
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_dir == Path("~/.pmmcp/sessions")


def test_session_ttl_hours_defaults_to_24():
    """session_ttl_hours defaults to 24."""
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_ttl_hours == 24


def test_session_dir_overridable(monkeypatch):
    """session_dir can be overridden via env var."""
    monkeypatch.setenv("PMPROXY_SESSION_DIR", "/tmp/custom-sessions")
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_dir == Path("/tmp/custom-sessions")


def test_session_ttl_hours_overridable(monkeypatch):
    """session_ttl_hours can be overridden via env var."""
    monkeypatch.setenv("PMPROXY_SESSION_TTL_HOURS", "48")
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_ttl_hours == 48
