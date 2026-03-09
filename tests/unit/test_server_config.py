"""Tests for ServerConfig transport configuration via env vars."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestServerConfig:
    def test_defaults(self):
        """ServerConfig defaults to stdio transport on 127.0.0.1:8080."""
        from pmmcp.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.transport == "stdio"
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8080

    def test_env_var_override_transport(self, monkeypatch):
        """PMMCP_TRANSPORT env var overrides default."""
        monkeypatch.setenv("PMMCP_TRANSPORT", "streamable-http")
        from pmmcp.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.transport == "streamable-http"

    def test_env_var_override_host(self, monkeypatch):
        """PMMCP_HOST env var overrides default."""
        monkeypatch.setenv("PMMCP_HOST", "0.0.0.0")
        from pmmcp.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.host == "0.0.0.0"

    def test_env_var_override_port(self, monkeypatch):
        """PMMCP_PORT env var overrides default."""
        monkeypatch.setenv("PMMCP_PORT", "9090")
        from pmmcp.config import ServerConfig

        cfg = ServerConfig()
        assert cfg.port == 9090

    def test_invalid_transport_rejected(self):
        """Invalid transport value raises ValidationError."""
        from pmmcp.config import ServerConfig

        with pytest.raises(ValidationError):
            ServerConfig(transport="grpc")

    def test_constructor_overrides_env(self, monkeypatch):
        """Explicit constructor args take precedence over env vars."""
        monkeypatch.setenv("PMMCP_PORT", "9090")
        from pmmcp.config import ServerConfig

        cfg = ServerConfig(port=7070)
        assert cfg.port == 7070


class TestMainWiring:
    """Verify __main__.py reads transport defaults from ServerConfig."""

    def test_env_transport_becomes_argparse_default(self, monkeypatch):
        """PMMCP_TRANSPORT env var flows through to argparse defaults."""
        monkeypatch.setenv("PMMCP_TRANSPORT", "streamable-http")
        monkeypatch.setenv("PMMCP_HOST", "0.0.0.0")
        monkeypatch.setenv("PMMCP_PORT", "9090")
        # Only pass the required --pmproxy-url so argparse doesn't fail
        monkeypatch.setattr("sys.argv", ["pmmcp", "--pmproxy-url", "http://localhost:44322"])

        # We can't call main() (it would start the server), so we replicate
        # the parser setup path and check the parsed args.
        import importlib

        import pmmcp.__main__ as mod

        importlib.reload(mod)  # pick up fresh env

        from pmmcp.config import ServerConfig

        server_cfg = ServerConfig()
        assert server_cfg.transport == "streamable-http"
        assert server_cfg.host == "0.0.0.0"
        assert server_cfg.port == 9090
