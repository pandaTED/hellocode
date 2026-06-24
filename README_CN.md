# HelloCode

基于 Python 的终端原生 AI 编程助手。轻量、开源，类似 OpenCode / MiMoCode 的替代方案。

## 功能特性

- **多 Agent 系统** — 主 Agent 执行任务，子 Agent 并行处理子任务
- **持久化记忆** — 跨会话记忆，基于 SQLite FTS5 全文搜索
- **自主循环** — Agent 持续执行直到目标达成
- **16+ 内置工具** — 文件操作、Shell 执行、网页抓取、记忆搜索等
- **MCP 协议集成** — 连接外部工具服务器
- **插件系统** — 可扩展的 Hook 架构
- **任务管理** — 树形任务生命周期（open → in_progress → done）
- **Rich TUI** — 美观的终端界面，支持 Markdown 渲染

## 快速开始

### 安装

```bash
git clone https://github.com/pandaTED/hellocode.git
cd hellocode
pip install -e .
```

### 配置

在项目目录创建 `hellocode.json`：

```json
{
  "provider": {
    "default": "openai",
    "openai": {
      "apiKey": "your-api-key",
      "model": "gpt-4",
      "base_url": "https://api.openai.com/v1"
    }
  },
  "agent": {
    "build": {
      "max_tokens": 32768
    }
  }
}
```

或使用环境变量：

```bash
export OPENAI_API_KEY=your-api-key
```

### 运行

```bash
# 交互模式
python -m hellocode

# 单次提问模式
python -m hellocode "修复 auth.py 中的 bug"

# 指定模型
python -m hellocode -m gpt-4 "重构这段代码"
```

## CLI 参数

```
用法: hellocode [-h] [--model MODEL] [--agent AGENT] [--workdir WORKDIR]
                [--data-dir DATA_DIR] [--session-id SESSION_ID] [--version]
                [prompt ...]

位置参数:
  prompt                单次模式的提示词

选项:
  -h, --help            显示帮助信息
  -m, --model MODEL     覆盖模型名称
  -a, --agent AGENT     使用的 Agent（默认: build）
  -d, --workdir WORKDIR 工作目录
  --data-dir DATA_DIR   数据存储目录
  --session-id SESSION_ID  恢复之前的会话
  -v, --version         显示版本号
```

## 交互命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示可用命令 |
| `/tasks` | 列出当前任务 |
| `/sessions` | 列出历史会话 |
| `/memory <查询>` | 搜索持久化记忆 |
| `/new` | 开始新会话 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

## 架构

```
┌─────────────────────────────────────────┐
│          终端界面 (Rich)                 │
├─────────────────────────────────────────┤
│           Agent 自主循环                 │
│  Agent · Task · Actor · Memory          │
├─────────────────────────────────────────┤
│            基础设施层                    │
│  Storage(SQLite) · Provider(LLM)        │
│  MCP · Plugin · Config · Shell          │
└─────────────────────────────────────────┘
```

## 内置工具

| 工具 | 说明 |
|------|------|
| `read` | 读取文件/目录内容 |
| `write` | 创建或覆写文件 |
| `edit` | 精确字符串替换 |
| `glob` | 按模式查找文件 |
| `grep` | 正则搜索文件内容 |
| `bash` | 执行 Shell 命令 |
| `change_directory` | 切换工作目录 |
| `webfetch` | 抓取网页内容 |
| `task` | 任务生命周期管理 |
| `actor` | 生成和管理子 Agent |
| `memory` | 搜索持久化记忆 |
| `workflow` | 执行工作流脚本 |
| `skill` | 加载专业技能 |
| `notebook-edit` | 编辑 Jupyter Notebook |
| `apply_patch` | 应用 unified diff 补丁 |
| `question` | 向用户提问 |

## 项目结构

```
hellocode/
├── __init__.py         # 包入口
├── __main__.py         # CLI 入口
├── agent.py            # Agent 自主循环
├── agents.py           # 内置 Agent 定义
├── config.py           # 分层配置系统
├── mcp.py              # MCP 协议集成
├── memory.py           # 记忆系统（FTS5）
├── plugin.py           # 插件 Hook 架构
├── provider.py         # OpenAI 兼容 LLM 客户端
├── storage.py          # SQLite 存储层
├── tui.py              # 终端 UI
├── workflow.py         # 工作流引擎
└── tools/
    ├── __init__.py     # 工具注册
    ├── base.py         # Tool 基类
    └── builtin.py      # 16 个内置工具
```

## 配置来源

配置按优先级从低到高合并：

1. 全局: `~/.config/hellocode/hellocode.json`
2. 环境变量: `MIMOCODE_CONFIG`（JSON 字符串）
3. 项目目录: `./hellocode.json`
4. 项目目录: `./.hellocode/*.json`
5. 环境变量: `OPENAI_API_KEY`

## 许可证

MIT
