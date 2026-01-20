# MCP DevOps Tools

AI 驱动的 Bug 排查工具，通过 MCP (Model Context Protocol) 让 Claude Code 能够调用 Kibana、Archery 等平台的 API。

## 功能特性

- **Kibana MCP Server**: 查询 ELK 日志、按服务名搜索、错误追踪、链路追踪
- **Archery MCP Server**: SQL 审核、执行查询、管理工单
- **Doris MCP Server**: OLAP 数据查询（可选）

## Kibana MCP 工具列表

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

### search_logs 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `index` | string | ✅ | 索引模式，如 "logs-*", "app-logs-*" |
| `keyword` | string | ❌ | 日志内容关键词 |
| `time_range` | string | ❌ | 相对时间范围，如 "1h", "24h", "7d"（默认 "1h"） |
| `level` | string | ❌ | 日志级别：error, warn, info |
| `size` | int | ❌ | 返回数量，默认 50，最大 500 |
| `start_time` | string | ❌ | 绝对开始时间 (ISO格式)，如 "2024-01-19T19:00:00+08:00" |
| `end_time` | string | ❌ | 绝对结束时间 (ISO格式)，如 "2024-01-19T20:00:00+08:00" |

**示例：**

```python
# 使用相对时间
search_logs(index="logs-*", keyword="Exception", time_range="24h", level="error")

# 使用绝对时间（查询某一天19:00-20:00的日志）
search_logs(index="logs-*", start_time="2024-01-19T19:00:00+08:00", end_time="2024-01-19T20:00:00+08:00")
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

## Archery MCP 工具列表

| 工具 | 功能 | 推荐场景 |
|------|------|----------|
| `get_instances` | 列出数据库实例 | **AI 首先调用**，发现可用的数据库实例 |
| `get_databases` | 列出数据库 | 获取实例下的数据库列表 |
| `query_execute` | 执行只读查询 | **推荐使用**，执行 SELECT 查询 |
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
| `sql_content` | string | ✅ | SQL SELECT 语句（仅支持只读查询） |
| `instance_name` | string | ✅ | 数据库实例名（从 get_instances 获取） |
| `db_name` | string | ✅ | 数据库名（从 get_databases 获取） |
| `limit` | int | ❌ | 返回行数限制，默认 100，最大 1000 |

**示例：**

```python
# 查询用户表
query_execute(
    sql_content="SELECT * FROM users WHERE status = 1",
    instance_name="prod-mysql-master",
    db_name="user_db",
    limit=50
)
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入实际的账号密码
```

### 3. 启动 MCP Server

```bash
# 启动 Kibana MCP Server (端口 8000)
python -m servers.kibana

# 启动 Archery MCP Server (端口 8001)
python -m servers.archery

# 或启动所有服务
python -m main
```

### 4. 在 Claude Code 中注册

```bash
# 注册 Kibana MCP
claude mcp add --transport http kibana http://localhost:8000/mcp

# 注册 Archery MCP
claude mcp add --transport http archery http://localhost:8001/mcp
```

### 5. 使用

```
> 帮我查询最近1小时的错误日志
> 搜索包含 "NullPointerException" 的日志
> 用 Archery 查询 user_db 的用户表
> 审核这个 SQL: ALTER TABLE users ADD COLUMN phone VARCHAR(20)
```

## 项目结构

```
mcp-devops-tools/
├── docs/
│   ├── PLAN.md           # 开发计划
│   └── PROGRESS.md       # 进度跟踪
├── servers/
│   ├── kibana/           # Kibana MCP Server
│   ├── archery/          # Archery MCP Server
│   └── doris/            # Doris MCP Server
├── common/               # 公共模块
├── tests/                # 测试代码
├── .env.example          # 环境变量示例
├── requirements.txt      # Python 依赖
└── README.md             # 本文件
```

## 文档

- [开发计划](docs/PLAN.md)
- [进度跟踪](docs/PROGRESS.md)

## 安全注意事项

- 所有密码存储在本地 `.env` 文件中，不要提交到版本控制
- SQL 查询限制为只读操作
- 建议使用只读权限的账号
