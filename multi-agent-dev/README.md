# Multi-Agent Collaborative Development System

多智能体协作开发系统 — 从自然语言需求到可运行代码的全自动开发流水线。

4 个 AI Agent（产品经理、架构师、程序员、审查员）各司其职，通过 MCP 工具协议真正操作文件系统、执行命令、管理 Git，将一句话需求自动转化为完整可运行的项目。

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)              │
│  需求输入 / 流式渲染 / 审批按钮 / 文件树 / 进度条         │
└────────────────────────┬────────────────────────────┘
                         │ yields DevMessage (Generator)
┌────────────────────────▼────────────────────────────┐
│               DevEngine (core/engine.py)            │
│  7 阶段状态机 / Agent 间上下文传递 / 审批门 / 修复循环    │
└────────────────────────┬────────────────────────────┘
                         │ agent.run_with_tools()
┌────────────────────────▼────────────────────────────┐
│                Agent Layer (agents/)                │
│  BaseAgent → ToolAgent (Agentic tool-calling loop)  │
│  PM  │  Architect  │  Programmer  │  Reviewer       │
└────────────────────────┬────────────────────────────┘
                         │ execute_tool()
┌────────────────────────▼──────────────────────────────┐
│             MCP Server Layer (mcp_servers/)           │
│  filesystem_server  │  terminal_server  │  git_server │
└────────────────────────┬──────────────────────────────┘
                         │ OS operations (sandboxed)
┌────────────────────────▼────────────────────────────┐
│              workspace/<project_name>/              │
│  requirements.md / design.md / src/ / tests/        │
└─────────────────────────────────────────────────────┘
```

## Features

### 4 Agent 协作分工

| Agent | 角色 | 可用工具 | 产出 |
|:---:|:---:|---------|------|
| PM | 产品经理 | read_file, write_file, list_directory | requirements.md（用户故事 + 验收标准） |
| Architect | 架构师 | read_file, write_file, list_directory, run_command | design.md（技术方案 + 文件结构 + Mermaid 架构图） |
| Programmer | 程序员 | 全部 10 个工具 | 完整源代码 + Git 初始提交 |
| Reviewer | 审查员 | read_file, list_directory, search_files, run_command | 测试报告 + 修复建议 |

### 7 阶段自动化流水线

```
需求输入 → 需求分析(PM) → [人工审批] → 架构设计(Architect) → [人工审批]
→ 编码实现(Programmer) → 测试修复循环(Reviewer↔Programmer) → Git提交 → 交付总结
```

- **Human-in-the-Loop 审批门**：需求文档和架构设计完成后暂停，等待用户审批通过/重新生成，确保方向正确
- **自动测试修复循环**：Reviewer 发现 bug → 错误信息传给 Programmer 修复 → 重新测试，最多 3 轮

### MCP 工具协议

10 个沙箱化工具，所有操作限定在 workspace 目录内：

| Server | 工具 | 说明 |
|--------|------|------|
| filesystem | `read_file` | 读取文件内容 |
| filesystem | `write_file` | 创建/覆写文件 |
| filesystem | `list_directory` | 递归列出目录树 |
| filesystem | `search_files` | 按关键词搜索文件内容 |
| terminal | `run_command` | 执行 shell 命令（带超时 + 命令黑名单） |
| git | `git_init` | 初始化 Git 仓库 |
| git | `git_add` | 暂存文件 |
| git | `git_commit` | 提交变更 |
| git | `git_status` | 查看仓库状态 |
| git | `git_diff` | 查看文件差异 |

### 流式渲染 & 实时可视化

- Token 级别流式输出：Agent 思考过程实时可见
- 工具调用实时展示：每次文件读写、命令执行都即时显示在 UI
- 阶段分隔线 + 角色标签：清晰区分当前阶段和发言 Agent

## Tech Stack

- **LLM**: DeepSeek（OpenAI 兼容 API，支持 Function Calling）
- **Agent 框架**: 自研 ToolAgent（Agentic tool-calling loop）
- **工具层**: MCP 协议设计，Python 函数实现
- **前端**: Streamlit（流式渲染 + 审批交互）
- **安全**: 命令黑名单、路径遍历防护、workspace 沙箱隔离

## Project Structure

```
multi-agent-dev/
├── app.py                          # Streamlit 主界面
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
│
├── agents/
│   ├── base.py                     # BaseAgent — speak / speak_stream
│   ├── tool_agent.py               # ToolAgent — Agentic tool-calling loop 核心
│   ├── pm.py                       # 产品经理 Agent
│   ├── architect.py                # 架构师 Agent
│   ├── programmer.py               # 程序员 Agent
│   └── reviewer.py                 # 审查员 Agent
│
├── core/
│   ├── config.py                   # API 配置 + 安全策略
│   ├── models.py                   # DevMessage / DevState / Phase / MessageType
│   ├── engine.py                   # DevEngine — 7 阶段 Generator 编排引擎
│   └── workspace.py                # workspace 创建 / 列表 / 隔离
│
├── mcp_servers/
│   ├── filesystem_server.py        # 文件系统工具（读/写/列目录/搜索）
│   ├── terminal_server.py          # 终端工具（沙箱化命令执行）
│   ├── git_server.py               # Git 工具（init/add/commit/status/diff）
│   └── registry.py                 # 统一工具注册 + 角色权限过滤
│
├── prompts/
│   ├── pm_system.md                # PM 系统提示词
│   ├── architect_system.md         # 架构师系统提示词
│   ├── programmer_system.md        # 程序员系统提示词
│   └── reviewer_system.md          # 审查员系统提示词
│
├── ui/
│   ├── components.py               # 消息卡片 / 阶段分隔线 / 流式占位符
│   └── styles.py                   # CSS 样式
│
└── workspace/                      # 生成的项目输出目录
```

## Quick Start

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

### 3. 启动应用

```bash
streamlit run app.py
```

### 4. 输入需求

在文本框中输入自然语言需求，例如：

> 用 Python 写一个命令行待办事项管理工具，支持增删改查和持久化存储

点击 **"🚀 开始开发"**，系统将自动完成：
1. PM 分析需求 → 生成 `requirements.md` → 等待你审批
2. 架构师设计方案 → 生成 `design.md` + 创建目录结构 → 等待你审批
3. 程序员逐文件编写完整代码
4. 审查员运行测试 → 发现问题自动交给程序员修复（最多 3 轮）
5. 自动 Git init + commit
6. 输出项目交付总结 + 文件树

生成的项目在 `workspace/` 目录下，即开即用。

## Core Design

### ToolAgent — Agentic Tool-Calling Loop

系统的核心组件，桥接 LLM Function Calling 与 MCP 工具执行：

```
LLM 响应 → 包含 tool_calls?
  ├─ 是 → 逐个执行工具 → 结果追加到上下文 → 重新调 LLM（循环）
  └─ 否 → 流式输出最终文本（token by token）
```

- 每个 Agent 按角色过滤可用工具（最小权限原则）
- 最多 20 次工具调用迭代，防止死循环
- 工具执行失败时，错误信息作为 tool result 返回给 LLM 自行调整

### Generator 流式架构

全链路使用 Python Generator 模式传递消息，实现真正的实时流式渲染：

```
ToolAgent.run_with_tools()  →  DevEngine.run()  →  Streamlit UI
     yields DevMessage          yields DevMessage     renders in real-time
```

审批门通过 Generator 的 `send()` 协议实现暂停/恢复。

### 安全沙箱

- **路径遍历防护**: 所有文件操作使用 `os.path.realpath()` 校验，禁止 `..` 跳出 workspace
- **命令黑名单**: 拦截 `rm -rf /`、`sudo`、`shutdown` 等危险命令
- **执行超时**: shell 命令默认 30 秒超时
- **workspace 隔离**: 每个项目在独立目录中运行

## Roadmap

- [ ] **Phase 1: FastAPI 后端** — 把 DevEngine 包装成 RESTful API，SSE 流式推送替代 Streamlit 轮询
  - [ ] FastAPI 路由：`/api/dev/start`（SSE 流式开发）、`/api/dev/approve`（审批）、`/api/workspace/*`（文件浏览/下载）
  - [ ] 将 Generator `yield DevMessage` 转为 SSE `event-stream` 推送
  - [ ] 审批门改为异步等待（前端 POST 审批结果，后端 resume Generator）
  - [ ] `core/` 和 `agents/` 零改动，仅替换 UI 层

- [ ] **Phase 2: PostgreSQL 数据库** — 用户系统 + 项目持久化 + 消息历史
  - [ ] 数据模型：User / Project / Message 三表设计
  - [ ] SQLAlchemy 2.0 ORM + Alembic 迁移管理
  - [ ] JWT 用户认证（注册/登录）
  - [ ] 项目 CRUD + 开发消息持久化（含工具调用记录 JSON 字段）
  - [ ] 历史项目回看：按时间线回放完整开发过程

## License

MIT
