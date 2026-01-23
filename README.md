# MCP DevOps Tools

AI 驱动的 Bug 排查工具，通过 MCP (Model Context Protocol) 让 Claude Code 能够调用 Kibana、Archery、Doris 等平台的 API。

## 功能特性

| MCP Server | 端口 | 用途 |
|------------|------|------|
| **Kibana** | 8000 | 查询 3 天内的 ELK 日志 |
| **Archery** | 8001 | SQL 数据库查询 + 工单提交 |
| **Doris** | 8002 | 查询 3 天以上的历史日志 |

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

### 3. 启动 MCP Server

```cmd
# 后台启动（无窗口）
D:\dev\AI\mcp-devops-tools\start_all_background.bat

# 前台启动（有窗口，方便查看日志）
D:\dev\AI\mcp-devops-tools\start_all.bat

# 查看状态
D:\dev\AI\mcp-devops-tools\status.bat

# 停止所有服务
D:\dev\AI\mcp-devops-tools\stop_all.bat
```

### 4. 在 Claude Code 中注册 MCP

```bash
# 添加到当前项目
claude mcp add kibana --transport http --url http://localhost:8000/mcp
claude mcp add archery --transport http --url http://localhost:8001/mcp
claude mcp add doris --transport http --url http://localhost:8002/mcp
```

---

## Kibana MCP 工具列表

**用途：查询 3 天内的 ELK 日志**

| 工具 | 功能 |
|------|------|
| `list_services` | 列出可用服务（首先调用） |
| `search_logs_by_service` | 按服务名查询日志（推荐） |
| `search_logs` | 通用日志搜索 |
| `get_error_logs` | 获取错误日志 |

---

## Archery MCP 工具列表

**用途：SQL 数据库查询 + DDL/DML 工单提交**

### 查询工具

| 工具 | 功能 |
|------|------|
| `get_instances` | 列出数据库实例（首先调用） |
| `get_databases` | 列出数据库 |
| `query_execute` | 执行 SELECT/SHOW 查询（推荐） |

### 工单工具

| 工具 | 功能 |
|------|------|
| `get_resource_groups` | 获取资源组列表（提交工单前首先调用） |
| `get_group_instances` | 获取资源组的实例 |
| `check_sql` | SQL 语法检查 |
| `submit_workflow` | 提交 DDL/DML 审核工单 |
| `get_workflow_list` | 获取工单列表 |
| `get_workflow_detail` | 获取工单详情 |

### 提交工单流程

```
1. get_resource_groups() -> 获取资源组列表
2. get_group_instances(group_name="TiDB") -> 获取该组的实例
3. check_sql(instance_name, db_name, sql_content) -> 检查 SQL
4. submit_workflow(workflow_name, group_name, instance_name, db_name, sql_content) -> 提交工单
```

### 示例

```python
# 提交工单
submit_workflow(
    workflow_name="添加 remark 字段",
    group_name="TiDB",
    instance_name="cepf-tidb",
    db_name="cepf_order",
    sql_content="ALTER TABLE orders ADD COLUMN remark VARCHAR(200);",
    is_backup=True
)
```

---

## Doris MCP 工具列表

**用途：查询 3 天以上的历史日志（Ops-Cloud）**

| 工具 | 功能 |
|------|------|
| `list_services` | 列出可用服务（首先调用） |
| `list_environments` | 列出环境列表 |
| `search_historical_logs` | 搜索历史日志（推荐） |
| `get_historical_error_logs` | 获取历史错误日志 |
| `search_by_trace_id` | 按 Trace ID 搜索 |

### Token 自动刷新

Doris MCP 支持 Token 自动刷新，无需手动从浏览器复制 Token。

---

## 日志查询策略

| 日志时间 | 使用的 MCP |
|----------|------------|
| 3 天内 | **Kibana** |
| 3 天以上 | **Doris** |

---

## 项目结构

```
mcp-devops-tools/
├── servers/
│   ├── kibana/           # Kibana MCP Server
│   ├── archery/          # Archery MCP Server
│   └── doris/            # Doris MCP Server
├── common/
│   └── config.py         # 配置管理
├── .env                  # 环境变量
├── start_all.bat         # 前台启动
├── start_all_background.bat  # 后台启动
├── stop_all.bat          # 停止服务
├── status.bat            # 查看状态
└── README.md
```
