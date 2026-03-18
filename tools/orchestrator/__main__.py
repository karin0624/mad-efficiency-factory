"""Allow running as `python -m tools.orchestrator` — starts MCP server."""

from .server import mcp

mcp.run(transport="stdio")
