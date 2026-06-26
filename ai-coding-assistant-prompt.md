# AI 编程助手终端应用 — 完整开发提示词

> 将以下内容提供给 AI 编程工具，用于从零实现一个类似 MiMoCode 的终端原生 AI 编程助手。可使用任意编程语言。

---

## 一、项目概述

构建一个**终端原生的 AI 编程助手**（CLI + TUI），具备以下核心能力：

1. **多 Agent 系统**：主 Agent 执行任务，子 Agent 并行处理子任务
2. **持久化记忆**：跨会话记忆，基于 SQLite FTS5 全文搜索
3. **智能上下文管理**：自动 checkpoint，上下文压缩与重建
4. **目标驱动自主循环**：Agent 持续执行直到目标达成
5. **子 Agent 编排**：spawn/send/wait/cancel 生命周期管理
6. **24+ 内置工具**：文件操作、Shell 执行、网络搜索、记忆搜索等
7. **MCP 协议集成**：连接外部工具服务器
8. **插件系统**：可扩展的 hook 架构
9. **工作流引擎**：结构化的工作流执行

**运行时要求**：
- 需要能执行 Shell 命令的运行时
- 需要 SQLite 支持（带 FTS5 扩展）
- 需要 LLM API 调用能力（OpenAI 兼容格式）
- 需要终端 UI 渲染能力

---

## 二、架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────┐
│                    表现层 (CLI/TUI)                   │
│  Terminal UI · 命令行参数解析 · 交互式输入             │
├─────────────────────────────────────────────────────┤
│                    API 层 (HTTP Server)               │
│  REST API · WebSocket · OpenAPI Spec                 │
├─────────────────────────────────────────────────────┤
│                    业务层 (Core)                      │
│  Agent · Session · Tool · Memory · Task · Actor      │
├─────────────────────────────────────────────────────┤
│                    基础设施层                         │
│  Storage(SQLite) · Provider(LLM) · MCP · Plugin      │
│  Config · Auth · Git · Shell · Bus(事件总线)          │
└─────────────────────────────────────────────────────┘
```

### 2.2 核心设计模式

#### Effect 模式（函数式服务）
所有核心服务使用 Effect 模式：
- 服务定义为接口 + 实现层（Layer）
- 依赖通过依赖注入传递
- 错误通过类型系统传播
- 资源通过 acquireUseRelease 管理生命周期

#### Event Sourcing
- 关键状态变更记录为事件
- 事件存储在 SQLite event 表
- 支持状态重放和同步

#### Actor 模型
- 每个 Agent 运行在独立的 Actor 中
- Actor 之间通过 Inbox 消息通信
- 支持父子 Actor 层级关系

---

## 三、数据模型

### 3.1 SQLite 表结构

#### 核心业务表

```sql
-- 项目表
CREATE TABLE project (
  id TEXT PRIMARY KEY,
  worktree TEXT,
  vcs TEXT,
  name TEXT,
  icon_url TEXT,
  icon_color TEXT,
  sandboards TEXT,  -- JSON
  commands TEXT,    -- JSON
  time_initialized INTEGER
);

-- 会话表
CREATE TABLE session (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES project(id),
  workspace_id TEXT,
  parent_id TEXT,
  context_from TEXT,
  slug TEXT,
  directory TEXT,
  title TEXT,
  version INTEGER,
  share_url TEXT,
  summary_additions INTEGER,
  summary_deletions INTEGER,
  summary_files INTEGER,
  summary_diffs INTEGER,
  revert TEXT,
  permission TEXT,
  time_compacting INTEGER,
  time_archived INTEGER,
  last_checkpoint_message_id TEXT,
  time_created INTEGER,
  time_updated INTEGER
);

-- 消息表
CREATE TABLE message (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES session(id),
  agent_id TEXT,
  data TEXT,  -- JSON: role, content, metadata
  time_created INTEGER,
  time_updated INTEGER
);

-- 消息片段表（工具调用、文本等）
CREATE TABLE part (
  id TEXT PRIMARY KEY,
  message_id TEXT REFERENCES message(id),
  session_id TEXT,
  data TEXT,  -- JSON: type, content, toolCallId, etc.
  time_created INTEGER,
  time_updated INTEGER
);
```

#### Task 系统表

```sql
-- 任务表（树形结构）
CREATE TABLE task (
  session_id TEXT,
  id TEXT,
  parent_task_id TEXT,
  status TEXT,  -- open, in_progress, blocked, done, abandoned
  summary TEXT,
  owner TEXT,
  created_at INTEGER,
  last_event_at INTEGER,
  ended_at INTEGER,
  cleanup_after INTEGER,
  PRIMARY KEY (session_id, id)
);

-- 任务事件表
CREATE TABLE task_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  task_id TEXT,
  at INTEGER,
  kind TEXT,
  summary TEXT,
  FOREIGN KEY (session_id, task_id) REFERENCES task(session_id, id)
);
```

#### Actor 系统表

```sql
-- Actor 注册表
CREATE TABLE actor_registry (
  session_id TEXT,
  actor_id TEXT,
  mode TEXT,           -- peer, subagent, main
  parent_actor_id TEXT,
  status TEXT,         -- pending, running, idle
  last_outcome TEXT,   -- success, failure, cancelled
  lifecycle TEXT,      -- ephemeral, persistent
  agent TEXT,
  description TEXT,
  context_mode TEXT,   -- none, state, full
  context_watermark INTEGER,
  background INTEGER,  -- boolean
  tools TEXT,          -- JSON array
  last_turn_time INTEGER,
  turn_count INTEGER,
  last_error TEXT,
  PRIMARY KEY (session_id, actor_id)
);
```

#### 记忆 FTS 表

```sql
-- 记忆全文搜索表
CREATE VIRTUAL TABLE memory_fts USING fts5(
  path,
  scope,        -- global, projects, sessions, cc
  scope_id,
  type,         -- pinned, snapshot, learning, progress, free
  body,
  fingerprint,
  last_indexed_at
);
```

#### 历史 FTS 表

```sql
-- 历史全文搜索表
CREATE VIRTUAL TABLE history_fts USING fts5(
  part_id,
  session_id,
  message_id,
  project_id,
  kind,
  tool_name,
  body,
  time_created
);
```

#### 事件溯源表

```sql
CREATE TABLE event_sequence (
  aggregate_id TEXT PRIMARY KEY,
  seq INTEGER
);

CREATE TABLE event (
  id TEXT PRIMARY KEY,
  aggregate_id TEXT REFERENCES event_sequence(aggregate_id),
  seq INTEGER,
  type TEXT,
  data TEXT  -- JSON
);
```

#### 其他表

```sql
-- Inbox 消息表
CREATE TABLE inbox (
  id TEXT PRIMARY KEY,
  receiver_session_id TEXT,
  receiver_actor_id TEXT,
  sender_session_id TEXT,
  sender_actor_id TEXT,
  type TEXT,
  content TEXT,  -- JSON
  created_at INTEGER
);

-- Workflow 运行表
CREATE TABLE workflow_run (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  name TEXT,
  status TEXT,
  running INTEGER,
  succeeded INTEGER,
  failed INTEGER,
  current_phase TEXT,
  parent_actor_id TEXT,
  args TEXT,  -- JSON
  script_sha TEXT,
  agent_timeout_ms INTEGER,
  error TEXT
);

-- 账户表
CREATE TABLE account (
  id TEXT PRIMARY KEY,
  email TEXT,
  url TEXT,
  access_token TEXT,
  refresh_token TEXT,
  token_expiry INTEGER
);

-- 权限表
CREATE TABLE permission (
  project_id TEXT PRIMARY KEY,
  data TEXT  -- JSON
);
```

### 3.2 目录结构

```
data/
├── memory/
│   ├── global/
│   │   └── MEMORY.md
│   ├── projects/
│   │   └── <project-id>/
│   │       └── MEMORY.md
│   └── sessions/
│       └── <session-id>/
│           ├── checkpoint.md
│           ├── notes.md
│           └── tasks/
│               └── <task-id>/
│                   └── progress.md
└── mimocode.db
```

---

## 四、模块详细设计

### 4.1 Agent 系统

#### Agent 定义

```typescript
interface AgentInfo {
  name: string;
  description: string;
  mode: "primary" | "subagent" | "all";
  permission: PermissionRuleset;
  model?: string;          // 覆盖默认模型
  prompt?: string;         // 系统提示词
  toolAllowlist?: string[]; // 允许的工具列表
  temperature?: number;
  color?: string;
  hidden?: boolean;        // 是否在 UI 中隐藏
}
```

#### 内置 Agent

| Agent | 类型 | 职责 |
|-------|------|------|
| **build** | primary | 主执行 Agent，完整工具访问权限 |
| **plan** | primary | 只读分析 Agent，用于规划 |
| **compose** | primary | 编排 Agent，协调工作流 |
| **explore** | subagent (hidden) | 快速代码探索 |
| **title** | subagent (hidden) | 生成会话标题 |
| **summary** | subagent (hidden) | 生成会话摘要 |
| **compaction** | subagent (hidden) | 上下文压缩 |
| **checkpoint-writer** | subagent (hidden) | 写入 checkpoint 文件 |
| **dream** | subagent (hidden) | 记忆整合（每 7 天） |
| **distill** | subagent (hidden) | 工作流提取（每 30 天） |

#### Agent 权限

默认权限规则：
- 允许大多数工具
- 禁止读取 `.env` 文件
- 外部目录操作需要确认
- 用户可通过配置覆盖

---

### 4.2 Tool 系统

#### Tool 定义模式

```typescript
// 每个 Tool 定义为：
interface ToolInfo {
  id: string;
  description: string;
  parameters: ZodSchema;        // Zod 参数校验
  execute: (args, context) => Promise<ExecuteResult>;
  shell?: ShellMode;            // 可选 shell 风格调用
}

interface ExecuteResult {
  title: string;
  output: string;
  metadata?: Record<string, any>;
  annotations?: ToolAnnotation[];
}

interface ToolContext {
  sessionId: string;
  messageId: string;
  agentId: string;
  abortSignal: AbortSignal;
  askPermission: (permission) => Promise<boolean>;
  publishMetadata: (key, value) => void;
}
```

#### 内置工具清单（24 个）

**文件操作（8 个）**：
1. `read` — 读取文件/目录，支持行偏移、图片、PDF
2. `write` — 写入/创建文件，生成 diff
3. `edit` — 精确字符串替换，支持 replaceAll
4. `multiedit` — 单文件多次编辑
5. `glob` — 文件模式匹配（基于 ripgrep）
6. `grep` — 正则内容搜索（基于 ripgrep）
7. `apply_patch` — 应用 unified-diff 补丁
8. `notebook-edit` — 编辑 Jupyter notebook

**执行类（2 个）**：
9. `bash` — 执行 shell 命令，支持超时、交互模式
10. `change_directory` — 切换工作目录

**网络类（3 个）**：
11. `webfetch` — 获取 URL 内容，转换为 markdown/text/HTML
12. `websearch` — 网页搜索（Exa API）
13. `codesearch` — API/SDK 文档搜索

**智能体编排（4 个）**：
14. `actor` — spawn/send/wait/cancel 子 Agent
15. `task` — 任务生命周期管理
16. `workflow` — 运行内置/内联工作流
17. `skill` — 加载专业技能

**记忆与历史（2 个）**：
18. `memory` — 搜索持久化记忆（BM25）
19. `history` — 搜索历史对话

**模式控制（3 个）**：
20. `plan_enter` — 进入规划模式
21. `plan_exit` — 退出规划模式
22. `question` — 向用户提问

**其他（2 个）**：
23. `lsp` — LSP 交互（实验性）
24. `invalid` — 未知工具错误处理

---

### 4.3 自主循环（Autonomous Loop）

#### 核心循环逻辑

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  while (true) {                                     │
│    1. drain inbox（接收子 Agent 消息）               │
│    2. 加载消息历史                                   │
│    3. classifyAssistantStep（分类上一步）            │
│       - continue: 有待处理工具，继续                 │
│       - final: 无待处理操作，准备停止                │
│       - failed/filtered: 错误停止                   │
│       - think-only/invalid: 重试                    │
│    4. 检查 taskGate（未完成任务？继续）              │
│    5. 检查 goalGate（目标达成？由独立 Judge 判断）   │
│    6. 调用 LLM 获取响应                             │
│    7. 处理工具调用                                   │
│    8. break 或 continue                             │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

#### Goal 机制

```typescript
interface Goal {
  condition: string;      // 目标描述
  reactCount: number;     // 已重试次数
}

interface Verdict {
  ok: boolean;            // 是否达成
  impossible?: boolean;   // 是否不可能
  reason?: string;        // 判定理由
}

// Judge 模型独立于执行 Agent，防止乐观偏差
function evaluate(transcript, goal): Promise<Verdict>;
```

#### TaskGate 逻辑

```
如果存在未完成的 tasks:
  → 注入 nudge 消息（提醒 Agent 继续）
  → 返回 true（继续循环）
否则:
  → 返回 false（允许停止）
```

---

### 4.4 记忆系统

#### 存储结构

```
<data>/memory/
├── global/              # 全局记忆（跨项目）
├── projects/<pid>/      # 项目记忆
│   └── MEMORY.md
└── sessions/<sid>/      # 会话记忆
    ├── checkpoint.md    # 会话检查点（11 个 section）
    ├── notes.md         # 会话笔记
    └── tasks/
        └── <task-id>/
            └── progress.md  # 任务进度
```

#### checkpoint.md 模板（11 个 section）

1. Active Intent — 当前意图
2. Task Tree — 任务树
3. Directives — 指令
4. Current Work — 当前工作
5. Files Touched — 已修改文件
6. Learnings — 学到的知识
7. Errors — 遇到的错误
8. Live Resources — 活跃资源
9. Design Decisions — 设计决策
10. Open Notes — 开放笔记
11. Checkpoint Metadata — 元数据

#### 搜索机制

```
用户查询 → 分词 → OR 连接 → FTS5 搜索 → BM25 排名 → 过滤低分结果
```

- 使用 BM25 算法排序
- 相对分数阈值：低于最高分 15% 的结果被过滤
- 支持按 scope/type 过滤

#### 增量更新

```
1. 扫描 .md 文件
2. 计算 fingerprint: "${size}-${mtimeMs}"
3. 与数据库对比
4. 匹配 → 跳过
5. 不匹配 → 重新索引
6. 删除已不存在的文件
```

---

### 4.5 子 Agent 编排

#### Spawn 流程

```
Allocate ID → Register in DB → Fork Fiber → Run Agent Loop
```

#### 两种 Spawn 模式

| 模式 | 说明 | 上下文 |
|------|------|--------|
| peer | 独立子会话 | 隔离环境 |
| subagent | 共享父会话 | 共享上下文 |

#### 生命周期

```
pending → running → idle
                  ↘ success/failure/cancelled
```

#### Actor Registry

- 基于 SQLite 的持久化注册表
- 孤儿恢复：启动时标记过期 actors 为 failed
- 卡死检测：每 60 秒扫描
- 递归取消：通过 parent_actor_id 递归取消

#### Inbox 消息

```typescript
interface InboxMessage {
  id: string;
  receiver_session_id: string;
  receiver_actor_id: string;
  sender_session_id: string;
  sender_actor_id: string;
  type: string;
  content: any;
  created_at: number;
}
```

---

### 4.6 Checkpoint 系统

#### 写入流程

```
1. 计算 token 预算边界
2. spawn checkpoint-writer 子 Agent
3. 读取之前的 checkpoint/memory
4. 写入更新后的文件：
   - checkpoint.md（会话）
   - MEMORY.md（项目）
   - notes.md（笔记）
   - tasks/<id>/progress.md（任务进度）
```

#### 重建流程

```
1. 读取所有 checkpoint 文件
2. 按 token 预算裁剪
3. 注入到 LLM 上下文（<system-reminder>）
4. 包含：累积知识、快照、全局记忆、任务进度、笔记
```

---

### 4.7 Compose 工作流

#### 工作流管线

```
brainstorm → plan → execute → review → verify → report → merge
```

#### Compose 技能（15 个）

| 阶段 | 技能 | 职责 |
|------|------|------|
| 规划 | compose:brainstorm | 探索意图，提出方案 |
| 规划 | compose:plan | 编写实现计划 |
| 规划 | compose:ask | 路由用户决策 |
| 执行 | compose:execute | 执行实现计划 |
| 执行 | compose:subagent | 子 Agent 驱动开发 |
| 执行 | compose:parallel | 并行调度子 Agent |
| 执行 | compose:tdd | 测试驱动开发 |
| 执行 | compose:worktree | 隔离工作区 |
| 质量 | compose:debug | 四阶段调试 |
| 质量 | compose:review | 代码审查 |
| 质量 | compose:verify | 证据验证 |
| 质量 | compose:feedback | 审查反馈处理 |
| 收尾 | compose:report | 最终报告 |
| 收尾 | compose:merge | 分支合并 |
| 元 | compose:new-skill | 创建新技能 |

---

### 4.8 MCP 集成

#### 传输类型

| 类型 | 说明 |
|------|------|
| Stdio | 本地进程通信 |
| StreamableHTTP | 远程 HTTP 流 |
| SSE | 远程 Server-Sent Events |

#### 工具发现

```
连接 MCP Server → client.listTools() → 转换为内部 Tool 格式
```

#### 状态管理

```typescript
type MCPStatus = "connected" | "disabled" | "pending" | "failed" | "needs_auth";
```

---

### 4.9 插件系统

#### Hook 架构

```typescript
interface PluginHooks {
  // Actor 生命周期
  "actor.preStop"?: (context) => Promise<void>;
  "actor.postStop"?: (context) => Promise<void>;
  
  // 事件处理
  "event"?: (event) => Promise<void>;
  
  // 配置
  "config"?: (config) => Config;
  
  // 输入/输出触发
  "input"?: (input) => Input;
  "output"?: (output) => Output;
}
```

#### 插件来源

| 来源 | 说明 |
|------|------|
| 内置插件 | auth, checkpoint, progress |
| npm 包 | 通过 PluginLoader 动态加载 |
| 文件 hook | hook/ 目录下的脚本 |
| 配置指定 | skills.paths / skills.urls |

#### 容错机制

- 断路器模式：失败 3 次后暂停 5 秒
- 超时保护：每个 hook 5 秒超时

---

### 4.10 配置系统

#### 配置合并顺序（从低到高）

1. well-known remote
2. 全局 `~/.config/mimocode/`
3. 自定义 `MIMOCODE_CONFIG` 环境变量
4. 项目本地 `mimocode.json`
5. `.mimocode/` 目录
6. `MIMOCODE_CONFIG_CONTENT` 环境变量
7. managed (MDM)
8. Claude Code MCP 兼容

#### 配置文件格式

```json
{
  "provider": {
    "default": "openai",
    "openai": {
      "apiKey": "sk-...",
      "model": "gpt-4"
    }
  },
  "agent": {
    "build": {
      "model": "gpt-4",
      "temperature": 0.7
    }
  },
  "mcp": {
    "servers": {
      "my-server": {
        "command": "node",
        "args": ["server.js"]
      }
    }
  },
  "plugin": {
    "paths": ["./plugins"]
  }
}
```

---

### 4.11 Server/API 层

#### 路由模块

| 模块 | 说明 |
|------|------|
| InstanceRoutes | 工作区实例路由 |
| ControlPlaneRoutes | 控制平面路由 |
| UIRoutes | UI 相关路由 |
| GlobalRoutes | 全局路由 |

#### 中间件

- Auth 认证
- CORS 跨域
- Compression 压缩
- Logging 日志
- Fencing 限流
- Error Handling 错误处理

#### 两种模式

```
单工作区模式：直接挂载 InstanceRoutes
多工作区模式：ControlPlane + Workspace Router + InstanceRoutes
```

---

## 五、关键算法

### 5.1 BM25 排名

```
BM25(D, Q) = Σ IDF(qi) × (f(qi, D) × (k1 + 1)) / (f(qi, D) + k1 × (1 - b + b × |D|/avgdl))

IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5))
```

- k1 = 1.2（词频饱和参数）
- b = 0.75（文档长度归一化）
- N = 文档总数
- n(qi) = 包含词 qi 的文档数

### 5.2 上下文压缩

```
1. 计算当前 token 使用量
2. 如果超过阈值：
   a. spawn compaction Agent
   b. 读取完整历史
   c. 生成压缩摘要
   d. 保留最近 N 条消息
   e. 注入摘要作为上下文
3. 继续执行
```

### 5.3 增量 FTS 索引

```
For each .md file:
  currentFingerprint = "${size}-${mtimeMs}"
  storedFingerprint = DB.get(file.path)
  
  if currentFingerprint == storedFingerprint:
    skip  // 未变化
  else:
    content = readFile(file.path)
    DB.upsert(file.path, content, currentFingerprint)

// 清理已删除文件
For each DB record:
  if !fileExists(record.path):
    DB.delete(record.path)
```

---

## 六、UI 设计

### 6.1 TUI 布局

```
┌─────────────────────────────────────────────────────┐
│  MiMo Code v1.0                    [build] [main]   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─ Session: Fix login bug ──────────────────────┐  │
│  │                                               │  │
│  │  > Read src/auth.ts                           │  │
│  │                                               │  │
│  │  The file shows a password comparison issue... │  │
│  │                                               │  │
│  │  [Edit] Fixed comparison to use timing-safe    │  │
│  │                                               │  │
│  │  > Run tests                                  │  │
│  │                                               │  │
│  │  ✓ 12 tests passed                            │  │
│  │                                               │  │
│  │  Task T1: Fix login bug [done]                │  │
│  │                                               │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Tasks ───────────────────────────────────────┐  │
│  │ T1: Fix login bug [done] ✓                    │  │
│  │ T2: Add unit tests [in_progress]              │  │
│  │   T2.1: Test password validation [...]        │  │
│  │   T2.2: Test session management [...]         │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌─ Input ───────────────────────────────────────┐  │
│  │ > _                                            │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 6.2 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+C | 中断当前操作 |
| Ctrl+Z | 挂起（可恢复） |
| Ctrl+L | 清屏 |
| Ctrl+R | 搜索历史 |
| Tab | 自动补全 |
| Up/Down | 历史导航 |

---

## 七、实现指南

### 7.1 推荐技术栈

| 组件 | 推荐选项 |
|------|----------|
| 语言 | TypeScript / Go / Rust / Python |
| 运行时 | Bun / Node.js / Deno |
| 数据库 | SQLite（带 FTS5） |
| ORM | Drizzle / Prisma / SQLAlchemy |
| HTTP 框架 | Hono / Express / Gin / FastAPI |
| TUI 框架 | Ink (React) / Bubbletea / Ratatui / Textual |
| LLM SDK | Vercel AI SDK / LangChain / 原生 HTTP |
| 测试 | Vitest / Go testing / pytest |

### 7.2 实现顺序

**Phase 1: 基础框架（2-3 周）**
1. 项目结构搭建
2. SQLite 存储层
3. 配置系统
4. 基础 Tool 定义
5. LLM 调用封装

**Phase 2: 核心循环（2-3 周）**
1. Agent 系统
2. 自主循环（runLoop）
3. 消息管理
4. 基础 Tool 实现（bash, read, write, edit）

**Phase 3: 记忆系统（1-2 周）**
1. FTS5 索引
2. Checkpoint 读写
3. 记忆搜索

**Phase 4: 子 Agent（2-3 周）**
1. Actor 系统
2. Spawn/Wait/Cancel
3. Inbox 消息
4. Task 系统

**Phase 5: 高级功能（2-3 周）**
1. Goal 机制
2. Compose 工作流
3. MCP 集成
4. 插件系统

**Phase 6: UI 和优化（2 周）**
1. TUI 界面
2. API 层
3. 性能优化
4. 测试覆盖

### 7.3 关键注意事项

1. **并发安全**：SQLite 写入需要 WAL 模式和适当的锁
2. **资源管理**：LLM 调用需要超时和重试机制
3. **错误恢复**：子 Agent 失败不应影响父 Agent
4. **上下文限制**：注意 LLM 的 token 限制
5. **安全性**：Shell 命令需要沙箱或权限控制

---

## 八、测试策略

### 单元测试

- Tool 参数校验
- 分类器逻辑
- FTS 查询构建
- BM25 排名

### 集成测试

- 完整的 Agent 循环
- 子 Agent spawn 和通信
- Checkpoint 读写
- MCP 连接

### 端到端测试

- 用户交互流程
- 长对话记忆保持
- 并发子 Agent

---

## 九、部署要求

### 最低配置

- 2 核 CPU
- 4GB RAM
- 10GB 磁盘
- 网络连接（LLM API 调用）

### 依赖服务

- LLM API（OpenAI 兼容）
- 可选：MCP Server
- 可选：搜索引擎 API

---

## 十、扩展点

1. **自定义 Agent**：通过配置添加新 Agent
2. **自定义 Tool**：实现 Tool 接口
3. **自定义 Skill**：编写 SKILL.md 文件
4. **自定义 Plugin**：实现 Hook 接口
5. **自定义 Provider**：适配新的 LLM API

---

> **使用说明**：将此文档提供给 AI 编程工具，指定目标语言和运行时，AI 将基于此规范从零实现完整的 AI 编程助手系统。
