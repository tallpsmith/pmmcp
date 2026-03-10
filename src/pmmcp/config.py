from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class PmproxyConfig(BaseSettings):
    url: AnyHttpUrl
    timeout: float = 30.0
    health_interval: int = 15
    session_dir: Path = Path("~/.pmmcp/sessions")
    session_ttl_hours: int = 24

    model_config = {"env_prefix": "PMPROXY_"}


class ServerConfig(BaseSettings):
    """Transport configuration for the MCP server itself.

    Reads PMMCP_TRANSPORT, PMMCP_HOST, PMMCP_PORT from the environment.
    CLI flags in __main__.py use these as defaults, so env vars work
    without any CLI args.
    """

    transport: Literal["stdio", "streamable-http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8080
    grafana_folder: str = "pmmcp-triage"
    report_dir: Path = Path("~/.pmmcp/reports")

    model_config = {"env_prefix": "PMMCP_"}
