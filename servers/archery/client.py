"""
Archery Client - Handle authentication and SQL operations via Archery platform

Archery is an open-source SQL audit platform based on Django.
API Documentation: https://github.com/hhyo/Archery/wiki/api
"""
import json
import logging
from typing import Any, Optional, List, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ArcheryAuthError(Exception):
    """Raised when authentication fails"""
    pass


class ArcheryQueryError(Exception):
    """Raised when a query fails"""
    pass


class ArcheryClient:
    """
    Archery client for authentication and SQL operations.

    Archery uses Django session-based authentication with CSRF protection.
    """

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = True
    ):
        """
        Initialize Archery client.

        Args:
            base_url: Archery base URL (e.g., http://archery.company.com)
            username: Username for login
            password: Password for login
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
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

        # Disable SSL warnings if not verifying
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def login(self) -> bool:
        """
        Authenticate with Archery using Django session.

        Returns:
            True if authentication successful

        Raises:
            ArcheryAuthError: If authentication fails
        """
        if not self.username or not self.password:
            raise ArcheryAuthError("No credentials provided (username/password)")

        try:
            # Step 1: Get login page to obtain CSRF token
            login_page_url = f"{self.base_url}/login/"
            resp = self.session.get(login_page_url, verify=self.verify_ssl)

            # Get CSRF token from cookies
            csrf_token = self.session.cookies.get('csrftoken')
            if not csrf_token:
                # Try to extract from page content
                import re
                match = re.search(r'csrfmiddlewaretoken.*?value=["\']([^"\']+)["\']', resp.text)
                if match:
                    csrf_token = match.group(1)

            if not csrf_token:
                raise ArcheryAuthError("Could not obtain CSRF token")

            # Step 2: Submit login form
            login_url = f"{self.base_url}/authenticate/"
            login_data = {
                'username': self.username,
                'password': self.password,
                'csrfmiddlewaretoken': csrf_token
            }

            headers = {
                'Referer': login_page_url,
                'Content-Type': 'application/x-www-form-urlencoded',
            }

            resp = self.session.post(
                login_url,
                data=login_data,
                headers=headers,
                verify=self.verify_ssl,
                allow_redirects=True
            )

            # Check if login was successful (redirected to home or no error)
            if resp.status_code == 200 and 'login' not in resp.url.lower():
                self._authenticated = True
                logger.info(f"Successfully logged in to Archery as {self.username}")
                return True

            # Alternative: Try API-based authentication
            return self._login_api()

        except requests.RequestException as e:
            raise ArcheryAuthError(f"Login request failed: {e}")

    def _login_api(self) -> bool:
        """
        Alternative login using Archery API (if available).
        """
        try:
            api_login_url = f"{self.base_url}/api/v1/auth/token/"
            resp = self.session.post(
                api_login_url,
                json={
                    'username': self.username,
                    'password': self.password
                },
                verify=self.verify_ssl
            )

            if resp.status_code == 200:
                data = resp.json()
                token = data.get('token') or data.get('access')
                if token:
                    self.session.headers['Authorization'] = f'Token {token}'
                    self._authenticated = True
                    logger.info(f"Successfully authenticated via API as {self.username}")
                    return True

            raise ArcheryAuthError(f"API login failed with status {resp.status_code}")

        except Exception as e:
            raise ArcheryAuthError(f"API login failed: {e}")

    def ensure_authenticated(self):
        """Ensure client is authenticated, login if not"""
        if not self._authenticated:
            self.login()

    def _get_csrf_token(self) -> str:
        """Get current CSRF token from cookies"""
        return self.session.cookies.get('csrftoken', '')

    def _api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make an API request to Archery.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response data as dict
        """
        self.ensure_authenticated()

        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-CSRFToken': self._get_csrf_token(),
            'Referer': self.base_url,
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
                    return resp.json()
                except json.JSONDecodeError:
                    return {'raw_response': resp.text}
            else:
                raise ArcheryQueryError(
                    f"API request failed with status {resp.status_code}: {resp.text}"
                )

        except requests.RequestException as e:
            raise ArcheryQueryError(f"API request failed: {e}")

    def get_instances(self, db_type: Optional[str] = None) -> List[Dict]:
        """
        Get list of database instances.

        Args:
            db_type: Filter by database type (mysql, mssql, oracle, etc.)

        Returns:
            List of instance dictionaries
        """
        params = {}
        if db_type:
            params['db_type'] = db_type

        result = self._api_request('GET', '/api/v1/instance/', params=params)

        # Handle different response formats
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get('data', result.get('results', []))
        return []

    def get_databases(self, instance_name: str) -> List[str]:
        """
        Get list of databases for an instance.

        Args:
            instance_name: Name of the database instance

        Returns:
            List of database names
        """
        result = self._api_request(
            'GET',
            '/api/v1/instance/databases/',
            params={'instance_name': instance_name}
        )

        if isinstance(result, dict):
            return result.get('data', result.get('databases', []))
        return result if isinstance(result, list) else []

    def sql_check(
        self,
        sql_content: str,
        instance_name: str,
        db_name: str = ''
    ) -> Dict:
        """
        Check SQL syntax and get optimization suggestions.

        Args:
            sql_content: SQL statement to check
            instance_name: Target instance name
            db_name: Target database name

        Returns:
            Check result with suggestions
        """
        data = {
            'sql_content': sql_content,
            'instance_name': instance_name,
            'db_name': db_name
        }

        return self._api_request('POST', '/api/v1/sql/check/', data=data)

    def sql_review(
        self,
        sql_content: str,
        instance_name: str,
        db_name: str,
        workflow_name: Optional[str] = None
    ) -> Dict:
        """
        Submit SQL for review/audit.

        Args:
            sql_content: SQL statement to review
            instance_name: Target instance name
            db_name: Target database name
            workflow_name: Optional workflow name

        Returns:
            Review result
        """
        data = {
            'sql_content': sql_content,
            'instance_name': instance_name,
            'db_name': db_name,
        }
        if workflow_name:
            data['workflow_name'] = workflow_name

        return self._api_request('POST', '/api/v1/sql/review/', data=data)

    def query_execute(
        self,
        sql_content: str,
        instance_name: str,
        db_name: str,
        limit: int = 100
    ) -> Dict:
        """
        Execute a read-only SQL query.

        IMPORTANT: Only SELECT queries are allowed for safety.

        Args:
            sql_content: SQL SELECT statement
            instance_name: Target instance name
            db_name: Target database name
            limit: Maximum rows to return (default 100)

        Returns:
            Query result with columns and rows
        """
        # Safety check: only allow SELECT queries
        sql_upper = sql_content.strip().upper()
        if not sql_upper.startswith('SELECT'):
            raise ArcheryQueryError(
                "Only SELECT queries are allowed. "
                "For DDL/DML operations, please use sql_review to submit a workflow."
            )

        # Add LIMIT if not present
        if 'LIMIT' not in sql_upper:
            sql_content = f"{sql_content.rstrip(';')} LIMIT {limit}"

        data = {
            'sql_content': sql_content,
            'instance_name': instance_name,
            'db_name': db_name,
            'limit_num': limit
        }

        # Try different API endpoints
        try:
            return self._api_request('POST', '/api/v1/query/', data=data)
        except ArcheryQueryError:
            # Fallback to alternative endpoint
            return self._api_request('POST', '/query/execute/', data=data)

    def get_workflow_list(
        self,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get list of SQL workflows/tickets.

        Args:
            status: Filter by status (pending, executing, finished, rejected, etc.)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            limit: Maximum workflows to return

        Returns:
            List of workflow dictionaries
        """
        params = {'limit': limit}
        if status:
            params['status'] = status
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        result = self._api_request('GET', '/api/v1/workflow/', params=params)

        if isinstance(result, dict):
            return result.get('data', result.get('results', []))
        return result if isinstance(result, list) else []

    def get_workflow_detail(self, workflow_id: int) -> Dict:
        """
        Get details of a specific workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow details
        """
        return self._api_request('GET', f'/api/v1/workflow/{workflow_id}/')

    def get_query_history(
        self,
        instance_name: Optional[str] = None,
        db_name: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get query execution history.

        Args:
            instance_name: Filter by instance name
            db_name: Filter by database name
            limit: Maximum records to return

        Returns:
            List of query history records
        """
        params = {'limit': limit}
        if instance_name:
            params['instance_name'] = instance_name
        if db_name:
            params['db_name'] = db_name

        result = self._api_request('GET', '/api/v1/query/history/', params=params)

        if isinstance(result, dict):
            return result.get('data', result.get('results', []))
        return result if isinstance(result, list) else []
