# HelloCode

Terminal-native AI coding assistant written in Python. A lightweight, open-source alternative to tools like OpenCode and MiMoCode.

## Features

- **Multi-Agent System** — Main agent executes tasks, sub-agents handle parallel subtasks
- **Persistent Memory** — Cross-session memory with SQLite FTS5 full-text search
- **Autonomous Loop** — Agent continues executing until goal is achieved
- **16+ Built-in Tools** — File operations, shell execution, web fetching, memory search
- **MCP Integration** — Connect external tool servers via Model Context Protocol
- **Plugin System** — Extensible hook architecture
- **Task Management** — Tree-structured task lifecycle (open → in_progress → done)
- **Rich TUI** — Beautiful terminal interface with markdown rendering

## Quick Start

### Install

```bash
git clone https://github.com/pandaTED/hellocode.git
cd hellocode
pip install -e .
```

### Configure

Create `hellocode.json` in your project directory:

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

Or use environment variable:

```bash
export OPENAI_API_KEY=your-api-key
```

### Run

```bash
# Interactive mode
python -m hellocode

# Single prompt mode
python -m hellocode "fix the bug in auth.py"

# Specify model
python -m hellocode -m gpt-4 "refactor this code"
```

## CLI Options

```
usage: hellocode [-h] [--model MODEL] [--agent AGENT] [--workdir WORKDIR]
                 [--data-dir DATA_DIR] [--session-id SESSION_ID] [--version]
                 [prompt ...]

positional arguments:
  prompt                Prompt for single-shot mode

options:
  -h, --help            Show this help message and exit
  -m, --model MODEL     Override model name
  -a, --agent AGENT     Agent to use (default: build)
  -d, --workdir WORKDIR Working directory
  --data-dir DATA_DIR   Data directory for storage/memory
  --session-id SESSION_ID  Resume a previous session
  -v, --version         Show version number and exit
```

## Interactive Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/tasks` | List current tasks |
| `/sessions` | List past sessions |
| `/memory <query>` | Search persistent memory |
| `/new` | Start a new session |
| `/clear` | Clear screen |
| `/exit` | Quit |

## Architecture

```
┌─────────────────────────────────────────┐
│          Terminal UI (Rich)             │
├─────────────────────────────────────────┤
│           Agent Loop (Core)             │
│  Agent · Task · Actor · Memory          │
├─────────────────────────────────────────┤
│          Infrastructure Layer           │
│  Storage(SQLite) · Provider(LLM)        │
│  MCP · Plugin · Config · Shell          │
└─────────────────────────────────────────┘
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read` | Read file/directory content |
| `write` | Create or overwrite files |
| `edit` | Precise string replacement |
| `glob` | Find files by pattern |
| `grep` | Search file contents with regex |
| `bash` | Execute shell commands |
| `change_directory` | Switch working directory |
| `webfetch` | Fetch URL content |
| `task` | Task lifecycle management |
| `actor` | Spawn and manage sub-agents |
| `memory` | Search persistent memory |
| `workflow` | Execute workflow scripts |
| `skill` | Load specialized skills |
| `notebook-edit` | Edit Jupyter notebooks |
| `apply_patch` | Apply unified diff patches |
| `question` | Ask user questions |

## Project Structure

```
hellocode/
├── __init__.py         # Package entry
├── __main__.py         # CLI entry point
├── agent.py            # Agent autonomous loop
├── agents.py           # Built-in agent definitions
├── config.py           # Layered configuration system
├── mcp.py              # MCP protocol integration
├── memory.py           # Memory system with FTS5
├── plugin.py           # Plugin hook architecture
├── provider.py         # OpenAI-compatible LLM client
├── storage.py          # SQLite storage layer
├── tui.py              # Terminal UI
├── workflow.py         # Workflow engine
└── tools/
    ├── __init__.py     # Tool registry
    ├── base.py         # Tool base class
    └── builtin.py      # 16 built-in tools
```

## Configuration Sources

Configuration is merged from (low to high priority):

1. Global: `~/.config/hellocode/hellocode.json`
2. Environment: `MIMOCODE_CONFIG` (JSON string)
3. Project: `./hellocode.json`
4. Project: `./.hellocode/*.json`
5. Environment: `OPENAI_API_KEY`

## License

MIT
