# 本地会话日志

本目录保存从本机 Codex 本地日志目录导出的会话日志，筛选条件为日志内容中包含 `harness_project`。

- `sessions/`：来自 `C:\Users\30479\.codex\sessions` 的活动/历史会话日志。
- `archived_sessions/`：来自 `C:\Users\30479\.codex\archived_sessions` 的归档会话日志。
- `manifest.csv`：导出清单，包含来源集合、文件名、源路径、最后修改时间和文件大小。

日志文件为原始 `.jsonl` transcript，可能包含提示词、命令输出、本地路径、代码片段以及其他敏感信息。提交或分享前请先审查内容。
