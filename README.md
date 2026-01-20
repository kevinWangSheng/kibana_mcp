# MCP DevOps Tools

AI 驱动的 Bug 排查工具，通过 MCP (Model Context Protocol) 让 Claude Code 能够调用 Kibana、Archery、Doris 等平台的 API。

## 功能特性

| MCP Server | 端口 | 用途 |
|------------|------|------|
| **Kibana** | 8000 | 查询 3 天内的 ELK 日志 |
| **Archery** | 8001 | SQL 数据库查询（MySQL、TiDB、MongoDB、Redis） |
| **Doris** | 8002 | 查询 3 天以上的历史日志（Ops-Cloud） |

## 快速开始

### 1. 安装依赖

```bash
cd D:\dev\AI\mcp-devops-tools
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入实际的账号密码
```

`.env` 配置示例：
```ini
# Kibana / Elasticsearch
KIBANA_URL=https://kibana.example.com
KIBANA_USERNAME=your_username
KIBANA_PASSWORD=your_password

# Archery SQL Platform
ARCHERY_URL=http://archery.example.internal
ARCHERY_USERNAME=your_username
ARCHERY_PASSWORD=your_password

# Doris / Ops-Cloud (Historical Logs)
DORIS_URL=http://ops-cloud.example.internal
DORIS_USERNAME=your_username
DORIS_PASSWORD=your_password
DORIS_TOKEN=  # 可选，留空会自动通过账号密码获取
```

### 3. 启动 MCP Server

**方式一：使用启动脚本（推荐）**

```cmd
# 启动所有服务
D:\dev\AI\mcp-devops-tools\start_all.bat

# 停止所有服务
D:\dev\AI\mcp-devops-tools\stop_all.bat
```

**方式二：单独启动**

```bash
# 启动 Kibana MCP Server (端口 8000)
python -m servers.kibana.server --port=8000

# 启动 Archery MCP Server (端口 8001)
python -m servers.archery.server --port=8001

# 启动 Doris MCP Server (端口 8002)
python -m servers.doris.server --port=8002
```

### 4. 在 Claude Code 中注册 MCP

**方式一：使用命令行（推荐）**

```bash
# 添加到当前项目
claude mcp add kibana --transport http --url http://localhost:8000/mcp
claude mcp add archery --transport http --url http://localhost:8001/mcp
claude mcp add doris --transport http --url http://localhost:8002/mcp

# 或者添加到全局（所有项目可用）
claude mcp add kibana --transport http --url http://localhost:8000/mcp --scope user
claude mcp add archery --transport http --url http://localhost:8001/mcp --scope user
claude mcp add doris --transport http --url http://localhost:8002/mcp --scope user
```

**方式二：编辑配置文件**

编辑 `C:\Users\<用户名>\.claude.json`：

```json
{
  "projects": {
    "D:/dev/AI": {
      "mcpServers": {
        "kibana": {
          "type": "http",
          "url": "http://localhost:8000/mcp"
        },
        "archery": {
          "type": "http",
          "url": "http://localhost:8001/mcp"
        },
        "doris": {
          "type": "http",
          "url": "http://localhost:8002/mcp"
        }
      }
    }
  }
}
```

或添加到全局 `mcpServers`（文件末尾附近）使所有项目都能使用：

```json
{
  "mcpServers": {
    "kibana": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    },
    "archery": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    },
    "doris": {
      "type": "http",
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

> **注意：** 修改配置后需要重启 Claude Code 生效。

---

## Kibana MCP 工具列表

**用途：查询 3 天内的 ELK 日志**

| 工具 | 功能 | 推荐场景 |
|------|------|----------|
| `list_services` | 列出可用的服务名 | **AI 首先调用**，发现可查询的服务 |
| `search_logs_by_service` | 按服务名查询日志 | **推荐使用**，精确查询某服务的日志 |
| `search_logs` | 通用日志搜索 | 按索引模式搜索，支持精确时间范围 |
| `get_error_logs` | 获取错误日志 | 快速获取 ERROR 级别日志 |
| `execute_es_query` | 执行原始 ES 查询 | 高级用户自定义查询 |
| `list_indices` | 列出索引 | 查看可用的索引模式 |
| `get_index_mapping` | 获取索引字段映射 | 了解日志字段结构 |
| `get_cluster_health` | 获取集群健康状态 | 检查 ES 集群状态 |

### AI 推荐使用流程

```
1. 调用 list_services() 获取可用服务列表
2. 调用 search_logs_by_service(service_name="xxx", ...) 查询具体服务的日志
```

### search_logs_by_service 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `service_name` | string | ✅ | 服务名（从 list_services 获取） |
| `keyword` | string | ❌ | 日志内容关键词 |
| `time_range` | string | ❌ | 时间范围，如 "1h", "24h", "7d" |
| `level` | string | ❌ | 日志级别：error, warn, info |
| `size` | int | ❌ | 返回数量，默认 50，最大 500 |
| `pod_name` | string | ❌ | 按 Pod 名称过滤 |
| `trace_id` | string | ❌ | 按链路追踪 ID 过滤 |
| `namespace` | string | ❌ | 按 K8s 命名空间过滤 |

---

## Archery MCP 工具列表

**用途：SQL 数据库查询（支持 MySQL、TiDB、MongoDB、Redis）**

| 工具 | 功能 | 推荐场景 |
|------|------|----------|
| `get_instances` | 列出数据库实例 | **AI 首先调用**，发现可用的数据库实例 |
| `get_databases` | 列出数据库 | 获取实例下的数据库列表 |
| `query_execute` | 执行查询 | **推荐使用**，执行 SELECT/SHOW 查询 |
| `sql_check` | SQL 语法检查 | 检查 SQL 语法和优化建议 |
| `sql_review` | SQL 审核提交 | 提交 DDL/DML 工单 |
| `get_workflow_list` | 获取工单列表 | 查看 SQL 审核工单 |
| `get_workflow_detail` | 获取工单详情 | 查看工单详细信息 |
| `get_query_history` | 查询历史 | 查看 SQL 执行历史 |

### AI 推荐使用流程

```
1. 调用 get_instances() 获取可用数据库实例
2. 调用 get_databases(instance_name="xxx") 获取数据库列表
3. 调用 query_execute(sql_content="SELECT ...", instance_name="xxx", db_name="xxx") 执行查询
```

### query_execute 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sql_content` | string | ✅ | SQL 语句（SELECT、SHOW 等只读查询） |
| `instance_name` | string | ✅ | 数据库实例名（从 get_instances 获取） |
| `db_name` | string | ✅ | 数据库名（从 get_databases 获取） |
| `limit` | int | ❌ | 返回行数限制，默认 100，最大 1000 |

**示例：**

```python
# MySQL 查询
query_execute(
    sql_content="SELECT * FROM users WHERE status = 1",
    instance_name="prod-mysql-master",
    db_name="user_db",
    limit=50
)

# TiDB 查询
query_execute(
    sql_content="SHOW TABLES",
    instance_name="tidb-common1",
    db_name="order_db"
)
```

---

## Doris MCP 工具列表

**用途：查询 3 天以上的历史日志（通过 Ops-Cloud 平台）**

| 工具 | 功能 | 推荐场景 |
|------|------|----------|
| `list_services` | 列出可用服务 | **AI 首先调用**，发现可查询的服务 |
| `list_environments` | 列出环境 | 获取可用环境列表（如 amz、rd生产 等） |
| `get_fields` | 获取字段列表 | 了解某环境下可查询的字段 |
| `search_historical_logs` | 搜索历史日志 | **推荐使用**，查询 3 天以上的日志 |
| `get_historical_error_logs` | 获取历史错误日志 | 快速获取历史 ERROR 日志 |
| `search_by_trace_id` | 按 Trace ID 搜索 | 分布式链路追踪 |

### AI 推荐使用流程

```
1. 调用 list_services() 获取可用服务列表
2. 调用 list_environments() 获取环境列表（如 "rd生产"）
3. 调用 search_historical_logs(service_name="xxx", environment="rd生产", ...) 查询日志
```

### search_historical_logs 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `service_name` | string | ✅ | 服务名（从 list_services 获取） |
| `keyword` | string | ❌ | 日志内容关键词 |
| `level` | string | ❌ | 日志级别：ERROR, WARN, INFO, DEBUG |
| `days_ago_start` | int | ❌ | 开始时间（几天前），默认 7 |
| `days_ago_end` | int | ❌ | 结束时间（几天前），默认 3，最小 3 |
| `environment` | string | ❌ | 环境名称，默认 "amz" |
| `limit` | int | ❌ | 返回数量，默认 100，最大 1000 |

**示例：**

```python
# 查询 7-3 天前的日志
search_historical_logs(
    service_name="cepf-data-collection-task",
    environment="rd生产",
    days_ago_start=7,
    days_ago_end=3
)

# 查询历史错误日志
get_historical_error_logs(
    service_name="order-service",
    days_ago_start=14,
    days_ago_end=7
)
```

### Token 自动刷新

Doris MCP 支持 Token 自动刷新：
- 如果提供了 `DORIS_TOKEN`，会优先使用
- 如果 Token 过期或无效，会自动使用 `DORIS_USERNAME` 和 `DORIS_PASSWORD` 重新登录获取新 Token
- 无需手动从浏览器复制 Token

---

## 日志查询策略

| 日志时间 | 使用的 MCP | 说明 |
|----------|------------|------|
| 3 天内 | **Kibana** | 实时日志，存储在 ELK 中 |
| 3 天以上 | **Doris** | 历史日志，存储在 Doris/Ops-Cloud 中 |

---

## 项目结构

```
mcp-devops-tools/
├── servers/
│   ├── kibana/           # Kibana MCP Server
│   │   ├── client.py     # Kibana API 客户端
│   │   └── server.py     # MCP 服务端
│   ├── archery/          # Archery MCP Server
│   │   ├── client.py     # Archery API 客户端
│   │   └── server.py     # MCP 服务端
│   └── doris/            # Doris MCP Server
│       ├── client.py     # Ops-Cloud API 客户端
│       └── server.py     # MCP 服务端
├── common/
│   └── config.py         # 配置管理
├── .env.example          # 环境变量示例
├── .env                   # 环境变量（不提交到 Git）
├── requirements.txt      # Python 依赖
├── start_all.bat         # 一键启动脚本
├── stop_all.bat          # 一键停止脚本
└── README.md             # 本文件
```

---

## 安全注意事项

- 所有密码存储在本地 `.env` 文件中，不要提交到版本控制
- SQL 查询限制为只读操作（SELECT、SHOW）
- 建议使用只读权限的账号
- Token 会自动刷新，无需手动维护

---

## 常见问题

### Q: 提示连接超时或代理错误？

服务已配置自动绕过内部域名的代理（`.internal`、`.local`、`192.168.*`、`10.*`），如果仍有问题，检查系统代理设置。

### Q: Doris Token 过期怎么办？

无需手动处理，只要配置了 `DORIS_USERNAME` 和 `DORIS_PASSWORD`，系统会自动重新登录获取新 Token。

### Q: 如何查看 MCP 是否正常运行？

```bash
# 检查端口是否被监听
netstat -an | findstr "8000 8001 8002"
```

### Q: Claude Code 没有显示 MCP 工具？

1. 确保 MCP 服务已启动
2. 确保已添加 MCP 到 Claude Code 配置
3. 重启 Claude Code
