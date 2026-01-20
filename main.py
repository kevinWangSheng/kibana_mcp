"""
MCP DevOps Tools - Main entry point

This script starts the MCP server(s) for DevOps tools integration.

Usage:
    python main.py                    # Start with default settings
    python main.py --port=8000        # Specify port
    python main.py --server=kibana    # Start specific server only
"""
import sys
import logging
from common.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    config = Config()

    # Parse command line arguments
    port = config.server_port
    server = "kibana"  # Default to kibana for now
    transport = "streamable-http"

    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg.startswith("--server="):
            server = arg.split("=")[1]
        elif arg == "--stdio":
            transport = "stdio"

    logger.info(f"Starting MCP DevOps Tools")
    logger.info(f"  Server: {server}")
    logger.info(f"  Port: {port}")
    logger.info(f"  Transport: {transport}")

    if server == "kibana":
        from servers.kibana.server import mcp

        if not config.validate_kibana():
            logger.error("Kibana configuration is incomplete!")
            logger.error("Please set KIBANA_URL, KIBANA_USERNAME, KIBANA_PASSWORD in .env file")
            sys.exit(1)

        logger.info(f"Kibana URL: {config.kibana.url}")
        logger.info(f"MCP endpoint will be at: http://localhost:8000/mcp")

        if transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(transport="streamable-http")

    elif server == "archery":
        logger.error("Archery server not yet implemented")
        sys.exit(1)

    elif server == "doris":
        logger.error("Doris server not yet implemented")
        sys.exit(1)

    else:
        logger.error(f"Unknown server: {server}")
        sys.exit(1)


if __name__ == "__main__":
    main()
