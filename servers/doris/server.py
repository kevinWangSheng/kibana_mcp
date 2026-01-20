"""
Doris MCP Server - Query historical logs (3+ days old) via Ops-Cloud platform

This server provides access to Doris for querying historical logs that are
older than 3 days. For logs within 3 days, use the Kibana MCP server instead.

Tools:
- list_services: List available service names
- list_environments: List available environments
- get_fields: Get available fields for an environment
- search_historical_logs: Query historical logs
- get_historical_error_logs: Get ERROR level historical logs
"""
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import DorisClient, DorisAuthError, DorisQueryError
from common.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize config
config = Config()

# Initialize MCP server
mcp = FastMCP(
    "Doris MCP Server",
    json_response=True
)

# Global client instance (lazy initialized)
_client: Optional[DorisClient] = None


def get_client() -> DorisClient:
    """Get or create Doris client"""
    global _client

    if _client is None:
        if not config.validate_doris():
            raise DorisAuthError(
                "Doris configuration is incomplete. "
                "Please set DORIS_URL and DORIS_TOKEN (or DORIS_USERNAME/DORIS_PASSWORD) in .env file"
            )

        _client = DorisClient(
            base_url=config.doris.url,
            token=config.doris.token,
            username=config.doris.username,
            password=config.doris.password,
            verify_ssl=False
        )

        # Validate connection
        if config.doris.token:
            _client._set_auth_header(config.doris.token)
            _client._authenticated = True
        else:
            _client.login()

    return _client


@mcp.tool()
def list_services(keyword: str = '') -> str:
    """
    List available service names for log queries.

    Call this FIRST to discover what services are available before querying logs.

    Args:
        keyword: Optional keyword to filter services

    Returns:
        JSON string with list of service names

    Example:
        list_services()  # List all services
        list_services(keyword="order")  # Filter services containing "order"
    """
    try:
        client = get_client()
        services = client.get_service_names(keyword)

        return json.dumps({
            'success': True,
            'count': len(services),
            'services': services
        }, ensure_ascii=False, indent=2)

    except (DorisAuthError, DorisQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in list_services")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def list_environments() -> str:
    """
    List available environments.

    Returns:
        JSON string with list of environment names

    Example:
        list_environments()
    """
    try:
        client = get_client()
        environments = client.get_environments()

        return json.dumps({
            'success': True,
            'count': len(environments),
            'environments': environments
        }, ensure_ascii=False, indent=2)

    except (DorisAuthError, DorisQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in list_environments")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_fields(environment: str = 'amz') -> str:
    """
    Get available fields for an environment.

    Args:
        environment: Environment name (default: 'amz')

    Returns:
        JSON string with list of available fields

    Example:
        get_fields(environment="amz")
    """
    try:
        client = get_client()
        fields = client.get_fields(environment)

        return json.dumps({
            'success': True,
            'environment': environment,
            'count': len(fields),
            'fields': fields
        }, ensure_ascii=False, indent=2)

    except (DorisAuthError, DorisQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_fields")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def search_historical_logs(
    service_name: str,
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    days_ago_start: int = 7,
    days_ago_end: int = 3,
    environment: str = 'amz',
    limit: int = 100
) -> str:
    """
    Search historical logs from Doris (for logs older than 3 days).

    IMPORTANT: This queries logs OLDER than 3 days. For recent logs (within 3 days),
    use the Kibana MCP server instead.

    Args:
        service_name: Service name to query (use list_services to find available services)
        keyword: Search keyword in log message (optional)
        level: Log level filter - ERROR, WARN, INFO, DEBUG (optional)
        days_ago_start: How many days ago to start searching (default: 7)
        days_ago_end: How many days ago to end searching (default: 3, minimum for Doris)
        environment: Environment name (default: 'amz')
        limit: Maximum number of results (default: 100, max: 1000)

    Returns:
        JSON string with log entries

    Examples:
        search_historical_logs(service_name="order-service", days_ago_start=10, days_ago_end=5)
        search_historical_logs(service_name="payment-service", keyword="timeout", level="ERROR")
    """
    try:
        client = get_client()

        # Enforce minimum 3 days ago for Doris (recent logs are in ELK)
        if days_ago_end < 3:
            days_ago_end = 3

        # Limit max results
        limit = min(limit, 1000)

        from datetime import datetime, timedelta
        start_dt = datetime.utcnow() - timedelta(days=days_ago_start)
        end_dt = datetime.utcnow() - timedelta(days=days_ago_end)

        result = client.query_logs(
            service_name=service_name,
            start_time=start_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            end_time=end_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            keyword=keyword,
            level=level,
            environment=environment,
            page_size=limit
        )

        return json.dumps({
            'success': True,
            'service_name': service_name,
            'time_range': {
                'start': start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'end': end_dt.strftime('%Y-%m-%d %H:%M:%S')
            },
            'result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (DorisAuthError, DorisQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in search_historical_logs")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_historical_error_logs(
    service_name: str,
    days_ago_start: int = 7,
    days_ago_end: int = 3,
    environment: str = 'amz',
    limit: int = 100
) -> str:
    """
    Get ERROR level historical logs for a service.

    This is a convenience method for quickly finding errors in historical logs.

    Args:
        service_name: Service name to query
        days_ago_start: How many days ago to start (default: 7)
        days_ago_end: How many days ago to end (default: 3)
        environment: Environment name (default: 'amz')
        limit: Maximum results (default: 100)

    Returns:
        JSON string with error log entries

    Example:
        get_historical_error_logs(service_name="order-service", days_ago_start=14, days_ago_end=7)
    """
    try:
        client = get_client()

        # Enforce minimum 3 days ago
        if days_ago_end < 3:
            days_ago_end = 3

        limit = min(limit, 1000)

        result = client.get_error_logs(
            service_name=service_name,
            days_ago_start=days_ago_start,
            days_ago_end=days_ago_end,
            environment=environment,
            limit=limit
        )

        return json.dumps({
            'success': True,
            'service_name': service_name,
            'level': 'ERROR',
            'result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (DorisAuthError, DorisQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_historical_error_logs")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def search_by_trace_id(
    trace_id: str,
    environment: str = 'amz'
) -> str:
    """
    Search historical logs by trace ID for distributed tracing.

    Args:
        trace_id: Trace ID to search for
        environment: Environment name (default: 'amz')

    Returns:
        JSON string with matching logs

    Example:
        search_by_trace_id(trace_id="abc123def456")
    """
    try:
        client = get_client()
        result = client.query_logs_by_trace_id(
            trace_id=trace_id,
            environment=environment
        )

        return json.dumps({
            'success': True,
            'trace_id': trace_id,
            'result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (DorisAuthError, DorisQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in search_by_trace_id")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


# Main entry point
if __name__ == "__main__":
    import sys
    import uvicorn

    transport = "streamable-http"
    port = 8002  # Default port for Doris MCP

    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--stdio":
            transport = "stdio"

    logger.info(f"Starting Doris MCP Server on port {port} with {transport} transport")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        app = mcp.streamable_http_app()
        uvicorn.run(app, host="0.0.0.0", port=port)
