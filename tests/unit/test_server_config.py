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
