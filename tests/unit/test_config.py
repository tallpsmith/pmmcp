"""Unit tests for config fields."""

from __future__ import annotations

from pathlib import Path

from pmmcp.config import ServerConfig


def test_server_config_grafana_folder_default():
    """PMMCP_GRAFANA_FOLDER defaults to 'pmmcp-triage'."""
    cfg = ServerConfig()
    assert cfg.grafana_folder == "pmmcp-triage"


def test_server_config_grafana_folder_env_override(monkeypatch):
    """PMMCP_GRAFANA_FOLDER can be overridden via env var."""
    monkeypatch.setenv("PMMCP_GRAFANA_FOLDER", "my-triage")
    cfg = ServerConfig()
    assert cfg.grafana_folder == "my-triage"


def test_server_config_report_dir_default():
    """PMMCP_REPORT_DIR defaults to ~/.pmmcp/reports/."""
    cfg = ServerConfig()
    assert cfg.report_dir == Path("~/.pmmcp/reports")


def test_server_config_report_dir_env_override(monkeypatch):
    """PMMCP_REPORT_DIR can be overridden via env var."""
    monkeypatch.setenv("PMMCP_REPORT_DIR", "/tmp/reports")
    cfg = ServerConfig()
    assert cfg.report_dir == Path("/tmp/reports")
