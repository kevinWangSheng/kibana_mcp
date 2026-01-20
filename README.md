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
# 启动 Kibana MCP Server
python -m servers.kibana

# 或启动所有服务
python -m main
```

### 4. 在 Claude Code 中注册

```bash
claude mcp add --transport http kibana http://localhost:8000/mcp
```

### 5. 使用

```
> 帮我查询最近1小时的错误日志
> 搜索包含 "NullPointerException" 的日志
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
