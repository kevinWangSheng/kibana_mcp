"""
Entry point for running Archery MCP Server as a module.

Usage:
    python -m servers.archery
    python -m servers.archery --port=8001
    python -m servers.archery --stdio
"""
from .server import mcp, config, logger

if __name__ == "__main__":
    import sys
    import uvicorn

    transport = "streamable-http"
    port = 8001  # Default port for Archery (different from Kibana)

    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--stdio":
            transport = "stdio"

    logger.info(f"Starting Archery MCP Server on port {port} with {transport} transport")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        app = mcp.streamable_http_app()
        uvicorn.run(app, host="0.0.0.0", port=port)
