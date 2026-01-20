# MCP Server 开发计划 - AI 驱动的 Bug 排查工具

## 项目目标

开发一套 MCP (Model Context Protocol) Server，让 Claude Code 能够调用 Archery、ELK、Doris 等平台的 API，实现 AI 辅助的生产环境 bug 排查。

## 技术选型

- **开发语言**: Python
- **协议**: MCP (Model Context Protocol) - HTTP Transport
- **目标集成**: Claude Code（交互式） + Claude Agent SDK（自动化）

---

## 实际环境信息

| 平台 | URL | 登录方式 |
|------|-----|----------|
| **Kibana** | `https://kibana-new.naloc.cn` | 账号密码 |
| **Archery** | `http://archery.basic.akops.internal` | 账号密码 |
| **Doris** | 待确认 | 待确认 |

---

## 阶段一：基础设施搭建

### 1.1 项目结构
```
mcp-devops-tools/
├── docs/
│   ├── PLAN.md           # 本文档 - 开发计划
│   └── PROGRESS.md       # 进度跟踪
├── servers/
│   ├── __init__.py
│   ├── kibana/           # Kibana MCP Server
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── client.py
│   ├── archery/          # Archery MCP Server
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── client.py
│   └── doris/            # Doris MCP Server
│       ├── __init__.py
│       ├── server.py
│       └── client.py
├── common/               # 公共模块
│   ├── __init__.py
│   ├── auth.py           # 认证相关
│   └── utils.py          # 工具函数
├── tests/                # 测试代码
├── .env.example          # 环境变量示例
├── .gitignore
├── requirements.txt
└── README.md
```

### 1.2 依赖列表
```
mcp                    # MCP Python SDK
requests              # HTTP 请求
pydantic              # 数据验证
python-dotenv         # 环境变量管理
```

---

## 阶段二：MCP Server 开发

### 2.1 Kibana MCP Server（优先开发）

**工具列表**:
| 工具名 | 功能 | 参数 | 状态 |
|--------|------|------|------|
| `list_services` | 列出可用服务名 | index_pattern, time_range | ✅ 已完成 |
| `search_logs_by_service` | 按服务名搜索日志 | service_name, keyword, time_range, level, pod_name, trace_id, namespace | ✅ 已完成 |
| `search_logs` | 通用日志搜索 | index, keyword, time_range, level, size | ✅ 已完成 |
| `get_error_logs` | 获取错误日志 | index, time_range, size | ✅ 已完成 |
| `list_indices` | 列出可用索引 | pattern | ✅ 已完成 |
| `get_index_mapping` | 获取索引字段映射 | index | ✅ 已完成 |
| `execute_es_query` | 执行原始 ES 查询 | method, path, body | ✅ 已完成 |
| `get_cluster_health` | 获取集群健康状态 | - | ✅ 已完成 |

**AI 推荐使用流程**:
```
1. list_services() -> 获取可用服务列表
2. search_logs_by_service(service_name="xxx") -> 按服务查询日志
```

**认证方式**: 账号密码登录 -> 获取 Session

### 2.2 Archery MCP Server

**工具列表**:
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `sql_check` | SQL 语法检查 | sql_content, instance_name |
| `sql_review` | SQL 审核 | sql_content, instance_name, db_name |
| `get_workflow_list` | 获取工单列表 | status, start_date, end_date |
| `get_workflow_detail` | 获取工单详情 | workflow_id |
| `query_execute` | 执行只读查询 | sql_content, instance_name, db_name |

**认证方式**: 账号密码登录（Django Session）

### 2.3 Doris MCP Server（待确认环境）

**工具列表**:
| 工具名 | 功能 | 参数 |
|--------|------|------|
| `execute_query` | 执行查询 | sql, database |
| `list_databases` | 列出数据库 | - |
| `list_tables` | 列出表 | database |
| `describe_table` | 获取表结构 | database, table |

**认证方式**: MySQL 协议

---

## 阶段三：Claude Code 集成

### 3.1 启动 MCP Server
```bash
# 启动单个服务
python -m servers.kibana --port 8001

# 或合并启动
python -m main --port 8000
```

### 3.2 注册到 Claude Code
```bash
claude mcp add --transport http kibana http://localhost:8001/mcp
claude mcp add --transport http archery http://localhost:8002/mcp
```

### 3.3 使用示例
```
> 帮我查询最近1小时的错误日志
> 用 Archery 审核这个 SQL: SELECT * FROM users WHERE id = 1
```

---

## 阶段四：认证方案

### 4.1 账号密码认证（推荐）

#### Kibana 登录示例
```python
import requests

class KibanaClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(username, password)

    def _login(self, username: str, password: str):
        # Kibana 登录接口
        resp = self.session.post(
            f"{self.base_url}/internal/security/login",
            json={
                "providerType": "basic",
                "providerName": "basic",
                "currentURL": f"{self.base_url}/login",
                "params": {
                    "username": username,
                    "password": password
                }
            },
            headers={"kbn-xsrf": "true"}
        )
        return resp.status_code == 200
```

#### Archery 登录示例
```python
class ArcheryClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.session = requests.Session()
        self._login(username, password)

    def _login(self, username: str, password: str):
        # 1. 获取 CSRF Token
        self.session.get(f"{self.base_url}/login/")
        csrf_token = self.session.cookies.get('csrftoken')

        # 2. 提交登录
        self.session.post(
            f"{self.base_url}/authenticate/",
            data={
                'username': username,
                'password': password,
                'csrfmiddlewaretoken': csrf_token
            },
            headers={'Referer': f"{self.base_url}/login/"}
        )
```

### 4.2 环境变量配置

```env
# .env 文件

# Kibana
KIBANA_URL=https://kibana-new.naloc.cn
KIBANA_USERNAME=your_username
KIBANA_PASSWORD=your_password

# Archery
ARCHERY_URL=http://archery.basic.akops.internal
ARCHERY_USERNAME=your_username
ARCHERY_PASSWORD=your_password

# Doris（待确认）
DORIS_HOST=doris.company.com
DORIS_PORT=9030
DORIS_USERNAME=your_username
DORIS_PASSWORD=your_password
```

---

## 阶段五：安全措施

- [ ] 所有 SQL 执行限制为只读操作（SELECT）
- [ ] 配置查询超时时间
- [ ] 限制返回结果数量
- [ ] 敏感字段脱敏（手机号、身份证等）
- [ ] 操作日志记录

---

## 阶段六：自动化扩展（可选）

使用 Claude Agent SDK 构建自动化流程：

```python
from claude_code_sdk import query, ClaudeCodeOptions

async def diagnose_issue(issue_description: str):
    options = ClaudeCodeOptions(
        mcp_servers={
            "kibana": {"type": "http", "url": "http://localhost:8001/mcp"},
            "archery": {"type": "http", "url": "http://localhost:8002/mcp"}
        },
        allowed_tools=["mcp__*"]
    )

    async for message in query(
        prompt=f"请帮我排查这个问题：{issue_description}",
        options=options
    ):
        yield message
```

---

## 参考资源

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Archery API 文档](https://demo.archerydms.com/api/swagger/)
- [Kibana API 文档](https://www.elastic.co/guide/en/kibana/current/api.html)
- [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk)
