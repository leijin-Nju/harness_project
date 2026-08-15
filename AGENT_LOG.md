# Agent Log

| Time | Task | Superpowers Skill | Context / Prompt | Output / Commit | Human Intervention |
| --- | --- | --- | --- | --- | --- |
| 2026-08-10 | Design | brainstorming | A 类 Coding Agent Harness 课程目标与 MVP 约束 | `248ea5a` design spec | 确认范围与技术约束 |
| 2026-08-10 | Plan | writing-plans | 已确认设计、TDD 与逐任务交付要求 | `7daa413` implementation plan | 选择按计划执行 |
| 2026-08-11 | Tasks 1-2 | TDD | 共享模型、动作解析、mockable LLM | `5c49510`、`9734e24`；审查修订 `aef49dc`、`63a6bb5` | 无额外干预记录 |
| 2026-08-11 | Tasks 3-5 | TDD, systematic debugging | 路径围栏、风险分类、HITL 状态机 | `a1936f3`、`f3678da`、`34a80b9`；四次边界修订 | 无额外干预记录 |
| 2026-08-12 | Tasks 6-9 | TDD | JSON memory、反馈、工具、凭据 | `3c7c84c`、`5d02aad`、`b699509`、`c099e1c`；三次审查修订 | 明确禁止 SQLite 与明文凭据 |
| 2026-08-12 | Tasks 10-12 | TDD | 核心循环、CLI、最小 WebUI/API | `ecd3d97`、`e4830e7`、`f8b8f09` | 明确 CLI 为主、WebUI 为 adapter |
| 2026-08-12 | Tasks 13-14 | TDD, verification-before-completion | 确定性机制 demo、Docker、GitLab CI | `542c9f6`、`b395c23`、`d15d79d` | 要求所有 shell 命令有限超时 |
| 2026-08-12 | Task 15 previous dispatch | subagent workflow | 课程文档与最终验证 | 模型容量失败，无代码输出 | 用户重新派发并提供恢复说明 |
| 2026-08-12 | Task 15 | TDD, verification-before-completion | brief、设计、PLAN、Git 历史与现有验证说明 | 根目录课程文档、README、文档测试与报告 | 指定精确格式、文件范围和最终回复格式 |
| 2026-08-14 | WebUI polish | brainstorming, TDD, verification-before-completion | 最小 WebUI 需要展示任务、审批、反馈和记忆，并支持审批操作 | `src/harness/web.py` 与 `tests/test_web.py` 更新；`python -m pytest tests/test_web.py` 通过 | 明确 WebUI 仍只作为 adapter，不承担核心 loop |
| 2026-08-15 | Submission file selection | verification-before-completion | 区分必要提交文件、本地产物和可从 GitHub 拉取的内容 | 暂存 `REFLECTION.md`、`src/harness/web.py`、`tests/test_web.py`；排除测试临时目录、镜像 tar 和聊天日志 | 用户要求“必要的提交文件，其余可在 GitHub 上拉取” |
| 2026-08-15 | Non-code document completion | brainstorming | 根据课程通用要求与 A 类 harness 要求补全非代码交付信息 | README、DEPLOYMENT、AGENT_LOG、SPEC/SPEC_PROCESS 一致性修订 | 用户要求补全相关文档并包含应有信息 |
