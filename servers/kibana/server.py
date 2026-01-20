"""
Kibana MCP Server - Expose Kibana/Elasticsearch functionality via MCP

Tools:
- search_logs: Search logs with keyword and filters
- get_error_logs: Get error level logs
- list_indices: List available indices
- execute_query: Execute raw Elasticsearch DSL query
"""
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import KibanaClient, KibanaAuthError, KibanaQueryError
from common.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize config
config = Config()

# Initialize MCP server
mcp = FastMCP(
    "Kibana MCP Server",
    json_response=True
)

# Global client instance (lazy initialized)
_client: Optional[KibanaClient] = None


def get_client() -> KibanaClient:
    """Get or create Kibana client"""
    global _client

    if _client is None:
        if not config.validate_kibana():
            raise KibanaAuthError(
                "Kibana configuration is incomplete. "
                "Please set KIBANA_URL, KIBANA_USERNAME, KIBANA_PASSWORD in .env file"
            )

        _client = KibanaClient(
            base_url=config.kibana.url,
            username=config.kibana.username,
            password=config.kibana.password,
            verify_ssl=False
        )
        _client.login()

    return _client


@mcp.tool()
def search_logs(
    index: str,
    keyword: Optional[str] = None,
    time_range: str = "1h",
    level: Optional[str] = None,
    size: int = 50,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> str:
    """
    Search logs in Elasticsearch via Kibana.

    Args:
        index: Index pattern (e.g., "logs-*", "app-logs-*")
        keyword: Search keyword (optional, searches in message/log fields)
        time_range: Time range like "1h", "24h", "7d" (default: "1h") - used if start_time/end_time not provided
        level: Log level filter like "ERROR", "WARN", "INFO" (optional)
        size: Number of results to return (default: 50, max: 500)
        start_time: Absolute start time in ISO format (e.g., "2024-01-19T19:00:00+08:00" or "2024-01-19T11:00:00Z")
        end_time: Absolute end time in ISO format (e.g., "2024-01-19T20:00:00+08:00" or "2024-01-19T12:00:00Z")

    Returns:
        JSON string with search results containing log entries

    Examples:
        search_logs(index="app-logs-*", keyword="NullPointerException", time_range="24h")
        search_logs(index="logs-*", level="ERROR", time_range="1h")
        search_logs(index="logs-*", start_time="2024-01-19T19:00:00+08:00", end_time="2024-01-19T20:00:00+08:00")
    """
    try:
        client = get_client()

        # Limit size for safety
        size = min(size, 500)

        result = client.search_logs(
            index=index,
            keyword=keyword,
            time_range=time_range,
            level=level,
            size=size,
            start_time=start_time,
            end_time=end_time
        )

        # Extract hits for cleaner output
        hits = result.get('hits', {})
        total = hits.get('total', {})
        if isinstance(total, dict):
            total_count = total.get('value', 0)
        else:
            total_count = total

        logs = []
        for hit in hits.get('hits', []):
            log_entry = {
                '_index': hit.get('_index'),
                '_id': hit.get('_id'),
                **hit.get('_source', {})
            }
            logs.append(log_entry)

        return json.dumps({
            'success': True,
            'total': total_count,
            'returned': len(logs),
            'logs': logs
        }, ensure_ascii=False, indent=2, default=str)

    except (KibanaAuthError, KibanaQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in search_logs")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_error_logs(
    index: str,
    time_range: str = "1h",
    size: int = 50
) -> str:
    """
    Get ERROR level logs from Elasticsearch.

    This is a convenience method that filters for ERROR level logs.

    Args:
        index: Index pattern (e.g., "logs-*", "app-logs-*")
        time_range: Time range like "1h", "24h", "7d" (default: "1h")
        size: Number of results to return (default: 50, max: 500)

    Returns:
        JSON string with error log entries

    Example:
        get_error_logs(index="production-logs-*", time_range="24h")
    """
    return search_logs(index=index, time_range=time_range, level="ERROR", size=size)


@mcp.tool()
def list_indices(pattern: str = "*") -> str:
    """
    List available Elasticsearch indices.

    Args:
        pattern: Index pattern to filter (default: "*" for all)

    Returns:
        JSON string with list of index names

    Examples:
        list_indices()  # List all indices
        list_indices(pattern="logs-*")  # List indices matching pattern
    """
    try:
        client = get_client()
        indices = client.list_indices(pattern)

        return json.dumps({
            'success': True,
            'count': len(indices),
            'indices': sorted(indices)
        }, ensure_ascii=False, indent=2)

    except (KibanaAuthError, KibanaQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in list_indices")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_index_mapping(index: str) -> str:
    """
    Get field mapping for an index.

    This helps understand what fields are available for searching.

    Args:
        index: Index name (e.g., "logs-2024.01.01")

    Returns:
        JSON string with index mapping showing all fields and their types

    Example:
        get_index_mapping(index="app-logs-2024.01.15")
    """
    try:
        client = get_client()
        mapping = client.get_index_mapping(index)

        return json.dumps({
            'success': True,
            'mapping': mapping
        }, ensure_ascii=False, indent=2)

    except (KibanaAuthError, KibanaQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_index_mapping")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def execute_es_query(
    method: str,
    path: str,
    body: Optional[str] = None
) -> str:
    """
    Execute a raw Elasticsearch query via Kibana Console.

    This is for advanced users who need full control over the query.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: Elasticsearch API path (e.g., "/my-index/_search")
        body: Query body as JSON string (optional)

    Returns:
        JSON string with Elasticsearch response

    Examples:
        execute_es_query(method="GET", path="/_cluster/health")
        execute_es_query(
            method="POST",
            path="/logs-*/_search",
            body='{"query": {"match_all": {}}, "size": 10}'
        )
    """
    try:
        client = get_client()

        # Parse body if provided
        body_dict = None
        if body:
            try:
                body_dict = json.loads(body)
            except json.JSONDecodeError as e:
                return json.dumps({
                    'success': False,
                    'error': f"Invalid JSON body: {str(e)}"
                }, ensure_ascii=False)

        result = client.execute_query(method, path, body_dict)

        return json.dumps({
            'success': True,
            'result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (KibanaAuthError, KibanaQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in execute_es_query")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def list_services(
    index_pattern: str = "*",
    time_range: str = "24h"
) -> str:
    """
    List available service names from logs.

    AI should call this tool FIRST to discover what services are available,
    then use search_logs_by_service to query logs for a specific service.

    Args:
        index_pattern: Index pattern to search (default: "*" for all)
        time_range: Time range to look for services (default: "24h")

    Returns:
        JSON string with list of service names

    Example workflow for AI:
        1. Call list_services() to see available services
        2. Call search_logs_by_service(service_name="xxx", ...) to query logs
    """
    try:
        client = get_client()
        services = client.list_services(index_pattern, time_range)

        return json.dumps({
            'success': True,
            'count': len(services),
            'services': sorted(services)
        }, ensure_ascii=False, indent=2)

    except (KibanaAuthError, KibanaQueryError) as e:
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
def search_logs_by_service(
    service_name: str,
    keyword: Optional[str] = None,
    time_range: str = "1h",
    level: Optional[str] = None,
    size: int = 50,
    pod_name: Optional[str] = None,
    trace_id: Optional[str] = None,
    namespace: Optional[str] = None
) -> str:
    """
    Search logs for a specific service by name.

    This is the RECOMMENDED tool for AI to query logs. Use list_services() first
    to discover available service names.

    Args:
        service_name: Service name to search (required, e.g., "cepf-data-collection-listing-task")
        keyword: Search keyword in message field (optional)
        time_range: Time range like "1h", "24h", "7d" (default: "1h")
        level: Log level filter like "error", "warn", "info" (optional)
        size: Number of results to return (default: 50, max: 500)
        pod_name: Filter by specific pod name (optional)
        trace_id: Filter by trace ID for distributed tracing (optional)
        namespace: Filter by Kubernetes namespace (optional)

    Returns:
        JSON string with search results containing log entries

    Examples:
        search_logs_by_service(service_name="my-service", time_range="1h")
        search_logs_by_service(service_name="my-service", level="error", time_range="24h")
        search_logs_by_service(service_name="my-service", keyword="Exception", trace_id="abc123")
    """
    try:
        client = get_client()

        # Limit size for safety
        size = min(size, 500)

        # Build additional filters
        filters = {}
        if pod_name:
            filters['pod_name'] = pod_name
        if trace_id:
            filters['trace_id'] = trace_id
        if namespace:
            filters['namespace'] = namespace

        result = client.search_logs_by_service(
            service_name=service_name,
            keyword=keyword,
            time_range=time_range,
            level=level,
            size=size,
            filters=filters if filters else None
        )

        # Extract hits for cleaner output
        hits = result.get('hits', {})
        total = hits.get('total', {})
        if isinstance(total, dict):
            total_count = total.get('value', 0)
        else:
            total_count = total

        logs = []
        for hit in hits.get('hits', []):
            log_entry = {
                '_index': hit.get('_index'),
                '_id': hit.get('_id'),
                **hit.get('_source', {})
            }
            logs.append(log_entry)

        return json.dumps({
            'success': True,
            'service_name': service_name,
            'total': total_count,
            'returned': len(logs),
            'logs': logs
        }, ensure_ascii=False, indent=2, default=str)

    except (KibanaAuthError, KibanaQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in search_logs_by_service")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_cluster_health() -> str:
    """
    Get Elasticsearch cluster health status.

    Returns:
        JSON string with cluster health information including:
        - cluster_name
        - status (green/yellow/red)
        - number_of_nodes
        - active_shards

    Example:
        get_cluster_health()
    """
    try:
        client = get_client()
        health = client.get_cluster_health()

        return json.dumps({
            'success': True,
            'health': health
        }, ensure_ascii=False, indent=2)

    except (KibanaAuthError, KibanaQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_cluster_health")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


# Main entry point
if __name__ == "__main__":
    import sys

    # Check for transport argument
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
        mcp.run(transport="streamable-http", port=port)
