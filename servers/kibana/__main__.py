"""
Entry point for running Kibana MCP Server as a module.

Usage:
    python -m servers.kibana
    python -m servers.kibana --port=8001
    python -m servers.kibana --stdio
"""
from .server import mcp, config, logger

if __name__ == "__main__":
    import sys
    import uvicorn

    transport = "streamable-http"
    port = config.server_port

    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--stdio":
            transport = "stdio"

    logger.info(f"Starting Kibana MCP Server on port {port} with {transport} transport")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # Use uvicorn directly to specify port
        app = mcp.streamable_http_app()
        uvicorn.run(app, host="0.0.0.0", port=port)
