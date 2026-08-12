# SPEC Process

## Brainstorming Key Nodes

1. 将课程 A 类项目收敛为 Coding Agent Harness，而不是通用聊天机器人或现成 agent runner 的包装。
2. 确定主贡献机制为治理护栏、工作区边界与 HITL，反馈闭环作为可观察的第二机制。
3. 将 CLI 定为主要入口，WebUI 限定为状态展示和审批 adapter，避免前端稀释核心机制。
4. 将默认记忆方案确定为本地 JSON；明确排除 SQLite，MySQL 只保留未来 adapter 边界。
5. 将 mock LLM、离线测试和三场景 demo 作为验收核心，使课程评审无需网络和真实 key。
6. 将 Docker 定为首选分发路径，并在 GitLab CI 中分别验证单元测试和镜像构建。

## Three Critical Iterations

### 迭代一：从“能调用模型”转向“自有可验证循环”

初始范围容易停留在 LLM 调用和工具封装。规格将核心明确为
`context -> action -> governance -> tool -> feedback -> next action`，并要求每一轮状态持久化。
这使实现和评审都能检查机制，而不是只观察最终文本。

### 迭代二：从提示词安全转向确定性治理

安全规则从“提示模型不要做危险操作”修订为代码级路径围栏、命令风险分类和审批状态机。
后续提交继续补强复合 shell 命令、敏感文件和待审批状态，说明冷启动实现暴露了规则边界问题。

### 迭代三：从可运行项目转向可复现课程交付

最终范围加入 mock LLM 三场景演示、Docker、GitLab CI、根目录课程文档和文档测试。
分发命令随后增加有限超时，以满足阻塞风险约束；README 同步明确凭据与隔离边界。

## Adopted AI Suggestions

- 使用 Pydantic 结构化 action、tool result、feedback、approval、memory 和 run 状态。
- 使用 mock LLM 脚本驱动主循环，覆盖危险动作拒绝、反馈修复和 HITL 等待。
- 使用 JSON 原子替换持久化审批和记忆，保持 MVP 简单且离线可测。
- 使用 keyring 优先、环境变量后备的凭据策略，状态输出只显示掩码。
- 使用细粒度 TDD 任务和独立提交，使每个机制都能在集成前验证。

## Rejected Or Revised AI Suggestions

- 未采用 LangChain、AutoGen、CrewAI 或 LlamaIndex agent runner，因为项目要求自有核心循环。
- 未采用 SQLite；默认存储固定为本地 JSON，MySQL 仅保留未实现的未来 adapter。
- 未让 WebUI 执行命令或拥有独立 agent loop，避免出现双重治理路径。
- 未在 MVP 中实现完整容器沙箱；当前明确记录其局限并使用围栏、分级、审批和超时降低风险。
- 将可能泄露凭据的明文配置方案修订为 keyring 优先，并对环境变量与 `.env` 风险作显式说明。

## Cold-Start Trial Record

冷启动按 PLAN 的独立任务逐步执行，并由后续审查提交暴露和修复问题。代表性发现包括：

| 首次实现 | 暴露的问题 | 修订证据 |
| --- | --- | --- |
| 共享模型与审批字段 | `REVIEW` 决策需要强制关联审批 | `aef49dc` |
| OpenAI-compatible action schema | schema 包装不符合接口预期 | `63a6bb5` |
| 路径围栏 | action 类型与敏感文件检查不完整 | `93f2b96` |
| 命令风险分类 | 复合命令与多种 chaining 语法可绕过单命令判断 | `9d33357`、`7c70d27` |
| 审批状态机 | 非 pending 请求仍可能被重复处理 | `671023e` |
| JSON 记忆 | 项目形式的 API key 仍需脱敏 | `9438301` |
| 反馈解析 | 失败信息可能出现在 stdout 或 stderr | `1e9e72e` |
| 工具执行器 | 治理必须在执行边界再次强制 | `3ace5eb` |
| Docker/CI | 安装、测试与构建命令需要有限超时 | `d15d79d` |

Task 15 的前一次模型调度因容量失败且没有产生代码；本次直接从 brief、设计文档、PLAN 和
Git 历史恢复上下文。工作区中未跟踪的课程源文件未被修改或纳入提交。

## Reflection On Brainstorming

brainstorming 的主要价值是把“做一个 coding agent”拆成可验收的机制与边界，并提前锁定
MVP 不做什么。最重要的收获不是增加功能，而是让 mock、治理、存储、凭据和分发策略彼此
一致。过程上的不足是初始规则仍需多轮实现审查才能覆盖复合命令和跨输出流等边界；因此
后续类似项目应更早把绕过场景和失败通道写入规格示例。
