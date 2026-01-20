"""
Kibana Client - Handle authentication and Elasticsearch queries via Kibana
"""
import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class KibanaAuthError(Exception):
    """Raised when authentication fails"""
    pass


class KibanaQueryError(Exception):
    """Raised when a query fails"""
    pass


class KibanaClient:
    """
    Kibana client for authentication and Elasticsearch queries.

    Supports two authentication methods:
    1. Kibana internal security login (username/password)
    2. Session cookie (fallback)
    """

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookie: Optional[str] = None,
        verify_ssl: bool = False
    ):
        """
        Initialize Kibana client.

        Args:
            base_url: Kibana base URL (e.g., https://kibana.company.com)
            username: Username for login
            password: Password for login
            cookie: Optional session cookie (alternative to username/password)
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.cookie = cookie
        self.verify_ssl = verify_ssl
        self._authenticated = False

        # Setup session with retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Common headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'kbn-xsrf': 'true',  # Required by Kibana
        })

        # Disable SSL warnings if not verifying
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def login(self) -> bool:
        """
        Authenticate with Kibana.

        Returns:
            True if authentication successful

        Raises:
            KibanaAuthError: If authentication fails
        """
        if self.cookie:
            # Use provided cookie
            self.session.headers['Cookie'] = self.cookie
            self._authenticated = True
            logger.info("Using provided session cookie")
            return True

        if not self.username or not self.password:
            raise KibanaAuthError("No credentials provided (username/password or cookie)")

        # Try Kibana internal security login
        try:
            return self._login_internal_security()
        except Exception as e:
            logger.warning(f"Internal security login failed: {e}, trying basic auth")
            return self._login_basic_auth()

    def _login_internal_security(self) -> bool:
        """
        Login using Kibana internal security API.
        This is the standard method for Elastic Security.
        """
        login_url = f"{self.base_url}/internal/security/login"

        payload = {
            "providerType": "basic",
            "providerName": "basic",
            "currentURL": f"{self.base_url}/login",
            "params": {
                "username": self.username,
                "password": self.password
            }
        }

        try:
            resp = self.session.post(
                login_url,
                json=payload,
                verify=self.verify_ssl
            )

            if resp.status_code == 200:
                self._authenticated = True
                logger.info(f"Successfully logged in as {self.username}")
                return True
            else:
                error_msg = f"Login failed with status {resp.status_code}: {resp.text}"
                logger.error(error_msg)
                raise KibanaAuthError(error_msg)

        except requests.RequestException as e:
            raise KibanaAuthError(f"Login request failed: {e}")

    def _login_basic_auth(self) -> bool:
        """
        Fallback: Use HTTP Basic Auth.
        Some Kibana setups support this directly.
        """
        self.session.auth = (self.username, self.password)

        # Test authentication by accessing Kibana status
        try:
            resp = self.session.get(
                f"{self.base_url}/api/status",
                verify=self.verify_ssl
            )

            if resp.status_code == 200:
                self._authenticated = True
                logger.info(f"Successfully authenticated with basic auth")
                return True
            else:
                raise KibanaAuthError(f"Basic auth failed with status {resp.status_code}")

        except requests.RequestException as e:
            raise KibanaAuthError(f"Basic auth request failed: {e}")

    def ensure_authenticated(self):
        """Ensure client is authenticated, login if not"""
        if not self._authenticated:
            self.login()

    def execute_query(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None
    ) -> dict:
        """
        Execute an Elasticsearch query via Kibana Console proxy.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Elasticsearch path (e.g., /my-index/_search)
            body: Query body (optional)

        Returns:
            Elasticsearch response as dict
        """
        self.ensure_authenticated()

        # Kibana console proxy endpoint
        proxy_url = f"{self.base_url}/api/console/proxy"

        params = {
            'path': path,
            'method': method.upper()
        }

        try:
            if body:
                resp = self.session.post(
                    proxy_url,
                    params=params,
                    json=body,
                    verify=self.verify_ssl
                )
            else:
                resp = self.session.post(
                    proxy_url,
                    params=params,
                    verify=self.verify_ssl
                )

            if resp.status_code == 200:
                return resp.json()
            else:
                raise KibanaQueryError(
                    f"Query failed with status {resp.status_code}: {resp.text}"
                )

        except requests.RequestException as e:
            raise KibanaQueryError(f"Query request failed: {e}")

    def search(
        self,
        index: str,
        query: Optional[dict] = None,
        size: int = 100,
        sort: Optional[list] = None,
        source_includes: Optional[list] = None
    ) -> dict:
        """
        Search logs in Elasticsearch.

        Args:
            index: Index pattern (e.g., "logs-*", "app-logs-2024.01.*")
            query: Elasticsearch query DSL (optional)
            size: Number of results to return
            sort: Sort specification
            source_includes: Fields to include in response

        Returns:
            Search results
        """
        body = {
            "size": size,
            "query": query or {"match_all": {}}
        }

        if sort:
            body["sort"] = sort
        else:
            # Default: sort by timestamp descending
            body["sort"] = [{"@timestamp": {"order": "desc"}}]

        if source_includes:
            body["_source"] = {"includes": source_includes}

        return self.execute_query("POST", f"/{index}/_search", body)

    def search_logs(
        self,
        index: str,
        keyword: Optional[str] = None,
        time_range: str = "1h",
        level: Optional[str] = None,
        size: int = 100,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> dict:
        """
        Search logs with common filters.

        Args:
            index: Index pattern
            keyword: Search keyword (searches in message field)
            time_range: Time range (e.g., "1h", "24h", "7d") - used if start_time/end_time not provided
            level: Log level filter (e.g., "ERROR", "WARN")
            size: Number of results
            start_time: Absolute start time in ISO format (e.g., "2024-01-19T19:00:00+08:00")
            end_time: Absolute end time in ISO format (e.g., "2024-01-19T20:00:00+08:00")

        Returns:
            Search results
        """
        # Build query
        must_clauses = []

        # Time range filter - use absolute time if provided, otherwise relative
        if start_time and end_time:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": start_time,
                        "lte": end_time
                    }
                }
            })
        elif start_time:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": start_time,
                        "lte": "now"
                    }
                }
            })
        elif end_time:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": f"now-{time_range}",
                        "lte": end_time
                    }
                }
            })
        else:
            must_clauses.append({
                "range": {
                    "@timestamp": {
                        "gte": f"now-{time_range}",
                        "lte": "now"
                    }
                }
            })

        # Keyword filter
        if keyword:
            must_clauses.append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["message", "log", "msg", "error", "exception", "*"]
                }
            })

        # Level filter - support both 'level' and 'log_level' fields
        if level:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match": {"level": level.lower()}},
                        {"match": {"log_level": level.lower()}}
                    ],
                    "minimum_should_match": 1
                }
            })

        query = {
            "bool": {
                "must": must_clauses
            }
        }

        return self.search(index, query=query, size=size)

    def get_error_logs(
        self,
        index: str,
        time_range: str = "1h",
        size: int = 100
    ) -> dict:
        """
        Get error level logs.

        Args:
            index: Index pattern
            time_range: Time range
            size: Number of results

        Returns:
            Error logs
        """
        return self.search_logs(
            index=index,
            time_range=time_range,
            level="ERROR",
            size=size
        )

    def list_indices(self, pattern: str = "*") -> list:
        """
        List available indices.

        Args:
            pattern: Index pattern to filter

        Returns:
            List of index names
        """
        result = self.execute_query("GET", f"/_cat/indices/{pattern}?format=json")
        # Handle different response formats
        if isinstance(result, list):
            return [idx.get('index') for idx in result if isinstance(idx, dict) and idx.get('index')]
        elif isinstance(result, dict) and 'error' in result:
            raise KibanaQueryError(f"Failed to list indices: {result.get('error')}")
        return []

    def list_services(self, index_pattern: str = "*", time_range: str = "24h") -> list:
        """
        List available service names from logs.

        This helps AI understand which services are available for querying.

        Args:
            index_pattern: Index pattern to search (default: all indices)
            time_range: Time range to look for services (default: 24h)

        Returns:
            List of unique service names
        """
        body = {
            "size": 0,
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": f"now-{time_range}",
                        "lte": "now"
                    }
                }
            },
            "aggs": {
                "services": {
                    "terms": {
                        "field": "service_name.keyword",
                        "size": 500
                    }
                }
            }
        }

        result = self.execute_query("POST", f"/{index_pattern}/_search", body)

        # Extract service names from aggregation
        buckets = result.get('aggregations', {}).get('services', {}).get('buckets', [])
        return [bucket.get('key') for bucket in buckets if bucket.get('key')]

    def search_logs_by_service(
        self,
        service_name: str,
        keyword: Optional[str] = None,
        time_range: str = "1h",
        level: Optional[str] = None,
        size: int = 100,
        filters: Optional[dict] = None
    ) -> dict:
        """
        Search logs for a specific service.

        This is the recommended method for AI to query logs by service name.

        Args:
            service_name: Service name to search (e.g., "cepf-data-collection-listing-task")
            keyword: Search keyword in message field (optional)
            time_range: Time range (e.g., "1h", "24h", "7d")
            level: Log level filter (e.g., "error", "info", "warn")
            size: Number of results
            filters: Additional field filters as dict (e.g., {"pod_name": "xxx", "trace_id": "yyy"})

        Returns:
            Search results
        """
        # Build query
        must_clauses = []

        # Time range filter
        must_clauses.append({
            "range": {
                "@timestamp": {
                    "gte": f"now-{time_range}",
                    "lte": "now"
                }
            }
        })

        # Service name filter (exact match)
        must_clauses.append({
            "term": {
                "service_name.keyword": service_name
            }
        })

        # Keyword filter
        if keyword:
            must_clauses.append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["message", "log", "msg", "error", "exception", "*"]
                }
            })

        # Level filter - support both 'level' and 'log_level' fields
        if level:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match": {"level": level.lower()}},
                        {"match": {"log_level": level.lower()}}
                    ],
                    "minimum_should_match": 1
                }
            })

        # Additional filters
        if filters:
            for field, value in filters.items():
                if value:
                    # Try exact match first with .keyword suffix
                    must_clauses.append({
                        "bool": {
                            "should": [
                                {"term": {f"{field}.keyword": value}},
                                {"match": {field: value}}
                            ],
                            "minimum_should_match": 1
                        }
                    })

        query = {
            "bool": {
                "must": must_clauses
            }
        }

        return self.search(index="*", query=query, size=size)

    def get_index_mapping(self, index: str) -> dict:
        """
        Get index mapping (field definitions).

        Args:
            index: Index name

        Returns:
            Index mapping
        """
        return self.execute_query("GET", f"/{index}/_mapping")

    def get_cluster_health(self) -> dict:
        """Get Elasticsearch cluster health"""
        return self.execute_query("GET", "/_cluster/health")
