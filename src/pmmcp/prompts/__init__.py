# Prompt modules are imported here as side-effects to trigger @mcp.prompt() registration.
from pmmcp.prompts import (  # noqa: F401
    compare,
    coordinator,
    health,
    investigate,
    session_init,
    specialist,
    triage,
)
