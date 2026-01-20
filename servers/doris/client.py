"""
Doris/Ops-Cloud Client - Query historical logs (3+ days old) via Ops-Cloud platform

This client interfaces with the Ops-Cloud platform which provides access to Doris
for querying historical logs that are older than 3 days. For logs within 3 days,
use the Kibana/ELK server instead.

API Endpoints:
- GET /api/v1/logs/service-names - List available service names
- GET /api/v1/logs/environments - List available environments
- GET /api/v1/logs/fields - Get available fields for an environment
- POST /api/v1/logs/query - Query logs
"""
import json
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class DorisAuthError(Exception):
    """Raised when authentication fails"""
    pass


class DorisQueryError(Exception):
    """Raised when a query fails"""
    pass


class DorisClient:
    """
    Client for Ops-Cloud platform to query Doris historical logs.

    Uses JWT token authentication.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = True
    ):
        """
        Initialize Doris client.

        Args:
            base_url: Ops-Cloud base URL (e.g., http://ops-cloud.basic.akops.internal)
            token: JWT access token (if available)
            username: Username for login (if token not provided)
            password: Password for login (if token not provided)
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.username = username
        self.password = password
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

        # Disable proxy for internal domains
        parsed = urlparse(base_url)
        if parsed.hostname and (
            parsed.hostname.endswith('.internal') or
            parsed.hostname.endswith('.local') or
            parsed.hostname.startswith('192.168.') or
            parsed.hostname.startswith('10.') or
            parsed.hostname == 'localhost'
        ):
            self.session.trust_env = False
            self.session.proxies = {'http': None, 'https': None}
            logger.debug(f"Proxy disabled for internal host: {parsed.hostname}")

        # Disable SSL warnings if not verifying
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Set token if provided
        if token:
            self._set_auth_header(token)
            self._authenticated = True

    def _set_auth_header(self, token: str):
        """Set the authorization header with token."""
        self.session.headers['Authorization'] = token
        if not token.startswith('Bearer '):
            self.session.headers['Authorization'] = f'Bearer {token}'

    def login(self) -> bool:
        """
        Authenticate with Ops-Cloud platform.

        If token is already set, validates it. Otherwise attempts login with credentials.

        Returns:
            True if authentication successful

        Raises:
            DorisAuthError: If authentication fails
        """
        if self.token:
            # Validate existing token by making a simple request
            try:
                self.get_environments()
                self._authenticated = True
                logger.info("Token validated successfully")
                return True
            except DorisQueryError:
                logger.warning("Token validation failed, attempting re-login")
                self.token = None

        if not self.username or not self.password:
            raise DorisAuthError("No token or credentials provided")

        # Attempt login with credentials
        try:
            # Try multiple login endpoints
            login_endpoints = ['/api/v1/login', '/api/v1/auth/login', '/api/auth/login']

            for endpoint in login_endpoints:
                login_url = f"{self.base_url}{endpoint}"
                resp = self.session.post(
                    login_url,
                    json={'username': self.username, 'password': self.password},
                    verify=self.verify_ssl
                )

                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get('data', {}).get('accessToken') or data.get('accessToken') or data.get('token')
                    if token:
                        self.token = token
                        self._set_auth_header(token)
                        self._authenticated = True
                        logger.info(f"Successfully logged in as {self.username}")
                        return True

            raise DorisAuthError(f"Login failed on all endpoints")

        except requests.RequestException as e:
            raise DorisAuthError(f"Login request failed: {e}")

    def ensure_authenticated(self):
        """Ensure client is authenticated."""
        if not self._authenticated:
            if self.token:
                self._set_auth_header(self.token)
                self._authenticated = True
            else:
                self.login()

    def _api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        _retry: bool = True
    ) -> dict:
        """
        Make an API request to Ops-Cloud.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data (for POST)
            params: Query parameters (for GET)
            _retry: Internal flag to prevent infinite retry loops

        Returns:
            Response data as dict
        """
        self.ensure_authenticated()

        url = f"{self.base_url}{endpoint}"
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
        }

        try:
            if method.upper() == 'GET':
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    verify=self.verify_ssl
                )
            else:
                resp = self.session.post(
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                    verify=self.verify_ssl
                )

            if resp.status_code == 200:
                try:
                    result = resp.json()
                    # Handle common response formats
                    if isinstance(result, dict):
                        if result.get('code') == 0 or result.get('success'):
                            return result.get('data', result)
                        elif 'data' in result:
                            return result['data']
                    return result
                except json.JSONDecodeError:
                    return {'raw_response': resp.text}
            elif resp.status_code == 401:
                self._authenticated = False
                # Auto re-login if we have credentials and haven't retried yet
                if _retry and self.username and self.password:
                    logger.info("Token expired, attempting auto re-login...")
                    self.token = None  # Clear expired token
                    try:
                        self.login()
                        # Retry the request once
                        return self._api_request(method, endpoint, data, params, _retry=False)
                    except DorisAuthError as e:
                        raise DorisAuthError(f"Auto re-login failed: {e}")
                raise DorisAuthError("Authentication expired or invalid. No credentials available for auto re-login.")
            else:
                raise DorisQueryError(
                    f"API request failed with status {resp.status_code}: {resp.text}"
                )

        except requests.RequestException as e:
            raise DorisQueryError(f"API request failed: {e}")

    def get_service_names(self, keyword: str = '') -> List[str]:
        """
        Get list of available service names.

        Args:
            keyword: Optional keyword to filter services

        Returns:
            List of service names
        """
        params = {'keyword': keyword} if keyword else {}
        result = self._api_request('GET', '/api/v1/logs/service-names', params=params)

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get('services', result.get('data', []))
        return []

    def get_environments(self) -> List[str]:
        """
        Get list of available environments.

        Returns:
            List of environment names (e.g., ['amz', 'prod', 'test'])
        """
        result = self._api_request('GET', '/api/v1/logs/environments')

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # Handle nested structure: data.environments
            if 'environments' in result:
                return result['environments']
            elif 'data' in result:
                data = result['data']
                if isinstance(data, dict) and 'environments' in data:
                    return data['environments']
                elif isinstance(data, list):
                    return data
            return []
        return []

    def get_fields(self, environment: str) -> List[Dict]:
        """
        Get available fields for an environment.

        Args:
            environment: Environment name (e.g., 'amz')

        Returns:
            List of field definitions
        """
        result = self._api_request(
            'GET',
            '/api/v1/logs/fields',
            params={'environment': environment}
        )

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get('fields', result.get('data', []))
        return []

    def query_logs(
        self,
        service_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        keyword: Optional[str] = None,
        level: Optional[str] = None,
        environment: str = 'amz',
        page: int = 1,
        page_size: int = 100,
        **extra_filters
    ) -> Dict:
        """
        Query historical logs from Doris.

        Note: This is for logs older than 3 days. For recent logs, use Kibana.

        Args:
            service_name: Service name to query logs for
            start_time: Start time in ISO format (e.g., '2024-01-01T00:00:00Z')
            end_time: End time in ISO format
            keyword: Search keyword in log message
            level: Log level filter (ERROR, WARN, INFO, DEBUG)
            environment: Environment name (default: 'amz')
            page: Page number (default: 1)
            page_size: Page size (default: 100)
            **extra_filters: Additional filter parameters

        Returns:
            Dict with query results containing logs
        """
        # Default time range: 7 days ago to 3 days ago
        if not end_time:
            end_dt = datetime.utcnow() - timedelta(days=3)
            end_time = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        if not start_time:
            start_dt = datetime.utcnow() - timedelta(days=7)
            start_time = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Build query data with correct structure (API uses snake_case)
        query_data = {
            'service_name': service_name,
            'environment': environment,
            'time_range': {
                'start_time': start_time,
                'end_time': end_time
            },
            'page': page,
            'page_size': page_size
        }

        if keyword:
            query_data['keyword'] = keyword
        if level:
            query_data['level'] = level.upper()

        # Add any extra filters
        query_data.update(extra_filters)

        result = self._api_request('POST', '/api/v1/logs/query', data=query_data)

        return result

    def query_logs_by_trace_id(
        self,
        trace_id: str,
        environment: str = 'amz'
    ) -> Dict:
        """
        Query logs by trace ID for distributed tracing.

        Args:
            trace_id: Trace ID to search for
            environment: Environment name

        Returns:
            Dict with matching logs
        """
        return self.query_logs(
            service_name='',
            environment=environment,
            trace_id=trace_id,
            page_size=500
        )

    def get_error_logs(
        self,
        service_name: str,
        days_ago_start: int = 7,
        days_ago_end: int = 3,
        environment: str = 'amz',
        limit: int = 100
    ) -> Dict:
        """
        Get ERROR level logs for a service.

        Args:
            service_name: Service name
            days_ago_start: How many days ago to start (default: 7)
            days_ago_end: How many days ago to end (default: 3)
            environment: Environment name
            limit: Maximum results

        Returns:
            Dict with error logs
        """
        start_dt = datetime.utcnow() - timedelta(days=days_ago_start)
        end_dt = datetime.utcnow() - timedelta(days=days_ago_end)

        return self.query_logs(
            service_name=service_name,
            start_time=start_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            end_time=end_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            level='ERROR',
            environment=environment,
            page_size=limit
        )
