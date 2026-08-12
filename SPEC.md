# Coding Agent Harness Design

日期：2026-08-10

## 1. 问题陈述

本项目交付一个面向软件开发场景的 Coding Agent Harness。它的目标不是实现一个聊天机器人，而是实现一个可验证的软件开发自动化内核：读取任务、组织上下文、调用 LLM 或 mock LLM、解析动作、经过治理护栏、执行工具、收集客观反馈，再把结果回灌给下一轮决策，直到完成、失败、达到迭代上限或等待人工审批。

目标用户包括：

- 项目开发者：希望让 agent 在受控工作区内完成小型代码修改、运行测试并自我修正。
- 审批者：希望危险动作在执行前暂停，经过人类确认后再继续。
- 课程评审者：希望在不依赖真实 LLM 和网络的情况下，确定性验证 harness 的核心机制确实由代码实现。

本项目选择 A 类 Coding Agent Harness。主贡献维度是治理护栏、HITL 审批和工作区边界；反馈闭环作为第二条核心机制，用于展示 agent 可以根据 pytest、ruff 和命令退出码等客观信号调整下一步动作。

## 2. 用户故事

### US-01 - CLI 启动任务

优先级：Must

作为 项目开发者，我希望 用 CLI 启动一次 coding agent 任务，以便 让 harness 在受控工作区内完成小型代码修改。

验收标准：
1. 用户可以运行 `harness run "<task>" --workspace <path>` 启动任务。
2. harness 能完成上下文组装、LLM/mock LLM 调用、动作解析、工具执行、反馈回灌和停机判断。
3. mock LLM 模式不需要真实 API key，并可在单元测试中确定性运行完整主循环。

### US-02 - 危险动作治理

优先级：Must

作为 项目开发者，我希望 危险动作不会被 agent 直接执行，以便 避免删除文件、泄露凭据或越权修改工作区。

验收标准：
1. `rm -rf /`、删除数据库、读取 `.env`、写入 workspace 外路径等动作必须被拒绝。
2. `git push`、安装依赖、网络发布、长时间服务进程等动作必须进入人工审批。
3. `pytest`、`ruff`、只读文件读取、workspace 内安全写入等低风险动作可自动执行。
4. 单元测试能证明被拒绝或待审批动作没有被实际执行。

### US-03 - 人工审批

优先级：Must

作为 审批者，我希望 通过 CLI 或 WebUI 查看并处理待审批动作，以便 在人类确认后才允许中风险操作继续。

验收标准：
1. harness 会为中风险动作创建持久化审批请求，状态为 `pending`。
2. 用户可以批准、拒绝或修改后批准审批请求。
3. 主循环遇到待审批动作时进入 `waiting_for_approval`，恢复后继续执行。
4. 单元测试覆盖 `pending -> approved`、`pending -> rejected`、`pending -> expired` 状态转换。

### US-04 - 反馈闭环

优先级：Must

作为 项目开发者，我希望 测试和 lint 失败能被结构化回灌给 agent，以便 agent 根据客观反馈修正下一步动作。

验收标准：
1. `pytest` 失败会提取失败测试名、断言摘要和 traceback 关键片段。
2. `ruff` 失败会提取规则编号、文件、行号和消息。
3. 普通命令失败会记录命令、退出码、stderr 摘要和是否超时。
4. mock 演示能确定性复现“失败 -> 收到反馈 -> 修复 -> 验证通过”。

### US-05 - 确定性机制演示

优先级：Must

作为 课程评审者，我希望 无需真实 LLM 就能运行核心机制演示，以便 验证项目机制不是只靠提示词完成。

验收标准：
1. `make test` 或等价命令能运行 mock LLM 单元测试。
2. 演示覆盖危险动作拦截、反馈闭环自修复、HITL 审批状态机。
3. 演示不依赖网络、不依赖真实 API key、不修改 workspace 外文件。
4. CI 中 `unit-test` job 能执行这些测试。

### US-06 - 项目记忆

优先级：Should

作为 项目开发者，我希望 harness 记住项目约定和历史决策，以便 后续任务能按需获得相关上下文。

验收标准：
1. 默认使用本地 JSON 存储记忆，不使用 SQLite。
2. 记忆至少包含项目约定、用户决策、历史失败摘要三类。
3. 任务开始时按关键词、类型和最近性检索有限条记忆，而不是全量注入。
4. 可预留 MySQL adapter 接口，但 MVP 不要求部署 MySQL。

### US-07 - 安全凭据配置

优先级：Should

作为 新用户，我希望 安全配置 OpenAI-compatible API key，以便 真实 LLM 模式能运行且凭据不泄露。

验收标准：
1. CLI 支持隐藏输入 API key，并优先写入系统 keyring。
2. 支持环境变量作为 key 来源，并在 README 说明 `.env` 明文风险。
3. 查看凭据状态时只显示存在性、来源和更新时间，不回显明文。
4. 日志和错误信息不会打印 API key。

### US-08 - Docker 分发

优先级：Should

作为 部署者，我希望 用 Docker 启动 CLI/WebUI，以便 在新机器上复现项目运行环境。

验收标准：
1. README 提供 `docker build` 和 `docker run` 命令。
2. 容器支持挂载 workspace，并暴露 WebUI 端口。
3. 无真实 API key 时仍可运行 mock demo。
4. CI 能构建 Docker 镜像。

### US-09 - 最小 WebUI

优先级：Could

作为 项目开发者，我希望 通过最小 WebUI 查看任务状态、反馈摘要、审批队列和记忆条目，以便 更直观看到 harness 运行过程。

验收标准：
1. WebUI 至少提供任务状态页、审批列表页、反馈摘要页和记忆列表页。
2. 用户可在 WebUI 批准或拒绝审批请求。
3. WebUI 不承担核心 agent loop；核心机制必须仍可由 CLI 和单元测试验证。

### US-10 - 强隔离容器沙箱

优先级：Won't

作为 高级用户，我希望 所有命令都在强隔离容器沙箱中执行，以便 获得更强的系统级隔离。

验收标准：
1. MVP 不实现完整容器沙箱执行器。
2. SPEC 将其列为未来增强。
3. MVP 通过命令风险分级、路径围栏、超时和 HITL 审批降低风险。

## 3. 领域与机制设计

### 3.1 动作与工具

agent 可产生的动作必须是结构化对象，而不是任意自然语言指令。MVP 支持：

- `read_file`：读取 workspace 内文件。
- `write_file`：写入 workspace 内文件。
- `run_command`：执行受治理检查的 shell 命令。
- `run_checks`：运行默认验证命令，如 `pytest` 和 `ruff`。
- `remember`：写入项目约定、决策或失败摘要。
- `request_done`：报告任务完成，并附带摘要。

所有动作先经过 schema 校验，再经过治理模块检查。工具层只执行已被治理层允许的动作。

### 3.2 客观反馈信号

MVP 使用三类客观反馈信号：

- `pytest`：解析失败测试名、断言摘要、traceback 关键片段。
- `ruff`：解析规则编号、文件、行号和消息。
- 命令退出码：记录命令、退出码、stderr 摘要、stdout 摘要和超时状态。

反馈信号由 `FeedbackCollector` 和具体 parser 生成结构化 observation，并回灌给下一轮 LLM 调用。反馈机制必须能在 mock LLM 下确定性测试，不能依赖“让 LLM 自己检查”的提示词。

### 3.3 危险动作与治理边界

主贡献维度是治理护栏、HITL 审批和工作区边界。MVP 编码实现三个确定性层次。

1. **路径围栏**

   所有读写文件动作必须解析为绝对路径，并验证其位于配置的 workspace root 内。越界路径、符号链接逃逸、写入 `.git` 敏感区域、读取凭据文件等会被拒绝或要求审批。该机制可通过直接构造 action 单元测试验证。

2. **命令风险分级**

   `RiskClassifier` 将命令分为 `allow`、`review`、`deny`：

   - `allow`：`pytest`、`ruff`、`git status`、只读查询等低风险命令。
   - `review`：`git push`、安装依赖、网络发布、长时间服务进程等中风险命令。
   - `deny`：`rm -rf /`、格式化磁盘、删除数据库、越界删除、读取或泄露 key 的命令。

   命令执行器必须设置合理超时，避免进程无期限挂起。所有命令结果都以 stdout、stderr、退出码、超时状态的结构化形式返回。

3. **HITL 审批状态机**

   中风险动作不会直接执行，而是创建 `ApprovalRequest`，状态为 `pending`。用户可通过 CLI 或 WebUI 批准、拒绝或修改后批准。主循环遇到待审批动作时停机为 `waiting_for_approval`，恢复后继续执行。状态转换包括 `pending -> approved`、`pending -> rejected`、`pending -> expired`。

### 3.4 记忆需求

记忆机制不作为主贡献，但必须完整可运行。`harness.memory` 默认使用本地 JSON 存储，例如 workspace 下 `.harness/memory.json`。不使用 SQLite。设计保留 `MemoryStore` 接口，允许未来扩展 `MySQLMemoryStore`，但 MVP 不要求部署 MySQL。

记忆至少包含三类：

- 项目约定：例如“不使用 SQLite，默认本地 JSON，可选 MySQL”。
- 用户决策：例如“治理优先，反馈闭环作为配套”。
- 历史失败摘要：例如最近一次 pytest 或 ruff 失败的原因与修复结果。

任务开始时按关键词、类型和最近性检索有限条记忆，注入上下文；不得每次全量载入。

## 4. 系统架构

系统采用 CLI 为主、最小 WebUI 演示为辅的架构。

- `harness.cli`：主要入口，支持运行任务、查看审批、管理凭据、查看记忆状态。
- `harness.core.loop`：自有 agent 主循环，负责上下文组装、LLM 调用、动作解析、工具分发、反馈回灌和停机判断。
- `harness.llm`：LLM 抽象层，包含 OpenAI-compatible client 和 deterministic mock client。
- `harness.actions`：定义模型可返回的动作格式。
- `harness.tools`：工具注册和执行层，执行文件读写、shell、pytest、ruff。
- `harness.governance`：主贡献模块，包含路径围栏、命令风险分级、审批存储、审批状态机。
- `harness.feedback`：解析测试、ruff 和命令退出码，生成结构化反馈。
- `harness.memory`：本地 JSON 结构化记忆，预留 MySQL adapter。
- `harness.config`：配置 workspace root、允许命令、超时、LLM provider、memory 路径。
- `harness.credentials`：凭据来源、保存、更新、清除和脱敏展示。
- `harness.web`：最小 FastAPI WebUI/API，用于展示任务状态、反馈摘要、审批队列和记忆条目。

核心边界：Superpowers/Codex 只用于开发这个项目，交付物自己的 agent loop、治理、反馈、记忆都由仓库代码实现，并可用 mock LLM 单元测试验证。

## 5. 数据流

1. 用户通过 CLI 提交任务和 workspace。
2. 配置、凭据和记忆模块组装任务上下文。
3. 主循环调用 LLM 或 mock LLM。
4. LLM 返回结构化 action。
5. action parser 校验格式。
6. governance 判断 action 是 `allow`、`review` 还是 `deny`。
7. `allow` action 进入 tool executor。
8. tool executor 返回 stdout、stderr、exit code、文件结果或异常摘要。
9. feedback parser 生成结构化 observation。
10. 主循环把 observation 写入历史，并进入下一轮。
11. 达到完成、失败、等待审批或迭代上限后停机。

## 6. 数据模型

核心数据对象统一使用 Pydantic 定义，确保 action、feedback、approval 等外部契约有明确校验；少量不跨模块传递的内部轻量状态可使用 dataclass。

- `TaskRun`：`id`、`workspace`、`task`、`status`、`iterations`、`created_at`、`updated_at`、`stop_reason`。
- `Action`：`type`、`payload`、`request_id`、`created_at`。
- `RiskDecision`：`level`、`reasons`、`required_approval`、`policy_version`。
- `ToolResult`：`action_id`、`ok`、`stdout`、`stderr`、`exit_code`、`timed_out`、`duration_ms`。
- `Feedback`：`kind`、`summary`、`details`、`source`、`severity`。
- `ApprovalRequest`：`id`、`action`、`risk_decision`、`status`、`created_at`、`resolved_at`、`resolution_note`。
- `MemoryEntry`：`id`、`kind`、`text`、`keywords`、`created_at`、`last_used_at`、`source_task_id`。
- `CredentialStatus`：`provider`、`source`、`exists`、`updated_at`、`masked_preview`。

持久化位置默认在 workspace 下 `.harness/`：

- `.harness/runs/*.json`
- `.harness/approvals.json`
- `.harness/memory.json`
- `.harness/logs/*.jsonl`

持久化文件不得保存明文 API key。

## 7. 功能规约

### 7.1 主循环

输入：任务描述、workspace、配置、可选恢复状态。

行为：

- 读取相关记忆。
- 构造上下文。
- 调用 LLM 或 mock LLM。
- 解析结构化 action。
- 将 action 送入治理层。
- 执行被允许的工具。
- 收集反馈并回灌。
- 根据状态停机。

输出：`TaskRun` 状态、结构化日志、最终摘要。

边界条件与错误处理：

- action JSON 无法解析时，返回 `invalid_action` feedback，允许下一轮修正。
- 达到最大迭代次数时，以 `failed` 或 `max_iterations` 停机。
- 中风险动作创建审批请求后，以 `waiting_for_approval` 停机。

### 7.2 LLM 抽象

输入：上下文消息和可用 action schema。

行为：

- `OpenAICompatibleClient` 只做单次模型调用，不实现 agent runner。
- `MockLLMClient` 按预设脚本返回固定 action 序列。

输出：结构化 action 文本或已解析 action。

错误处理：

- key 缺失时真实 LLM 模式给出设置指引。
- mock 模式不要求 key。
- 调用失败时返回可诊断错误，不泄露凭据。

### 7.3 工具执行

输入：已通过治理的 action。

行为：

- 文件工具只操作 workspace 内路径。
- shell 工具必须设置超时。
- `run_checks` 默认运行 `pytest` 和 `ruff`。

输出：结构化 `ToolResult`。

错误处理：

- 命令超时返回 `timed_out=true`。
- 输出过长时截断并保留关键摘要。
- 命令不存在时返回 command failure feedback。

### 7.4 治理模块

输入：action、workspace、配置策略。

行为：

- 路径围栏判断路径是否在 workspace 内。
- 风险分类器判断命令和动作级别。
- 审批状态机持久化审批请求。

输出：`RiskDecision` 或 `ApprovalRequest`。

错误处理：

- 高风险动作直接拒绝。
- 中风险动作创建审批请求。
- 审批存储损坏时返回可恢复错误并保留备份。

### 7.5 反馈模块

输入：命令结果或工具结果。

行为：

- 解析 pytest、ruff 和通用命令失败。
- 提取最小必要摘要。
- 生成下一轮 observation。

输出：结构化 `Feedback`。

错误处理：

- 无法识别的输出降级为 generic command feedback。
- 输出过长时截断。

### 7.6 记忆模块

输入：记忆条目或任务上下文查询。

行为：

- 写入本地 JSON。
- 按关键词、类型和最近性检索。
- 限制返回条数。

输出：`MemoryEntry` 列表。

错误处理：

- JSON 损坏时备份原文件并报告恢复建议。
- 不保存明文 API key。
- MySQL 作为未来可选 adapter，不是 MVP 依赖。

### 7.7 凭据与配置

输入：用户输入、环境变量、配置文件。

行为：

- 优先从系统 keyring 读取 API key。
- 支持环境变量作为兼容来源。
- CLI 支持设置、查看状态、更新、清除。

输出：脱敏凭据状态或可用 provider 配置。

错误处理：

- 不回显明文 key。
- 日志不记录 key。
- `.env` 风险写入 README 和 SPEC。

### 7.8 WebUI

输入：浏览器请求或审批操作。

行为：

- 展示任务状态、审批队列、反馈摘要和记忆条目。
- 支持批准或拒绝审批请求。

输出：HTML 页面或 JSON API 响应。

边界：

- WebUI 不直接执行动作。
- WebUI 必须调用同一套 governance 和 approval API。

## 8. 技术选型与理由

- 语言：Python 3.11+，开发速度快，测试生态成熟，适合 CLI、WebUI、Docker 和教学演示。
- CLI：Typer，命令结构清晰，适合 `harness run`、`harness approvals`、`harness credentials`、`harness memory`。
- 数据模型：Pydantic，用于 action、feedback、approval 等结构化对象和边界校验。
- 测试：pytest，满足 mock LLM 确定性测试。
- lint/格式：ruff，速度快，配置简单。
- WebUI/API：FastAPI，轻量、易部署，适合最小演示接口。
- LLM：OpenAI-compatible API，真实模式可接供应商；测试和演示默认使用 mock LLM。
- 记忆：本地 JSON 默认存储；MySQL 作为未来 adapter；不使用 SQLite。
- 分发：Docker/OCI 镜像，便于新机器复现、挂载 workspace 和暴露 WebUI。

## 9. 凭据与安全设计

### 9.1 威胁模型

主要威胁包括：

- API key 被硬编码或提交到 Git。
- API key 出现在日志、错误信息或终端输出中。
- agent 读取 `.env` 或其它凭据文件并输出。
- shell 命令越权访问 workspace 外文件。
- agent 执行删除、发布、网络上传或长时间阻塞命令。
- WebUI 绕过治理层直接执行动作。

### 9.2 对策

- 凭据优先存入系统 keyring。
- 环境变量只作为兼容来源，README 明确 `.env` 是明文，存在进程环境可见风险。
- CLI 查看凭据状态时只显示存在性、来源和更新时间，不显示明文。
- 日志和异常统一经过脱敏处理。
- `PathFence` 阻止越界路径和敏感文件访问。
- `RiskClassifier` 对命令进行 allow/review/deny 分级。
- 中风险动作必须进入 HITL 审批状态机。
- 高风险动作直接拒绝。
- shell 执行必须有超时。
- WebUI 只调用核心 API，不绕过治理层。

## 10. 分发与部署设计

主分发形态是 Docker/OCI 镜像。

README 必须包含：

1. 本地开发安装命令。
2. `make test` 或等价测试命令。
3. `docker build` 构建命令。
4. `docker run` 运行 mock demo 的命令。
5. `docker run -p <port>` 启动 WebUI 的命令。
6. workspace 挂载方式。
7. API key 安全配置方式。
8. 已知限制和安全边界。

CI 使用 `.gitlab-ci.yml`，必须包含名为 `unit-test` 的 job；同时包含 Docker build job。MVP 最终交付提供本地 WebUI 访问地址和启动说明；公网部署与可远程访问 URL 属于未来部署项。

## 11. 非功能需求

- 安全性：凭据不硬编码、不提交、不打印；危险动作确定性拦截。
- 可靠性：命令执行有超时；长时间运行或阻塞风险命令进入审批或拒绝。
- 可测试性：核心机制移除真实 LLM 后仍可通过 mock LLM 单元测试验证。
- 可观测性：每轮 loop 记录 action、risk decision、observation、feedback、stop reason，日志脱敏。
- 可维护性：核心 loop、治理、反馈、记忆、凭据边界清晰。
- 可恢复性：审批请求、记忆、任务摘要持久化在 `.harness/`。
- 范围控制：MVP 不实现完整容器沙箱、向量检索、SQLite、复杂多 agent 编排。

## 12. 测试与机制演示

测试必须覆盖：

- action parsing。
- `PathFence`。
- `RiskClassifier`。
- `ApprovalStateMachine`。
- pytest、ruff 和 generic command feedback parser。
- `JsonMemoryStore`。
- credential masking。
- mock LLM 完整主循环。

机制演示必须至少包含：

1. mock LLM 试图执行危险动作，治理护栏拒绝或创建审批请求，动作没有实际执行。
2. mock LLM 第一轮写入有缺陷代码，pytest 失败；第二轮收到结构化反馈后修复；第三轮验证通过并结束。
3. HITL 审批请求从 `pending` 进入 `approved`、`rejected` 或 `expired`，主循环状态随之变化。

所有测试和演示不依赖网络、不依赖真实 LLM、不修改 workspace 外文件。

## 13. 验收标准

1. `pytest -q` 与 `ruff check src tests scripts` 在 Python 3.11+ 环境通过，核心测试不访问网络且不需要真实 API key。
2. `python scripts/mock_demo.py` 输出危险动作拒绝、反馈修复完成和 HITL 等待审批三个确定性结果。
3. CLI 能运行任务并管理审批、凭据和 JSON 记忆；WebUI 只展示状态和处理审批。
4. 默认持久化为 workspace 内 `.harness/` JSON 文件，不引入 SQLite 或 MySQL MVP 依赖。
5. 凭据不硬编码、不提交、不记录或明文显示，命令执行均有有限超时。
6. Dockerfile 可作为首选分发路径构建镜像；若本地环境不能访问 Docker daemon，必须如实记录该限制。
7. 根目录课程文档存在且 README 包含安装、使用、Docker、API key、安全边界和目录结构章节。

## 14. 最终交付清单

- `SPEC.md`：根据本设计文档沉淀的根目录规格文档。
- `PLAN.md`：由 Superpowers `writing-plans` 产出的实现计划。
- `SPEC_PROCESS.md`：记录 brainstorming、planning 和冷启动试运行过程。
- `AGENT_LOG.md`：记录技能使用、subagent 输出、人工干预和关键 commit。
- `README.md`：项目简介、安装、运行、分发、key 安全配置、目录结构、安全边界。
- `REFLECTION.md`：仅包含课程指定章节标题的反思占位模板，最终反思正文不由 agent 生成。
- 源代码：自有 harness 内核、CLI、WebUI、治理、反馈、记忆、凭据模块。
- 测试：mock LLM 单元测试和机制演示。
- CI：`.gitlab-ci.yml`，包含 `unit-test` job 和 Docker build。
- 分发产物：Dockerfile 和镜像构建说明。
- 部署信息：本地 WebUI 访问地址和启动说明；公网部署作为未来工作。

## 15. 风险与未决问题

- WebUI 是课程硬性展示项，但不能让前端工作稀释 harness 内核深度；MVP 只做最小展示和审批。
- 真实 LLM 接入必须严格保持为单次调用抽象，不能引入现成 agent runner。
- 风险分类规则需要足够明确，避免既过宽又过窄；PLAN 中应先用测试锁定风险规则。
- JSON 记忆文件简单可靠，但并发写入能力有限；MVP 接受该限制，未来可通过 MySQL adapter 增强。
- 完整容器沙箱很有价值，但超出 MVP 范围；当前通过路径围栏、命令风险分级、超时和 HITL 审批控制风险。
- 冷启动试运行需要另一个类型的 agent 执行 1-2 个 PLAN task；SPEC_PROCESS.md 必须记录它暴露的问题和修订。

## 16. 后续流程

1. 用户审阅并确认本设计文档。
2. 调用 Superpowers `writing-plans` 生成 `PLAN.md`。
3. 使用 git worktrees 隔离实现任务。
4. 按 TDD 执行每个 task。
5. 完成后请求代码评审。
6. 通过验证后按 finishing flow 决定 PR、merge 或保留分支。
