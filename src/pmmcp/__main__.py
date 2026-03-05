from __future__ import annotations

import argparse
import logging
import sys


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="pmmcp — MCP server for PCP (Performance Co-Pilot) via pmproxy"
    )
    parser.add_argument(
        "--pmproxy-url",
        default=None,
        help="pmproxy base URL (e.g., http://localhost:44322); overrides PMPROXY_URL env var",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="HTTP request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Bind port for HTTP transport (default: 8080)",
    )
    args = parser.parse_args()

    import pmmcp.server as srv
    from pmmcp.config import PmproxyConfig

    kwargs: dict = {}
    if args.pmproxy_url is not None:
        kwargs["url"] = args.pmproxy_url
    if args.timeout is not None:
        kwargs["timeout"] = args.timeout
    srv._config = PmproxyConfig(**kwargs)

    if args.transport == "streamable-http":
        srv.mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        srv.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
