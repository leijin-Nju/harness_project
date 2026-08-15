import json
from collections.abc import Callable
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from harness.config import HarnessConfig
from harness.governance.approval import ApprovalStateMachine, JsonApprovalStore
from harness.memory import JsonMemoryStore
from harness.models import ApprovalRequest, MemoryEntry, TaskRun


def create_app(workspace_root: str | Path) -> FastAPI:
    """Create a read-and-approval-only web adapter for local harness state."""
    config = HarnessConfig(workspace_root=Path(workspace_root))
    paths = config.paths()
    approval_store = JsonApprovalStore(paths["approvals"])
    approval_machine = ApprovalStateMachine(approval_store)
    memory_store = JsonMemoryStore(paths["memory"])
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        approvals = approval_store.list()
        memories = memory_store.list()
        runs = _load_runs(paths["runs_dir"])
        latest_run = escape(runs[-1].task) if runs else "无"
        pending_approvals = sum(1 for approval in approvals if approval.status.value == "pending")
        return f"""
        <!doctype html>
        <html lang="zh-CN">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>编码智能体控制台</title>
            <style>{_DASHBOARD_CSS}</style>
          </head>
          <body>
            <div class="app-frame">
              <header class="topbar">
                <div class="brand-block">
                  <p class="eyebrow">编码智能体控制台</p>
                  <h1>任务状态</h1>
                  <p class="workspace-meta">工作区：{escape(str(config.workspace_root))}</p>
                </div>
                <div class="toolbar">
                  <div id="approval-feedback" class="status-line" role="status">就绪</div>
                  <button id="refresh-dashboard" class="button primary" type="button">
                    刷新
                  </button>
                </div>
              </header>
              <main class="page-shell">
                <section class="metrics" aria-label="概览">
                  <article class="metric">
                    <span>运行</span>
                    <strong id="runs-count">{len(runs)}</strong>
                  </article>
                  <article class="metric">
                    <span>审批</span>
                    <strong id="approvals-count">{len(approvals)}</strong>
                  </article>
                  <article class="metric">
                    <span>待处理</span>
                    <strong id="pending-count">{pending_approvals}</strong>
                  </article>
                  <article class="metric">
                    <span>记忆</span>
                    <strong id="memory-count">{len(memories)}</strong>
                  </article>
                </section>
                <section class="latest-strip" aria-label="最近运行">
                  <span>最近</span>
                  <strong id="latest-run">{latest_run}</strong>
                </section>
                <section class="workbench-layout">
                  <div class="primary-column">
                    <section class="panel runs-panel" data-api-url="/api/runs">
                      <div class="panel-heading">
                        <div>
                          <h2>运行记录</h2>
                          <p>运行次数：{len(runs)}</p>
                        </div>
                      </div>
                      <div id="recent-runs" class="item-list">
                        {_render_runs(runs)}
                      </div>
                    </section>
                    <section class="panel feedback-panel">
                      <div class="panel-heading">
                        <div>
                          <h2>近期反馈</h2>
                          <p>来自最近运行的观察结果</p>
                        </div>
                      </div>
                      <div id="feedback-list" class="item-list">
                        {_render_feedback(runs)}
                      </div>
                    </section>
                  </div>
                  <aside class="side-rail">
                    <section class="panel approvals-panel" data-api-url="/api/approvals">
                      <div class="panel-heading">
                        <div>
                          <h2>审批队列</h2>
                          <p>审批请求：{len(approvals)}</p>
                        </div>
                      </div>
                      <div id="approval-list" class="item-list">
                        {_render_approvals(approvals)}
                      </div>
                    </section>
                    <section class="panel memory-panel" data-api-url="/api/memory">
                      <div class="panel-heading">
                        <div>
                          <h2>记忆</h2>
                          <p>记忆条目：{len(memories)}</p>
                        </div>
                      </div>
                      <div id="memory-list" class="item-list">
                        {_render_memories(memories)}
                      </div>
                    </section>
                  </aside>
                </section>
              </main>
            </div>
            <script>{_DASHBOARD_JS}</script>
          </body>
        </html>
        """

    @app.get("/api/approvals", response_model=list[ApprovalRequest])
    def list_approvals() -> list[ApprovalRequest]:
        return approval_store.list()

    @app.post("/api/approvals/{request_id}/approve", response_model=ApprovalRequest)
    def approve(request_id: str) -> ApprovalRequest:
        return _resolve_approval(approval_machine.approve, request_id)

    @app.post("/api/approvals/{request_id}/reject", response_model=ApprovalRequest)
    def reject(request_id: str) -> ApprovalRequest:
        return _resolve_approval(approval_machine.reject, request_id)

    @app.get("/api/memory", response_model=list[MemoryEntry])
    def list_memory() -> list[MemoryEntry]:
        return memory_store.list()

    @app.get("/api/runs", response_model=list[TaskRun])
    def list_runs() -> list[TaskRun]:
        return _load_runs(paths["runs_dir"])

    return app


def _load_runs(runs_dir: Path) -> list[TaskRun]:
    if not runs_dir.exists():
        return []
    runs = [
        TaskRun.model_validate_json(path.read_text(encoding="utf-8"))
        for path in runs_dir.glob("*.json")
    ]
    return sorted(runs, key=lambda run: run.updated_at)


def _render_runs(runs: list[TaskRun]) -> str:
    if not runs:
        return _empty_state("暂无运行记录。")
    items = []
    for run in reversed(runs[-8:]):
        stop_reason = f"<p>{escape(run.stop_reason)}</p>" if run.stop_reason else ""
        run_meta = (
            f"迭代次数：{run.iterations} | "
            f"更新时间：{_format_date(run.updated_at)}"
        )
        pending = (
            f'<span class="meta">审批：{escape(run.pending_approval_id)}</span>'
            if run.pending_approval_id
            else ""
        )
        items.append(
            f"""
            <article class="list-item">
              <div class="item-main">
                <div class="item-title-row">
                  <h3>{escape(run.task)}</h3>
                  {_status_badge(run.status.value)}
                </div>
                <p class="meta">{run_meta}</p>
                {stop_reason}
                {pending}
              </div>
            </article>
            """
        )
    return "".join(items)


def _render_approvals(approvals: list[ApprovalRequest]) -> str:
    if not approvals:
        return _empty_state("暂无审批请求。")
    items = []
    for approval in reversed(approvals[-8:]):
        action_type = escape(approval.action.type.value)
        payload = escape(_action_summary(approval.action.payload))
        reasons = "; ".join(approval.risk_decision.reasons)
        disabled = " disabled" if approval.status.value != "pending" else ""
        approve_button = (
            f'<button class="button approve" type="button" '
            f'data-approval-id="{escape(approval.id)}" '
            f'data-approval-action="approve"{disabled}>批准</button>'
        )
        reject_button = (
            f'<button class="button reject" type="button" '
            f'data-approval-id="{escape(approval.id)}" '
            f'data-approval-action="reject"{disabled}>拒绝</button>'
        )
        items.append(
            f"""
            <article class="list-item approval-item" data-approval-id="{escape(approval.id)}">
              <div class="item-main">
                <div class="item-title-row">
                  <h3>{action_type}</h3>
                  {_status_badge(approval.status.value)}
                </div>
                <code>{payload}</code>
                <p>{escape(reasons) if reasons else "暂无风险原因记录。"}</p>
                <p class="meta">创建时间：{_format_date(approval.created_at)}</p>
              </div>
              <div class="item-actions">
                {approve_button}
                {reject_button}
              </div>
            </article>
            """
        )
    return "".join(items)


def _render_memories(memories: list[MemoryEntry]) -> str:
    if not memories:
        return _empty_state("暂无记忆条目。")
    items = []
    for memory in reversed(memories[-8:]):
        keywords = ", ".join(memory.keywords)
        keyword_html = f'<p class="meta">关键词：{escape(keywords)}</p>' if keywords else ""
        items.append(
            f"""
            <article class="list-item">
              <div class="item-main">
                <div class="item-title-row">
                  <h3>{escape(memory.kind.value)}</h3>
                  <span class="meta">{_format_date(memory.created_at)}</span>
                </div>
                <p>{escape(memory.text)}</p>
                {keyword_html}
              </div>
            </article>
            """
        )
    return "".join(items)


def _render_feedback(runs: list[TaskRun]) -> str:
    observations = [
        (run, observation)
        for run in reversed(runs[-8:])
        for observation in reversed(run.observations[-3:])
    ]
    if not observations:
        return _empty_state("暂无近期反馈。")
    items = []
    for run, observation in observations[:8]:
        items.append(
            f"""
            <article class="list-item">
              <div class="item-main">
                <div class="item-title-row">
                  <h3>{escape(observation.summary)}</h3>
                  {_status_badge(observation.severity)}
                </div>
                <p>{escape(str(observation.details))}</p>
                <p class="meta">{escape(run.task)} | {escape(observation.kind)}</p>
              </div>
            </article>
            """
        )
    return "".join(items)


def _empty_state(message: str) -> str:
    return f'<p class="empty-state">{escape(message)}</p>'


def _status_badge(value: str) -> str:
    safe_value = escape(value)
    class_name = "badge"
    if value in {"pending", "waiting_for_approval", "review"}:
        class_name += " warning"
    elif value in {"approved", "completed", "allow", "info"}:
        class_name += " success"
    elif value in {"rejected", "failed", "deny", "error"}:
        class_name += " danger"
    return f'<span class="{class_name}">{safe_value}</span>'


def _format_date(value) -> str:
    return escape(value.strftime("%Y-%m-%d %H:%M:%S UTC"))


def _action_summary(payload: dict) -> str:
    if "command" in payload:
        return str(payload["command"])
    if "path" in payload:
        return str(payload["path"])
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _resolve_approval(
    operation: Callable[[str], ApprovalRequest], request_id: str
) -> ApprovalRequest:
    try:
        return operation(request_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="approval request not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


_DASHBOARD_CSS = """
:root {
  color-scheme: light;
  --bg: #f5f7f8;
  --surface: #ffffff;
  --surface-muted: #eef3f2;
  --border: #d7dfdd;
  --text: #182123;
  --muted: #5e6c70;
  --accent: #0b6f6a;
  --accent-strong: #084f4c;
  --warning: #9a6200;
  --warning-bg: #fff5d7;
  --danger: #a63a50;
  --danger-bg: #fde8ed;
  --success: #1e7b4f;
  --success-bg: #e5f5ec;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
}

.topbar {
  align-items: center;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 24px;
  justify-content: space-between;
  min-height: 112px;
  padding: 24px clamp(20px, 4vw, 56px);
}

.eyebrow,
.subtitle,
.meta,
.panel-heading p,
.empty-state {
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.45;
}

.eyebrow {
  font-weight: 700;
  letter-spacing: 0;
  margin: 0 0 6px;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  font-size: clamp(1.75rem, 3vw, 2.5rem);
  line-height: 1.1;
}

h2 {
  font-size: 1rem;
  line-height: 1.25;
}

h3 {
  font-size: 0.96rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.subtitle {
  margin-top: 8px;
  overflow-wrap: anywhere;
}

.page-shell {
  margin: 0 auto;
  max-width: 1180px;
  padding: 24px clamp(16px, 3vw, 32px) 40px;
}

.metrics {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
}

.metric,
.latest-strip,
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.metric {
  min-height: 92px;
  padding: 16px;
}

.metric span {
  color: var(--muted);
  display: block;
  font-size: 0.88rem;
}

.metric strong {
  display: block;
  font-size: 2rem;
  line-height: 1.2;
  margin-top: 8px;
}

.latest-strip {
  align-items: center;
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  min-height: 48px;
  padding: 12px 16px;
}

.latest-strip span {
  color: var(--muted);
}

.latest-strip strong {
  overflow-wrap: anywhere;
}

.status-line {
  color: var(--muted);
  min-height: 24px;
  padding: 0 2px 10px;
}

.status-line.error {
  color: var(--danger);
}

.dashboard-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.panel {
  min-width: 0;
  overflow: hidden;
}

.panel-heading {
  align-items: center;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  min-height: 66px;
  padding: 16px;
}

.item-list {
  display: grid;
  gap: 0;
}

.list-item {
  align-items: start;
  border-bottom: 1px solid var(--border);
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
  min-height: 82px;
  padding: 16px;
}

.list-item:last-child {
  border-bottom: 0;
}

.item-main {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.item-title-row {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.item-actions {
  display: flex;
  gap: 8px;
}

.button {
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  cursor: pointer;
  display: inline-flex;
  font: inherit;
  font-weight: 700;
  justify-content: center;
  min-height: 38px;
  padding: 0 14px;
  white-space: nowrap;
}

.button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}

.button:focus-visible {
  outline: 3px solid rgba(11, 111, 106, 0.28);
  outline-offset: 2px;
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

.button.primary,
.button.approve {
  background: var(--accent);
  border-color: var(--accent);
  color: #ffffff;
}

.button.reject {
  border-color: #e2b8c1;
  color: var(--danger);
}

.badge {
  background: var(--surface-muted);
  border-radius: 999px;
  color: var(--muted);
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1;
  padding: 6px 9px;
}

.badge.success {
  background: var(--success-bg);
  color: var(--success);
}

.badge.warning {
  background: var(--warning-bg);
  color: var(--warning);
}

.badge.danger {
  background: var(--danger-bg);
  color: var(--danger);
}

code {
  background: #f0f3f1;
  border: 1px solid var(--border);
  border-radius: 6px;
  display: block;
  font-family: "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
  font-size: 0.86rem;
  line-height: 1.5;
  max-width: 100%;
  overflow-wrap: anywhere;
  padding: 8px 10px;
}

.empty-state {
  padding: 18px 16px;
}

@media (max-width: 880px) {
  .metrics,
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .topbar .button {
    width: 100%;
  }
}

@media (max-width: 560px) {
  .list-item,
  .approval-item {
    grid-template-columns: 1fr;
  }

  .item-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .item-title-row {
    align-items: flex-start;
    flex-direction: column;
  }
}

h1 {
  font-size: 1.75rem;
}

.app-frame {
  min-height: 100vh;
}

.topbar {
  min-height: 96px;
  padding: 20px 40px;
}

.brand-block {
  min-width: 0;
}

.workspace-meta {
  color: var(--muted);
  font-size: 0.86rem;
  line-height: 1.45;
  margin-top: 8px;
  overflow-wrap: anywhere;
}

.toolbar {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  gap: 12px;
}

.toolbar .status-line {
  align-items: center;
  background: #f8faf9;
  border: 1px solid var(--border);
  border-radius: 999px;
  display: inline-flex;
  min-height: 34px;
  min-width: 96px;
  padding: 0 12px;
}

.page-shell {
  max-width: 1240px;
  padding: 20px 28px 36px;
}

.metrics {
  gap: 10px;
  margin-bottom: 12px;
}

.metric {
  min-height: 78px;
  padding: 13px 14px;
}

.metric span {
  font-size: 0.8rem;
}

.metric strong {
  font-size: 1.7rem;
  line-height: 1.15;
  margin-top: 6px;
}

.latest-strip {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  min-height: 42px;
  padding: 10px 14px;
}

.workbench-layout {
  align-items: start;
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.9fr);
}

.primary-column,
.side-rail {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.side-rail {
  position: sticky;
  top: 16px;
}

.panel-heading {
  background: #f8faf9;
  min-height: 58px;
  padding: 13px 14px;
}

.list-item {
  min-height: 74px;
  padding: 13px 14px;
}

.list-item:hover {
  background: #fbfcfc;
}

.item-main {
  gap: 7px;
}

.button {
  border-color: #bcc8c6;
  font-size: 0.88rem;
  min-height: 36px;
  padding: 0 13px;
}

.button.primary:hover:not(:disabled),
.button.approve:hover:not(:disabled) {
  background: var(--accent-strong);
  color: #ffffff;
}

.badge {
  font-size: 0.74rem;
  font-weight: 800;
  padding: 5px 8px;
}

code {
  font-size: 0.82rem;
  padding: 7px 9px;
}

@media (max-width: 980px) {
  .topbar {
    padding: 18px 20px;
  }

  .toolbar {
    width: 100%;
  }

  .toolbar .status-line,
  .toolbar .button {
    flex: 1 1 0;
  }

  .metrics,
  .workbench-layout {
    grid-template-columns: 1fr;
  }

  .side-rail {
    position: static;
  }
}

@media (max-width: 620px) {
  .page-shell {
    padding: 16px 14px 28px;
  }

  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .latest-strip {
    grid-template-columns: 1fr;
  }
}
"""


_DASHBOARD_JS = """
const endpoints = {
  runs: "/api/runs",
  approvals: "/api/approvals",
  memory: "/api/memory",
};

const state = {
  runs: [],
  approvals: [],
  memory: [],
};

const statusLine = document.querySelector("#approval-feedback");
const refreshButton = document.querySelector("#refresh-dashboard");
const approvalList = document.querySelector("#approval-list");

function text(value) {
  return value === null || value === undefined || value === "" ? "无" : String(value);
}

function formatDate(value) {
  if (!value) {
    return "未知";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return text(value);
  }
  return parsed.toLocaleString();
}

function badge(value) {
  const span = document.createElement("span");
  const normalized = text(value);
  span.className = "badge";
  if (["pending", "waiting_for_approval", "review"].includes(normalized)) {
    span.classList.add("warning");
  } else if (["approved", "completed", "allow", "info"].includes(normalized)) {
    span.classList.add("success");
  } else if (["rejected", "failed", "deny", "error"].includes(normalized)) {
    span.classList.add("danger");
  }
  span.textContent = normalized;
  return span;
}

function showStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function clearAndEmpty(target, message) {
  target.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "empty-state";
  empty.textContent = message;
  target.append(empty);
}

function itemShell(title, statusValue) {
  const article = document.createElement("article");
  article.className = "list-item";

  const main = document.createElement("div");
  main.className = "item-main";

  const row = document.createElement("div");
  row.className = "item-title-row";

  const heading = document.createElement("h3");
  heading.textContent = text(title);
  row.append(heading, badge(statusValue));
  main.append(row);
  article.append(main);
  return { article, main };
}

function renderRuns(runs) {
  const target = document.querySelector("#recent-runs");
  target.replaceChildren();
  if (!runs.length) {
    clearAndEmpty(target, "暂无运行记录。");
    return;
  }
  runs.slice(-8).reverse().forEach((run) => {
    const { article, main } = itemShell(run.task, run.status);
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = `迭代次数：${run.iterations} | 更新时间：${formatDate(run.updated_at)}`;
    main.append(meta);
    if (run.stop_reason) {
      const reason = document.createElement("p");
      reason.textContent = run.stop_reason;
      main.append(reason);
    }
    if (run.pending_approval_id) {
      const pending = document.createElement("span");
      pending.className = "meta";
      pending.textContent = `审批：${run.pending_approval_id}`;
      main.append(pending);
    }
    target.append(article);
  });
}

function actionSummary(action) {
  const payload = action?.payload || {};
  if (payload.command) {
    return payload.command;
  }
  if (payload.path) {
    return payload.path;
  }
  return JSON.stringify(payload);
}

function renderApprovals(approvals) {
  approvalList.replaceChildren();
  if (!approvals.length) {
    clearAndEmpty(approvalList, "暂无审批请求。");
    return;
  }
  approvals.slice(-8).reverse().forEach((approval) => {
    const { article, main } = itemShell(approval.action?.type, approval.status);
    article.classList.add("approval-item");
    article.dataset.approvalId = approval.id;

    const code = document.createElement("code");
    code.textContent = actionSummary(approval.action);
    main.append(code);

    const reason = document.createElement("p");
    reason.textContent = (approval.risk_decision?.reasons || []).join("; ") ||
      "暂无风险原因记录。";
    main.append(reason);

    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = `创建时间：${formatDate(approval.created_at)}`;
    main.append(meta);

    const actions = document.createElement("div");
    actions.className = "item-actions";
    ["approve", "reject"].forEach((operation) => {
      const button = document.createElement("button");
      button.className = operation === "approve" ? "button approve" : "button reject";
      button.type = "button";
      button.dataset.approvalId = approval.id;
      button.dataset.approvalAction = operation;
      button.textContent = operation === "approve" ? "批准" : "拒绝";
      button.disabled = approval.status !== "pending";
      actions.append(button);
    });
    article.append(actions);
    approvalList.append(article);
  });
}

function renderMemory(entries) {
  const target = document.querySelector("#memory-list");
  target.replaceChildren();
  if (!entries.length) {
    clearAndEmpty(target, "暂无记忆条目。");
    return;
  }
  entries.slice(-8).reverse().forEach((entry) => {
    const { article, main } = itemShell(entry.kind, formatDate(entry.created_at));
    const body = document.createElement("p");
    body.textContent = entry.text;
    main.append(body);
    if (entry.keywords?.length) {
      const keywords = document.createElement("p");
      keywords.className = "meta";
      keywords.textContent = `关键词：${entry.keywords.join(", ")}`;
      main.append(keywords);
    }
    target.append(article);
  });
}

function renderFeedback(runs) {
  const target = document.querySelector("#feedback-list");
  target.replaceChildren();
  const observations = runs
    .slice(-8)
    .reverse()
    .flatMap((run) => (run.observations || [])
      .slice(-3)
      .reverse()
      .map((observation) => ({ run, observation })));
  if (!observations.length) {
    clearAndEmpty(target, "暂无近期反馈。");
    return;
  }
  observations.slice(0, 8).forEach(({ run, observation }) => {
    const { article, main } = itemShell(observation.summary, observation.severity);
    const body = document.createElement("p");
    body.textContent = typeof observation.details === "string"
      ? observation.details
      : JSON.stringify(observation.details);
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = `${run.task} | ${observation.kind}`;
    main.append(body, meta);
    target.append(article);
  });
}

function renderDashboard() {
  document.querySelector("#runs-count").textContent = state.runs.length;
  document.querySelector("#approvals-count").textContent = state.approvals.length;
  document.querySelector("#pending-count").textContent = state.approvals.filter(
    (approval) => approval.status === "pending"
  ).length;
  document.querySelector("#memory-count").textContent = state.memory.length;
  document.querySelector("#latest-run").textContent = state.runs.length
    ? state.runs[state.runs.length - 1].task
    : "无";
  renderRuns(state.runs);
  renderApprovals(state.approvals);
  renderMemory(state.memory);
  renderFeedback(state.runs);
}

async function refreshDashboard() {
  refreshButton.disabled = true;
  showStatus("正在刷新...");
  try {
    const [runs, approvals, memory] = await Promise.all(
      [endpoints.runs, endpoints.approvals, endpoints.memory].map(async (url) => {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`${url} returned ${response.status}`);
        }
        return response.json();
      })
    );
    state.runs = runs;
    state.approvals = approvals;
    state.memory = memory;
    renderDashboard();
    showStatus("已更新。");
  } catch (error) {
    showStatus(error.message || "控制台刷新失败。", true);
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", refreshDashboard);
approvalList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-approval-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  const { approvalId, approvalAction } = button.dataset;
  showStatus(`${approvalAction === "approve" ? "正在批准" : "正在拒绝"} ${approvalId}...`);
  try {
    const response = await fetch(
      `/api/approvals/${approvalId}/${approvalAction}`,
      { method: "POST" }
    );
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `请求失败，状态码 ${response.status}`);
    }
    await refreshDashboard();
  } catch (error) {
    showStatus(error.message || "审批更新失败。", true);
    button.disabled = false;
  }
});
"""


app = create_app(Path.cwd())
