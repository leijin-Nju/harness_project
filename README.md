# Coding Agent Harness

Coding Agent Harness 是一个自有核心循环的 Python coding agent harness。它以 CLI
为主要入口，通过结构化动作、工作区路径围栏、确定性命令风险分级、HITL 审批和
客观反馈回灌，在受控范围内执行软件开发任务。最小 WebUI 仅负责状态展示和审批。

项目要求 Python 3.11+。默认记忆和审批状态使用工作区内的本地 JSON 文件，不使用 SQLite；
MySQL 仅保留为未来 adapter，不是 MVP 依赖。核心测试使用 mock LLM，
无需网络或真实 API key。Docker 是首选分发路径。

## Installation

本地开发安装：

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

激活虚拟环境后可使用 `harness` 命令。验证 Python 版本：

```bash
python --version
```

## Usage

无需 API key 的本地演示与完整机制演示：

```bash
harness demo --workspace .
python scripts/mock_demo.py
```

使用 mock 动作脚本运行任务：

```bash
harness run "finish the task" --workspace . --mock-script script.json
```

审批、记忆与凭据命令：

```bash
harness approvals list --workspace .
harness approvals approve REQUEST_ID --workspace .
harness approvals reject REQUEST_ID --workspace .
harness memory list --workspace .
harness credentials status
harness credentials set
harness credentials clear
```

本地启动最小 WebUI/API：

```bash
uvicorn harness.web:app --host 127.0.0.1 --port 8000
```

WebUI 位于 `http://127.0.0.1:8000/`。它读取与 CLI 相同的 `.harness/`
状态，但不会执行 shell 命令或承担 agent 核心循环。

## Docker Distribution

Docker 是项目的首选分发方式。构建镜像、运行默认 CLI demo、启动 WebUI：

```bash
docker build -t coding-agent-harness:local .
docker run --rm -v "$PWD:/workspace" coding-agent-harness:local
docker run --rm -p 8000:8000 -v "$PWD:/workspace" coding-agent-harness:local uvicorn harness.web:app --host 0.0.0.0 --port 8000
```

Windows PowerShell 可将 `$PWD` 替换为 `${PWD}`，或直接使用工作区绝对路径。
容器 WebUI 暴露于 `http://localhost:8000/`。

当前环境未验证 Docker daemon 与 Buildx；上述命令由项目文件和 CI 配置覆盖，实际构建结果
取决于运行机器可用的 Docker 服务。

## API Key Security

mock LLM 测试与 `scripts/mock_demo.py` 不需要 API key。真实 LLM 模式优先通过
隐藏输入写入系统 keyring：

```bash
harness credentials set
harness credentials status
```

也可通过进程环境变量 `OPENAI_API_KEY` 提供凭据。不要将 key 写入源码、提交到
Git、放入 mock 脚本或粘贴到日志。项目不会在状态命令中显示明文；`.env` 文件仍是
本地明文载体，且被路径围栏视为敏感文件，不推荐作为本项目的凭据存储方式。

## Directory Structure

```text
src/harness/               核心循环、治理、工具、反馈、记忆、CLI 与 WebUI
tests/                     离线单元测试与机制测试
scripts/mock_demo.py       确定性三场景演示
examples/mock_project/     演示用微型项目
docs/superpowers/          已确认设计与实施计划来源
.harness/                  运行时 JSON 状态、审批、记忆和日志（不提交）
Dockerfile                 首选容器分发定义
.gitlab-ci.yml             单元测试、lint 与镜像构建流水线
```

## Security Boundaries

- 文件动作必须留在解析后的 workspace 内；敏感凭据文件会被拒绝，`.git/` 写入需审批。
- 命令按 `ALLOW`、`REVIEW`、`DENY` 分级；危险命令拒绝，中风险命令等待人工审批。
- 所有 shell 命令具有有限超时，输出长度受限，凭据在记忆与状态输出中脱敏。
- CLI 是主要执行界面；WebUI 只显示状态并处理审批，不直接调用工具。
- MVP 不提供完整的操作系统或容器级执行沙箱，也不承诺对未知命令实现完备隔离。
- 本地 JSON 适合单用户 MVP，不提供高并发事务保证；MySQL 仅为未来扩展预留。

运行验证：

```bash
pytest -q
ruff check src tests scripts
python scripts/mock_demo.py
```
