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
    args = parser.parse_args()

    import pmmcp.server as srv
    from pmmcp.config import PmproxyConfig

    kwargs: dict = {}
    if args.pmproxy_url is not None:
        kwargs["url"] = args.pmproxy_url
    if args.timeout is not None:
        kwargs["timeout"] = args.timeout
    srv._config = PmproxyConfig(**kwargs)
    srv.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
