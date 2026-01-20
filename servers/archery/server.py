"""
Archery MCP Server - Expose Archery SQL platform functionality via MCP

Tools:
- get_instances: List database instances
- get_databases: List databases for an instance
- query_execute: Execute read-only SQL queries
- sql_check: Check SQL syntax and get suggestions
- sql_review: Submit SQL for audit review
- get_workflow_list: List SQL workflows/tickets
- get_workflow_detail: Get workflow details
"""
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import ArcheryClient, ArcheryAuthError, ArcheryQueryError
from common.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize config
config = Config()

# Initialize MCP server
mcp = FastMCP(
    "Archery MCP Server",
    json_response=True
)

# Global client instance (lazy initialized)
_client: Optional[ArcheryClient] = None


def get_client() -> ArcheryClient:
    """Get or create Archery client"""
    global _client

    if _client is None:
        if not config.validate_archery():
            raise ArcheryAuthError(
                "Archery configuration is incomplete. "
                "Please set ARCHERY_URL, ARCHERY_USERNAME, ARCHERY_PASSWORD in .env file"
            )

        _client = ArcheryClient(
            base_url=config.archery.url,
            username=config.archery.username,
            password=config.archery.password,
            verify_ssl=False
        )
        _client.login()

    return _client


@mcp.tool()
def get_instances(db_type: Optional[str] = None) -> str:
    """
    Get list of database instances registered in Archery.

    This should be called FIRST to discover available instances before running queries.

    Args:
        db_type: Filter by database type (mysql, mssql, oracle, pgsql, redis, mongo, etc.)

    Returns:
        JSON string with list of instances

    Example:
        get_instances()  # List all instances
        get_instances(db_type="mysql")  # List only MySQL instances
    """
    try:
        client = get_client()
        instances = client.get_instances(db_type)

        return json.dumps({
            'success': True,
            'count': len(instances),
            'instances': instances
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_instances")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_databases(instance_name: str) -> str:
    """
    Get list of databases for a specific instance.

    Call this after get_instances() to see available databases.

    Args:
        instance_name: Name of the database instance (from get_instances)

    Returns:
        JSON string with list of database names

    Example:
        get_databases(instance_name="prod-mysql-master")
    """
    try:
        client = get_client()
        databases = client.get_databases(instance_name)

        return json.dumps({
            'success': True,
            'instance_name': instance_name,
            'count': len(databases),
            'databases': databases
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_databases")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def query_execute(
    sql_content: str,
    instance_name: str,
    db_name: str,
    limit: int = 100
) -> str:
    """
    Execute a read-only SQL query (SELECT only).

    IMPORTANT: Only SELECT queries are allowed for safety.
    For DDL/DML operations, use sql_review to submit a workflow.

    Args:
        sql_content: SQL SELECT statement to execute
        instance_name: Target instance name (from get_instances)
        db_name: Target database name (from get_databases)
        limit: Maximum rows to return (default 100, max 1000)

    Returns:
        JSON string with query results (columns and rows)

    Examples:
        query_execute(
            sql_content="SELECT * FROM users WHERE status = 1",
            instance_name="prod-mysql-master",
            db_name="user_db",
            limit=50
        )
    """
    try:
        client = get_client()

        # Limit rows for safety
        limit = min(limit, 1000)

        result = client.query_execute(
            sql_content=sql_content,
            instance_name=instance_name,
            db_name=db_name,
            limit=limit
        )

        return json.dumps({
            'success': True,
            'instance_name': instance_name,
            'db_name': db_name,
            'result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in query_execute")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def sql_check(
    sql_content: str,
    instance_name: str,
    db_name: str = ''
) -> str:
    """
    Check SQL syntax and get optimization suggestions.

    Use this to validate SQL before submitting for review.

    Args:
        sql_content: SQL statement to check
        instance_name: Target instance name
        db_name: Target database name (optional)

    Returns:
        JSON string with check results and suggestions

    Example:
        sql_check(
            sql_content="SELECT * FROM users WHERE id = 1",
            instance_name="prod-mysql-master",
            db_name="user_db"
        )
    """
    try:
        client = get_client()
        result = client.sql_check(
            sql_content=sql_content,
            instance_name=instance_name,
            db_name=db_name
        )

        return json.dumps({
            'success': True,
            'check_result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in sql_check")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def sql_review(
    sql_content: str,
    instance_name: str,
    db_name: str,
    workflow_name: Optional[str] = None
) -> str:
    """
    Submit SQL for audit review (creates a workflow/ticket).

    Use this for DDL/DML operations that need approval.

    Args:
        sql_content: SQL statement to submit for review
        instance_name: Target instance name
        db_name: Target database name
        workflow_name: Optional name for the workflow/ticket

    Returns:
        JSON string with review submission result

    Example:
        sql_review(
            sql_content="ALTER TABLE users ADD COLUMN phone VARCHAR(20)",
            instance_name="prod-mysql-master",
            db_name="user_db",
            workflow_name="Add phone column to users"
        )
    """
    try:
        client = get_client()
        result = client.sql_review(
            sql_content=sql_content,
            instance_name=instance_name,
            db_name=db_name,
            workflow_name=workflow_name
        )

        return json.dumps({
            'success': True,
            'review_result': result
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in sql_review")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_workflow_list(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
) -> str:
    """
    Get list of SQL workflows/tickets.

    Args:
        status: Filter by status (pending, executing, finished, rejected, etc.)
        start_date: Start date filter (YYYY-MM-DD format)
        end_date: End date filter (YYYY-MM-DD format)
        limit: Maximum workflows to return (default 50)

    Returns:
        JSON string with list of workflows

    Examples:
        get_workflow_list()  # List all recent workflows
        get_workflow_list(status="pending")  # List pending workflows
        get_workflow_list(start_date="2024-01-01", end_date="2024-01-31")
    """
    try:
        client = get_client()
        workflows = client.get_workflow_list(
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        return json.dumps({
            'success': True,
            'count': len(workflows),
            'workflows': workflows
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_workflow_list")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_workflow_detail(workflow_id: int) -> str:
    """
    Get details of a specific workflow/ticket.

    Args:
        workflow_id: Workflow ID (from get_workflow_list)

    Returns:
        JSON string with workflow details

    Example:
        get_workflow_detail(workflow_id=12345)
    """
    try:
        client = get_client()
        workflow = client.get_workflow_detail(workflow_id)

        return json.dumps({
            'success': True,
            'workflow': workflow
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_workflow_detail")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


@mcp.tool()
def get_query_history(
    instance_name: Optional[str] = None,
    db_name: Optional[str] = None,
    limit: int = 50
) -> str:
    """
    Get SQL query execution history.

    Args:
        instance_name: Filter by instance name (optional)
        db_name: Filter by database name (optional)
        limit: Maximum records to return (default 50)

    Returns:
        JSON string with query history

    Example:
        get_query_history(instance_name="prod-mysql-master", limit=20)
    """
    try:
        client = get_client()
        history = client.get_query_history(
            instance_name=instance_name,
            db_name=db_name,
            limit=limit
        )

        return json.dumps({
            'success': True,
            'count': len(history),
            'history': history
        }, ensure_ascii=False, indent=2, default=str)

    except (ArcheryAuthError, ArcheryQueryError) as e:
        return json.dumps({
            'success': False,
            'error': str(e)
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Unexpected error in get_query_history")
        return json.dumps({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, ensure_ascii=False)


# Main entry point
if __name__ == "__main__":
    import sys
    import uvicorn

    transport = "streamable-http"
    port = 8001  # Default port for Archery MCP

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
