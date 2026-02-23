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
        required=True,
        help="pmproxy base URL (e.g., http://localhost:44322)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30.0)",
    )
    args = parser.parse_args()

    import pmmcp.server as srv
    from pmmcp.config import PmproxyConfig

    srv._config = PmproxyConfig(url=args.pmproxy_url, timeout=args.timeout)
    srv.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
