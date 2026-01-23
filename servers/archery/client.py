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

        # Disable proxy for internal domains
        # This is needed when system proxy is set but internal domains should bypass it
        from urllib.parse import urlparse
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

        First tries the API endpoint, then falls back to extracting from query log.

        Args:
            db_type: Filter by database type (mysql, mssql, oracle, etc.)

        Returns:
            List of instance dictionaries
        """
        self.ensure_authenticated()

        # Try API endpoint first
        try:
            params = {}
            if db_type:
                params['db_type'] = db_type
            result = self._api_request('GET', '/api/v1/instance/', params=params)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                instances = result.get('data', result.get('results', []))
                if instances:
                    return instances
        except ArcheryQueryError:
            pass

        # Fallback: extract instances from query log
        return self._get_instances_from_querylog()

    def _get_instances_from_querylog(self) -> List[Dict]:
        """Extract unique instances from query log history."""
        url = f"{self.base_url}/query/querylog/?limit=500&offset=0"
        headers = {
            'X-CSRFToken': self._get_csrf_token(),
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/sqlquery/',
        }

        try:
            resp = self.session.get(url, headers=headers, verify=self.verify_ssl)
            if resp.status_code == 200:
                data = resp.json()
                instances = {}
                for row in data.get('rows', []):
                    inst_name = row.get('instance_name', '')
                    db_name = row.get('db_name', '')
                    if inst_name:
                        if inst_name not in instances:
                            instances[inst_name] = {'instance_name': inst_name, 'databases': set()}
                        if db_name:
                            instances[inst_name]['databases'].add(db_name)

                # Convert to list format
                result = []
                for inst_name, info in instances.items():
                    result.append({
                        'instance_name': inst_name,
                        'databases': list(info['databases'])
                    })
                return result
        except Exception as e:
            logger.warning(f"Failed to get instances from querylog: {e}")

        return []

    def get_databases(self, instance_name: str) -> List[str]:
        """
        Get list of databases for an instance.

        First tries the API endpoint, then falls back to extracting from query log.

        Args:
            instance_name: Name of the database instance

        Returns:
            List of database names
        """
        self.ensure_authenticated()

        # Try API endpoint first
        try:
            result = self._api_request(
                'GET',
                '/api/v1/instance/databases/',
                params={'instance_name': instance_name}
            )
            if isinstance(result, dict):
                dbs = result.get('data', result.get('databases', []))
                if dbs:
                    return dbs
            elif isinstance(result, list) and result:
                return result
        except ArcheryQueryError:
            pass

        # Fallback: extract from query log
        instances = self._get_instances_from_querylog()
        for inst in instances:
            if inst.get('instance_name') == instance_name:
                return inst.get('databases', [])

        return []

    def get_query_log(self, limit: int = 50, offset: int = 0) -> Dict:
        """
        Get SQL query execution history.

        Args:
            limit: Maximum records to return (default 50)
            offset: Offset for pagination (default 0)

        Returns:
            Dict with total count and query log rows
        """
        self.ensure_authenticated()

        url = f"{self.base_url}/query/querylog/?limit={limit}&offset={offset}"
        headers = {
            'X-CSRFToken': self._get_csrf_token(),
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/sqlquery/',
        }

        try:
            resp = self.session.get(url, headers=headers, verify=self.verify_ssl)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise ArcheryQueryError(f"Failed to get query log: status {resp.status_code}")
        except requests.RequestException as e:
            raise ArcheryQueryError(f"Query log request failed: {e}")

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
        Execute a read-only query.

        Supports multiple database types:
        - MySQL/TiDB/PostgreSQL: SELECT statements, SHOW commands
        - MongoDB: db.collection.find(), db.collection.aggregate(), etc.
        - Redis: GET, KEYS, HGETALL, etc.

        Args:
            sql_content: Query statement (syntax depends on database type)
            instance_name: Target instance name
            db_name: Target database name
            limit: Maximum rows to return (default 100)

        Returns:
            Query result with columns and rows
        """
        self.ensure_authenticated()

        # Detect query type and validate
        sql_stripped = sql_content.strip()
        sql_upper = sql_stripped.upper()

        # Check for dangerous operations (basic safety)
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
        # Only check for SQL databases, not MongoDB/Redis
        is_mongodb = sql_stripped.startswith('db.')
        is_redis = any(sql_upper.startswith(cmd) for cmd in ['GET ', 'SET ', 'KEYS ', 'HGET', 'SCAN '])

        if not is_mongodb and not is_redis:
            for keyword in dangerous_keywords:
                if sql_upper.startswith(keyword):
                    raise ArcheryQueryError(
                        f"Dangerous operation '{keyword}' not allowed. "
                        "For DDL/DML operations, please use sql_review to submit a workflow."
                    )

        # For SQL databases, add LIMIT if it's a SELECT and no LIMIT present
        if sql_upper.startswith('SELECT') and 'LIMIT' not in sql_upper:
            sql_content = f"{sql_stripped.rstrip(';')} LIMIT {limit}"

        # Use the web query endpoint (works with session auth)
        url = f"{self.base_url}/query/"
        headers = {
            'X-CSRFToken': self._get_csrf_token(),
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/sqlquery/',
        }

        data = {
            'instance_name': instance_name,
            'db_name': db_name,
            'sql_content': sql_content,
            'limit_num': limit
        }

        try:
            resp = self.session.post(url, data=data, headers=headers, verify=self.verify_ssl)

            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 0:
                    return result.get('data', {})
                else:
                    raise ArcheryQueryError(result.get('msg', 'Query failed'))
            else:
                raise ArcheryQueryError(f"Query failed with status {resp.status_code}")

        except requests.RequestException as e:
            raise ArcheryQueryError(f"Query request failed: {e}")

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

    def get_resource_groups(self) -> List[str]:
        """
        Get list of available resource groups.

        Returns:
            List of resource group names
        """
        self.ensure_authenticated()

        # Get groups from the submit page
        resp = self.session.get(
            f'{self.base_url}/submitsql/',
            verify=self.verify_ssl
        )

        if resp.status_code != 200:
            raise ArcheryQueryError(f"Failed to get resource groups: {resp.status_code}")

        import re
        group_section = re.search(r'id="group_name"[^>]*>(.*?)</select>', resp.text, re.DOTALL)
        if group_section:
            options = re.findall(r'value="([^"]+)"[^>]*>([^<]+)</option>', group_section.group(1))
            return [name for val, name in options if val and val != 'is-empty']

        return []

    def get_group_instances(self, group_name: str) -> List[Dict]:
        """
        Get instances available for a resource group.

        Args:
            group_name: Resource group name

        Returns:
            List of instance dictionaries with id, type, db_type, instance_name
        """
        self.ensure_authenticated()

        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': self._get_csrf_token(),
        }

        resp = self.session.post(
            f'{self.base_url}/group/instances/',
            data={'group_name': group_name},
            headers=headers,
            verify=self.verify_ssl
        )

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get('status') == 0:
                    return data.get('data', [])
            except:
                pass

        raise ArcheryQueryError(f"Failed to get instances for group {group_name}")

    def check_sql_for_workflow(
        self,
        instance_id: int,
        db_name: str,
        sql_content: str
    ) -> Dict:
        """
        Check SQL before submitting workflow.

        Args:
            instance_id: Instance ID (from get_group_instances)
            db_name: Database name
            sql_content: SQL content (DDL/DML)

        Returns:
            Check result with errors/warnings
        """
        self.ensure_authenticated()

        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': self._get_csrf_token(),
            'Content-Type': 'application/json',
        }

        data = {
            'instance_id': instance_id,
            'db_name': db_name,
            'full_sql': sql_content,
        }

        resp = self.session.post(
            f'{self.base_url}/api/v1/workflow/sqlcheck/',
            json=data,
            headers=headers,
            verify=self.verify_ssl
        )

        if resp.status_code == 200:
            return resp.json()

        raise ArcheryQueryError(f"SQL check failed: {resp.text}")

    def _get_group_id_and_name(self, group_name: str) -> tuple:
        """Get resource group ID and actual value by name.

        Returns:
            Tuple of (group_id, group_value) where group_id is numeric and group_value is the form value
        """
        self.ensure_authenticated()

        # Get groups from the submit page
        resp = self.session.get(
            f'{self.base_url}/submitsql/',
            verify=self.verify_ssl
        )

        import re
        # Try to find group select element and extract both value and group_id attribute
        patterns = [
            r'id="group_name"[^>]*>(.*?)</select>',
            r'name="group_name"[^>]*>(.*?)</select>',
        ]

        for pattern in patterns:
            group_section = re.search(pattern, resp.text, re.DOTALL)
            if group_section:
                section_html = group_section.group(1)

                # Try to find options with group_id attribute
                # Format: <option value="TiDB" group_id="6">TiDB</option>
                options_with_attr = re.findall(
                    r'<option[^>]*value="([^"]+)"[^>]*group_id="(\d+)"[^>]*>([^<]+)</option>',
                    section_html
                )
                if options_with_attr:
                    logger.info(f"Found groups with group_id attr: {[(v, gid, n.strip()) for v, gid, n in options_with_attr[:5]]}")
                    for value, group_id, name in options_with_attr:
                        if name.strip() == group_name:
                            return int(group_id), value

                # Also try reversed attribute order
                options_with_attr = re.findall(
                    r'<option[^>]*group_id="(\d+)"[^>]*value="([^"]+)"[^>]*>([^<]+)</option>',
                    section_html
                )
                if options_with_attr:
                    logger.info(f"Found groups (reversed): {[(gid, v, n.strip()) for gid, v, n in options_with_attr[:5]]}")
                    for group_id, value, name in options_with_attr:
                        if name.strip() == group_name:
                            return int(group_id), value

                # Fallback: just get value (might be numeric ID itself)
                options = re.findall(r'value="([^"]+)"[^>]*>([^<]+)</option>', section_html)
                logger.info(f"Found group options (no attr): {[(v, n.strip()) for v, n in options[:5]]}")

                for value, name in options:
                    if name.strip() == group_name and value and value != 'is-empty':
                        if value.isdigit():
                            return int(value), value
                        # Value is not numeric, we need to find group_id elsewhere
                        break

        # Alternative: try API endpoint to get group list with IDs
        try:
            result = self._api_request('GET', '/group/list/')
            if isinstance(result, dict):
                groups = result.get('data', result.get('results', result.get('rows', [])))
            else:
                groups = result if isinstance(result, list) else []

            for g in groups:
                if g.get('group_name') == group_name:
                    group_id = g.get('group_id') or g.get('id')
                    if group_id:
                        return int(group_id), group_name
        except Exception as e:
            logger.warning(f"API group lookup failed: {e}")

        # Try getting groups from group management page
        try:
            resp = self.session.get(f'{self.base_url}/group/', verify=self.verify_ssl)
            # Look for group table data
            rows = re.findall(r'<tr[^>]*>.*?</tr>', resp.text, re.DOTALL)
            for row in rows:
                if group_name in row:
                    id_match = re.search(r'group_id["\s:=]+(\d+)', row)
                    if id_match:
                        return int(id_match.group(1)), group_name
        except Exception as e:
            logger.warning(f"Group page lookup failed: {e}")

        raise ArcheryQueryError(f"Resource group '{group_name}' not found - could not determine group_id")

    def submit_workflow(
        self,
        workflow_name: str,
        group_name: str,
        instance_name: str,
        db_name: str,
        sql_content: str,
        is_backup: bool = True,
        demand_url: str = ''
    ) -> Dict:
        """
        Submit SQL workflow for review.

        This is used for DDL/DML operations that need approval.
        SELECT queries should use query_execute() instead.

        Args:
            workflow_name: Name/title of the workflow
            group_name: Resource group name (from get_resource_groups)
            instance_name: Instance name (from get_group_instances)
            db_name: Target database name
            sql_content: SQL content (DDL/DML statements)
            is_backup: Whether to backup before execution (default True)
            demand_url: Optional demand/ticket URL

        Returns:
            Workflow submission result
        """
        self.ensure_authenticated()

        # Get instance ID and group ID
        instances = self.get_group_instances(group_name)
        instance = next((i for i in instances if i['instance_name'] == instance_name), None)
        if not instance:
            raise ArcheryQueryError(f"Instance '{instance_name}' not found in group '{group_name}'")

        instance_id = instance['id']

        # Get numeric group_id
        group_id = self._get_group_id_from_page(group_name)
        logger.info(f"Submitting workflow: group_name={group_name}, group_id={group_id}, instance_id={instance_id}")

        # Check SQL first
        check_result = self.check_sql_for_workflow(instance_id, db_name, sql_content)
        if check_result.get('is_critical'):
            raise ArcheryQueryError(f"SQL check failed with critical errors: {check_result}")

        # Try REST API first (Archery >= 1.9)
        try:
            return self._submit_workflow_api(
                workflow_name, group_id, instance_id, db_name,
                sql_content, is_backup, demand_url
            )
        except Exception as e:
            logger.warning(f"REST API submission failed: {e}, trying form submission")

        # Fallback to form submission
        return self._submit_workflow_form(
            workflow_name, group_name, group_name, instance_name, instance_id,
            db_name, sql_content, is_backup, demand_url
        )

    def _get_group_id_from_page(self, group_name: str) -> int:
        """Get numeric group_id from submitsql page HTML.

        The submitsql page contains option elements with group-id attribute:
        <option value="TiDB" group-id="6">TiDB</option>
        """
        self.ensure_authenticated()

        import re

        # Method 1: Parse submitsql page for group-id attribute (most reliable)
        try:
            resp = self.session.get(f'{self.base_url}/submitsql/', verify=self.verify_ssl)
            if resp.status_code == 200:
                # Look for group_name select and extract group-id attributes
                # Format: <option value="TiDB" group-id="6">TiDB</option>

                # Match: value="X" followed by group-id="N"
                pattern1 = r'<option[^>]*value="([^"]+)"[^>]*group-id="(\d+)"[^>]*>([^<]*)</option>'
                matches = re.findall(pattern1, resp.text)
                if matches:
                    logger.info(f"Found {len(matches)} groups with group-id attribute")
                    for value, group_id, text in matches:
                        name = text.strip()
                        if name == group_name or value == group_name:
                            logger.info(f"Found group_id={group_id} for {group_name}")
                            return int(group_id)

                # Try reversed attribute order: group-id="N" followed by value="X"
                pattern2 = r'<option[^>]*group-id="(\d+)"[^>]*value="([^"]+)"[^>]*>([^<]*)</option>'
                matches = re.findall(pattern2, resp.text)
                if matches:
                    for group_id, value, text in matches:
                        name = text.strip()
                        if name == group_name or value == group_name:
                            logger.info(f"Found group_id={group_id} for {group_name}")
                            return int(group_id)
        except Exception as e:
            logger.warning(f"Submitsql page parsing failed: {e}")

        # Method 2: Try /group/list/ AJAX endpoint as fallback
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': self._get_csrf_token(),
        }

        for endpoint in ['/group/list/', '/group/group/']:
            try:
                resp = self.session.get(
                    f'{self.base_url}{endpoint}',
                    headers=headers,
                    verify=self.verify_ssl
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get('rows', data.get('data', data.get('results', [])))
                    if not rows and isinstance(data, list):
                        rows = data
                    for row in rows:
                        if row.get('group_name') == group_name:
                            gid = row.get('group_id') or row.get('id')
                            logger.info(f"Found group_id={gid} for {group_name} from API")
                            return int(gid)
            except Exception as e:
                logger.debug(f"Group endpoint {endpoint} failed: {e}")

        raise ArcheryQueryError(f"Could not find numeric group_id for '{group_name}'")

    def _submit_workflow_api(
        self,
        workflow_name: str,
        group_id,  # Can be int or str (group_name)
        instance_id: int,
        db_name: str,
        sql_content: str,
        is_backup: bool,
        demand_url: str
    ) -> Dict:
        """Submit workflow via REST API (Archery >= 1.9)."""
        headers = {
            'X-CSRFToken': self._get_csrf_token(),
            'Content-Type': 'application/json',
            'Referer': f'{self.base_url}/submitsql/',
        }

        data = {
            'sql_content': sql_content,
            'workflow': {
                'workflow_name': workflow_name,
                'group_id': group_id,  # May be numeric ID or group_name string
                'instance': instance_id,
                'db_name': db_name,
                'is_backup': is_backup,
                'demand_url': demand_url,
                'is_offline_export': False,
            }
        }

        resp = self.session.post(
            f'{self.base_url}/api/v1/workflow/',
            json=data,
            headers=headers,
            verify=self.verify_ssl
        )

        logger.info(f"API submit response: status={resp.status_code}")

        if resp.status_code in (200, 201):
            result = resp.json()
            return {'status': 0, 'msg': 'Workflow submitted successfully', 'data': result}

        raise ArcheryQueryError(f"API submission failed: {resp.status_code} - {resp.text[:500]}")

    def _submit_workflow_form(
        self,
        workflow_name: str,
        group_name: str,
        group_value,  # Can be int (ID) or str (name)
        instance_name: str,
        instance_id: int,
        db_name: str,
        sql_content: str,
        is_backup: bool,
        demand_url: str
    ) -> Dict:
        """Submit workflow via form POST (legacy method)."""
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': self._get_csrf_token(),
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': f'{self.base_url}/submitsql/',
        }

        # Use the group_value we got from the form (could be ID or name)
        data = {
            'workflow_name': workflow_name,
            'group_name': group_value,  # Use the actual value from the form
            'instance_name': instance_id,  # Archery uses instance ID here
            'db_name': db_name,
            'sql_content': sql_content,
            'is_backup': '1' if is_backup else '0',
        }
        if demand_url:
            data['demand_url'] = demand_url

        resp = self.session.post(
            f'{self.base_url}/submitsql/',
            data=data,
            headers=headers,
            verify=self.verify_ssl
        )

        logger.info(f"Form submit response: status={resp.status_code}, url={resp.url}")
        logger.info(f"Response text (first 2000): {resp.text[:2000]}")

        if resp.status_code == 200:
            try:
                result = resp.json()
                if result.get('status') == 0:
                    return result
                else:
                    raise ArcheryQueryError(f"Form submission error: {result}")
            except json.JSONDecodeError:
                # HTML response - check for success indicators
                if 'sqlworkflow' in resp.url or '/detail/' in resp.url:
                    return {'status': 0, 'msg': 'Workflow submitted successfully'}
                # Check for error messages in HTML
                import re
                error_match = re.search(r'<div[^>]*class="[^"]*alert[^"]*"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
                if error_match:
                    error_msg = re.sub(r'<[^>]+>', '', error_match.group(1)).strip()
                    raise ArcheryQueryError(f"Form submission error: {error_msg}")
                raise ArcheryQueryError("Form submission failed: unexpected HTML response")

        raise ArcheryQueryError(f"Workflow submission failed: HTTP {resp.status_code}")
