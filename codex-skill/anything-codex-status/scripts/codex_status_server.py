#!/usr/bin/env python3
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PORT = int(os.environ.get("CODEX_STATUS_PORT", "8765"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
WORKSPACE_ENV = os.environ.get("CODEX_STATUS_WORKSPACE")
WORKSPACE = Path(WORKSPACE_ENV).expanduser().resolve() if WORKSPACE_ENV else Path.cwd().resolve()
STATE_DB = CODEX_HOME / "state_5.sqlite"
GOALS_DB = CODEX_HOME / "goals_1.sqlite"
ACCOUNTS_REGISTRY = CODEX_HOME / "accounts" / "registry.json"
SESSION_INDEX = CODEX_HOME / "session_index.jsonl"
FINAL_PHASES = {"final", "final_answer"}


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <title>Codex Status</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f4f6f1;
      --ink: #171b1d;
      --muted: #66706d;
      --line: #cbd2cc;
      --panel: #ffffff;
      --soft: #e9eee8;
      --accent: #0d8d7d;
      --accent-2: #cf5e36;
      --ok: #16794c;
      --warn: #b86a17;
      --bad: #b63f32;
      --shadow: 0 14px 34px rgba(23, 27, 29, 0.09);
    }

    * { box-sizing: border-box; }

    html, body { min-height: 100%; }

    body {
      margin: 0;
      background:
        linear-gradient(135deg, rgba(13, 141, 125, 0.08), transparent 36%),
        linear-gradient(315deg, rgba(207, 94, 54, 0.08), transparent 34%),
        var(--paper);
      color: var(--ink);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Display",
        "SF Pro Text", "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }

    .shell {
      width: min(100%, 1120px);
      min-height: 100svh;
      margin: 0 auto;
      padding: max(16px, env(safe-area-inset-top)) max(14px, env(safe-area-inset-right))
        max(18px, env(safe-area-inset-bottom)) max(14px, env(safe-area-inset-left));
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .topbar {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: start;
      gap: 10px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 12px;
    }

    .top-actions {
      display: flex;
      align-items: flex-start;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }

    h1 {
      margin: 0;
      font-size: 30px;
      line-height: 1;
      font-weight: 780;
      letter-spacing: 0;
    }

    .subtitle {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.3;
      word-break: break-word;
    }

    .live {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 30px;
      padding: 6px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.72);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .switch {
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 30px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--ink);
      font-size: 12px;
      font-weight: 760;
      user-select: none;
    }

    .switch input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }

    .switch-track {
      width: 38px;
      height: 22px;
      border: 1px solid #98a29e;
      border-radius: 999px;
      background: #dbe2dc;
      transition: background 180ms ease, border-color 180ms ease;
    }

    .switch-thumb {
      display: block;
      width: 16px;
      height: 16px;
      margin: 2px;
      border-radius: 50%;
      background: #ffffff;
      box-shadow: 0 1px 4px rgba(23, 27, 29, 0.28);
      transition: transform 180ms ease;
    }

    .switch input:checked + .switch-track {
      border-color: var(--accent);
      background: var(--accent);
    }

    .switch input:checked + .switch-track .switch-thumb {
      transform: translateX(16px);
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--warn);
      box-shadow: 0 0 0 4px rgba(184, 106, 23, 0.14);
    }

    .dot.ready {
      background: var(--ok);
      box-shadow: 0 0 0 4px rgba(22, 121, 76, 0.14);
    }

    .dot.running {
      background: var(--accent);
      box-shadow: 0 0 0 4px rgba(13, 141, 125, 0.14);
    }

    .grid {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr;
      flex: 1;
    }

    .panel {
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 13px;
      min-width: 0;
    }

    .panel.compact { box-shadow: none; }

    .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      text-transform: uppercase;
    }

    .headline {
      margin-top: 6px;
      font-size: 23px;
      line-height: 1.08;
      font-weight: 780;
      word-break: break-word;
    }

    .task {
      margin-top: 10px;
      color: #26302d;
      font-size: 14px;
      line-height: 1.42;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .kv {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .mini {
      min-height: 64px;
      padding: 10px;
      border-radius: 8px;
      background: var(--soft);
      border: 1px solid rgba(23, 27, 29, 0.06);
    }

    .mini strong {
      display: block;
      margin-top: 5px;
      font-size: 17px;
      line-height: 1.05;
      overflow-wrap: anywhere;
    }

    .usage {
      display: grid;
      gap: 10px;
    }

    .meter-row {
      display: grid;
      gap: 7px;
    }

    .meter-top {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }

    .meter-name {
      font-size: 15px;
      font-weight: 780;
    }

    .meter-value {
      font-size: 18px;
      font-weight: 800;
      white-space: nowrap;
    }

    .bar {
      height: 14px;
      border: 1px solid #98a29e;
      border-radius: 999px;
      background: #edf1ed;
      overflow: hidden;
    }

    .fill {
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, var(--ink), var(--accent));
      transition: width 280ms ease;
    }

    .fill.warn { background: linear-gradient(90deg, var(--accent-2), var(--warn)); }

    .reset {
      color: var(--muted);
      font-size: 12px;
    }

    .tokens {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }

    .big-number {
      font-size: 22px;
      font-weight: 820;
      line-height: 1;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }

    .log {
      margin: 0;
      max-height: 140px;
      overflow: hidden;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      line-height: 1.42;
      color: #28302e;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .footer {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 11px;
      padding-top: 2px;
    }

    body.compact-mode .subtitle,
    body.compact-mode .task-panel,
    body.compact-mode .runtime-panel,
    body.compact-mode .activity-panel {
      display: none;
    }

    body.compact-mode .grid {
      grid-template-columns: minmax(0, 620px);
      justify-content: center;
      align-content: start;
    }

    body.compact-mode .account-panel {
      box-shadow: var(--shadow);
    }

    @media (orientation: landscape) and (max-height: 520px) {
      .shell { gap: 8px; padding: 10px 12px; }
      .topbar { padding-bottom: 8px; }
      h1 { font-size: 24px; }
      .subtitle { margin-top: 3px; font-size: 12px; }
      .grid { grid-template-columns: 1.15fr 0.85fr; gap: 8px; }
      .panel { padding: 10px; }
      .headline { font-size: 20px; }
      .task { -webkit-line-clamp: 3; font-size: 13px; }
      .usage { gap: 8px; }
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .tokens { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .log { max-height: 88px; }
    }

    @media (min-width: 760px) {
      .shell { padding: 24px; }
      .grid { grid-template-columns: 1.1fr 0.9fr; }
      .headline { font-size: 28px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1>Codex Status</h1>
        <div class="subtitle" id="subtitle">Loading local thread...</div>
      </div>
      <div class="top-actions">
        <label class="switch" title="Show recent task">
          <input type="checkbox" id="showTaskToggle" checked>
          <span class="switch-track"><span class="switch-thumb"></span></span>
          <span>Task</span>
        </label>
        <div class="live"><span class="dot" id="dot"></span><span id="stateText">SYNC</span></div>
      </div>
    </header>

    <section class="grid">
      <article class="panel task-panel">
        <div class="label">Current Task</div>
        <div class="headline" id="title">--</div>
        <div class="task" id="task">Waiting for status data.</div>
        <div class="kv">
          <div class="mini"><div class="label">Model</div><strong id="model">--</strong></div>
          <div class="mini"><div class="label">Reasoning</div><strong id="effort">--</strong></div>
          <div class="mini"><div class="label">Thread Tokens</div><strong id="threadTokens">--</strong></div>
          <div class="mini"><div class="label">Updated</div><strong id="updated">--</strong></div>
        </div>
      </article>

      <div class="usage">
        <article class="panel compact account-panel">
          <div class="summary-grid">
            <div class="mini"><div class="label">Account</div><strong id="account">--</strong></div>
            <div class="mini"><div class="label">Plan</div><strong id="accountPlan">--</strong></div>
          </div>
        </article>

        <article class="panel compact">
          <div class="meter-row">
            <div class="meter-top">
              <div class="meter-name">5h quota</div>
              <div class="meter-value" id="quota5h">--</div>
            </div>
            <div class="bar"><div class="fill" id="quota5hFill"></div></div>
            <div class="reset" id="quota5hReset">--</div>
          </div>
        </article>

        <article class="panel compact">
          <div class="meter-row">
            <div class="meter-top">
              <div class="meter-name">Weekly quota</div>
              <div class="meter-value" id="quotaWeek">--</div>
            </div>
            <div class="bar"><div class="fill warn" id="quotaWeekFill"></div></div>
            <div class="reset" id="quotaWeekReset">--</div>
          </div>
        </article>

        <article class="panel compact runtime-panel">
          <div class="tokens">
            <div><div class="label">Session</div><div class="big-number" id="contextPct">--</div></div>
            <div><div class="label">Last Turn</div><div class="big-number" id="lastTurn">--</div></div>
            <div><div class="label">Plan</div><div class="big-number" id="plan">--</div></div>
          </div>
        </article>
      </div>
    </section>

    <article class="panel compact activity-panel">
      <div class="label">Recent Activity</div>
      <pre class="log" id="activity">--</pre>
    </article>

    <footer class="footer">
      <span id="server">local</span>
      <span id="clock">--</span>
    </footer>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    const fmt = new Intl.NumberFormat("en-US");
    const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
    const taskToggle = $("showTaskToggle");

    function applyTaskVisibility(showTask, persist = true) {
      document.body.classList.toggle("compact-mode", !showTask);
      taskToggle.checked = showTask;
      if (persist) {
        localStorage.setItem("codex-status-show-task", showTask ? "1" : "0");
      }
    }

    function setMeter(id, fillId, value) {
      const label = $(id);
      const fill = $(fillId);
      if (typeof value !== "number") {
        label.textContent = "--";
        fill.style.width = "0%";
        return;
      }
      const bounded = Math.max(0, Math.min(100, value));
      label.textContent = `${bounded.toFixed(0)}%`;
      fill.style.width = `${bounded}%`;
    }

    function text(value, fallback = "--") {
      return value === null || value === undefined || value === "" ? fallback : String(value);
    }

    function displayPlan(ratePlan, accountPlan) {
      const plan = text(ratePlan || accountPlan, "").toLowerCase();
      if (!plan) return "Unknown";
      if (plan.startsWith("pro")) return "Pro";
      if (plan === "plus") return "Plus";
      if (plan === "free") return "Free";
      if (plan === "team" || plan === "teams") return "Team";
      if (plan === "enterprise") return "Enterprise";
      return text(ratePlan || accountPlan);
    }

    async function refresh() {
      try {
        const res = await fetch("/api/status", { cache: "no-store" });
        const data = await res.json();
        const thread = data.thread || {};
        const usage = data.usage || {};
        const rate = usage.rate_limits || {};
        const state = data.state || {};
        const account = data.account || {};
        const accountLabel = account.email || account.profile_name || account.account_name || account.auth_mode;
        const planLabel = displayPlan(rate.plan_type, account.plan);

        $("title").textContent = text(thread.display_title || thread.title);
        $("task").textContent = text(data.latest_user_message || thread.preview, "No recent task text.");
        $("subtitle").textContent = `${text(thread.id).slice(0, 8)} · ${text(thread.cwd)} · ${text(data.tailscale_ip, "Tailscale unknown")}`;
        $("model").textContent = text(thread.model);
        $("effort").textContent = text(thread.reasoning_effort);
        $("threadTokens").textContent = thread.tokens_used ? fmt.format(thread.tokens_used) : "--";
        $("updated").textContent = text(thread.updated_relative);

        $("stateText").textContent = state.label || "SYNC";
        $("dot").className = `dot ${state.kind || ""}`;

        setMeter("quota5h", "quota5hFill", rate.primary?.used_percent);
        setMeter("quotaWeek", "quotaWeekFill", rate.secondary?.used_percent);
        $("quota5hReset").textContent = rate.primary?.reset_relative || "5h quota source not seen yet";
        $("quotaWeekReset").textContent = rate.secondary?.reset_relative || "Weekly quota source not seen yet";

        $("account").textContent = text(accountLabel, "Unknown");
        $("accountPlan").textContent = text(planLabel, "Unknown");
        $("contextPct").textContent = usage.total_tokens ? compact.format(usage.total_tokens) : "--";
        $("lastTurn").textContent = usage.last_turn_tokens ? fmt.format(usage.last_turn_tokens) : "--";
        $("plan").textContent = displayPlan(rate.plan_type, account.plan);
        $("activity").textContent = (data.activity || []).join("\\n") || "--";
        $("server").textContent = text(data.server);
        $("clock").textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
      } catch (error) {
        $("stateText").textContent = "OFFLINE";
        $("dot").className = "dot";
        $("activity").textContent = error.message;
      }
    }

    taskToggle.addEventListener("change", () => applyTaskVisibility(taskToggle.checked));
    applyTaskVisibility(localStorage.getItem("codex-status-show-task") !== "0", false);
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


def sqlite_connect(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)


def iso_to_epoch(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def relative_time(epoch):
    if not epoch:
        return "--"
    delta = int(time.time() - epoch)
    future = delta < 0
    delta = abs(delta)
    if delta < 60:
        text = f"{delta}s"
    elif delta < 3600:
        text = f"{delta // 60}m"
    elif delta < 86400:
        text = f"{delta // 3600}h"
    else:
        text = f"{delta // 86400}d"
    return f"in {text}" if future else f"{text} ago"


def wall_time(epoch):
    if not epoch:
        return "--"
    return datetime.fromtimestamp(epoch).strftime("%H:%M")


def shorten(value, limit=180):
    if not value:
        return ""
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def compact_title(*candidates):
    for candidate, allow_long in candidates:
        if not candidate:
            continue
        text = " ".join(str(candidate).split())
        if not text:
            continue
        if not allow_long and len(text) > 42:
            continue
        if len(text) <= 28:
            return text
        for mark in ["。", "？", "?", "，", ",", "：", ":"]:
            idx = text.find(mark)
            if 8 <= idx <= 34:
                text = text[:idx]
                break
        return shorten(text, 32)
    return "Codex task"


def query_sidebar_title(thread_id):
    if not thread_id or not SESSION_INDEX.exists():
        return None
    title = None
    try:
        for line in recent_lines(SESSION_INDEX, max_bytes=5_000_000):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("id") == thread_id and item.get("thread_name"):
                title = item["thread_name"]
    except OSError:
        return None
    return title


def query_current_thread():
    if not STATE_DB.exists():
        return None
    with sqlite_connect(STATE_DB) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            SELECT id, title, cwd, model, reasoning_effort, tokens_used, updated_at_ms,
                   updated_at, preview, rollout_path
            FROM threads
            WHERE cwd = ?
            ORDER BY updated_at_ms DESC, updated_at DESC
            LIMIT 1
            """,
            (str(WORKSPACE),),
        ).fetchone()
        if row is None:
            row = con.execute(
                """
                SELECT id, title, cwd, model, reasoning_effort, tokens_used, updated_at_ms,
                       updated_at, preview, rollout_path
                FROM threads
                ORDER BY updated_at_ms DESC, updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        updated_epoch = None
        if data.get("updated_at_ms"):
            updated_epoch = data["updated_at_ms"] / 1000
        elif data.get("updated_at"):
            updated_epoch = data["updated_at"]
        data["updated_epoch"] = updated_epoch
        data["updated_relative"] = relative_time(updated_epoch)
        data["preview"] = shorten(data.get("preview"), 240)
        data["sidebar_title"] = query_sidebar_title(data.get("id"))
        return data


def query_goal(thread_id):
    if not thread_id or not GOALS_DB.exists():
        return None
    with sqlite_connect(GOALS_DB) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            SELECT objective, status, token_budget, tokens_used, time_used_seconds, updated_at_ms
            FROM thread_goals
            WHERE thread_id = ?
            """,
            (thread_id,),
        ).fetchone()
        return dict(row) if row else None


def query_active_account():
    if not ACCOUNTS_REGISTRY.exists():
        return None
    try:
        registry = json.loads(ACCOUNTS_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    items = registry.get("items") or []
    active_key = registry.get("activeAccountKey")
    account = None
    for item in items:
        if item.get("accountKey") == active_key:
            account = item
            break
    if account is None and items:
        account = items[0]
    if not isinstance(account, dict):
        return None

    return {
        "email": account.get("email"),
        "profile_name": account.get("profileName"),
        "account_name": account.get("accountName"),
        "workspace_name": account.get("workspaceName"),
        "plan": account.get("plan"),
        "auth_mode": account.get("authMode"),
        "has_active_subscription": account.get("hasActiveSubscription"),
    }


def content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text") or item.get("content") or "")
        return "".join(parts)
    return ""


def parse_rollout(path):
    result = {
        "latest_user_message": None,
        "latest_assistant_message": None,
        "last_user_epoch": None,
        "last_final_epoch": None,
        "last_event_epoch": None,
        "usage": {},
        "activity": [],
    }
    if not path:
        return result
    rollout = Path(path)
    if not rollout.exists():
        return result

    activity = []
    latest_meaningful_rate_limits = None

    def add_activity(epoch, kind, message):
        text = shorten(message, 110)
        entry = {"minute": wall_time(epoch), "kind": kind, "text": text}
        if activity and activity[-1]["kind"] == kind and activity[-1]["text"] == text:
            activity[-1] = entry
            return
        activity.append(entry)
    for line in recent_lines(rollout):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            epoch = iso_to_epoch(item.get("timestamp"))
            if epoch:
                result["last_event_epoch"] = epoch
            payload = item.get("payload") or {}
            typ = item.get("type")

            if typ == "event_msg":
                ptype = payload.get("type")
                if ptype == "user_message":
                    msg = payload.get("message") or payload.get("text") or ""
                    result["latest_user_message"] = shorten(msg, 360)
                    result["last_user_epoch"] = epoch
                    add_activity(epoch, "USER", msg)
                elif ptype == "agent_message":
                    msg = payload.get("message") or ""
                    phase = payload.get("phase") or ""
                    result["latest_assistant_message"] = shorten(msg, 220)
                    if phase in FINAL_PHASES:
                        result["last_final_epoch"] = epoch
                    add_activity(epoch, "CODEX", msg)
                elif ptype == "token_count":
                    usage = {
                        "info": payload.get("info") or {},
                        "rate_limits": payload.get("rate_limits") or {},
                    }
                    result["usage"] = normalize_usage(usage)
                    rate_limits = result["usage"].get("rate_limits") or {}
                    if has_meaningful_rate_limits(rate_limits):
                        latest_meaningful_rate_limits = rate_limits
                    add_activity(epoch, "USAGE", "quota sample updated")
                elif ptype == "task_complete":
                    completed_at = payload.get("completed_at")
                    if completed_at:
                        result["last_final_epoch"] = completed_at
                    elif epoch:
                        result["last_final_epoch"] = epoch
                    msg = payload.get("last_agent_message") or "task complete"
                    result["latest_assistant_message"] = shorten(msg, 220)
                    add_activity(result["last_final_epoch"], "CODEX", msg)

            elif typ == "response_item":
                rtype = payload.get("type")
                if rtype == "message":
                    role = payload.get("role")
                    msg = content_text(payload.get("content"))
                    phase = payload.get("phase") or ""
                    if role == "user":
                        result["latest_user_message"] = shorten(msg, 360)
                        result["last_user_epoch"] = epoch
                        add_activity(epoch, "USER", msg)
                    elif role == "assistant":
                        result["latest_assistant_message"] = shorten(msg, 220)
                        if phase in FINAL_PHASES:
                            result["last_final_epoch"] = epoch
                        add_activity(epoch, "CODEX", msg)
                elif rtype == "function_call":
                    name = payload.get("name") or "tool"
                    add_activity(epoch, "TOOL", f"start {name}")
                elif rtype == "function_call_output":
                    add_activity(epoch, "TOOL", "done")

    recent = []
    seen = set()
    for entry in reversed(activity):
        key = (entry["kind"], entry["text"])
        if key in seen:
            continue
        seen.add(key)
        recent.append(entry)
        if len(recent) >= 7:
            break
    recent.reverse()
    result["activity"] = [
        f"{entry['minute']} {entry['kind']} {entry['text']}" for entry in recent
    ]
    usage = result.get("usage") or {}
    current_rate_limits = usage.get("rate_limits") or {}
    if latest_meaningful_rate_limits and should_fallback_rate_limits(current_rate_limits):
        fallback_rate_limits = dict(latest_meaningful_rate_limits)
        fallback_rate_limits["fallback_from_limit_id"] = current_rate_limits.get("limit_id")
        fallback_rate_limits["source"] = "recent_valid_sample"
        usage["rate_limits"] = fallback_rate_limits
    return result


def recent_lines(path, max_bytes=3_000_000):
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
            handle.readline()
        for line in handle:
            yield line.decode("utf-8", errors="ignore")


def normalize_limit(limit):
    if not isinstance(limit, dict):
        return None
    resets = limit.get("resets_at")
    return {
        "used_percent": limit.get("used_percent"),
        "window_minutes": limit.get("window_minutes"),
        "resets_at": resets,
        "reset_relative": f"resets {relative_time(resets)}" if resets else None,
    }


def limit_used_percent(limit):
    if not isinstance(limit, dict):
        return None
    value = limit.get("used_percent")
    return value if isinstance(value, (int, float)) else None


def has_meaningful_rate_limits(rate_limits):
    if not isinstance(rate_limits, dict):
        return False
    primary = limit_used_percent(rate_limits.get("primary"))
    secondary = limit_used_percent(rate_limits.get("secondary"))
    return any(value is not None and value > 0 for value in [primary, secondary])


def should_fallback_rate_limits(rate_limits):
    if not isinstance(rate_limits, dict):
        return False
    if rate_limits.get("limit_id") in {None, "codex"}:
        return False
    primary = limit_used_percent(rate_limits.get("primary"))
    secondary = limit_used_percent(rate_limits.get("secondary"))
    return primary == 0 and secondary == 0


def normalize_usage(raw):
    info = raw.get("info") or {}
    rate = raw.get("rate_limits") or {}
    total = info.get("total_token_usage") or {}
    last = info.get("last_token_usage") or {}
    context_window = info.get("model_context_window")
    total_tokens = total.get("total_tokens")
    context_percent = None
    if context_window and total_tokens and total_tokens <= context_window:
        context_percent = min(100, total_tokens / context_window * 100)
    return {
        "total_tokens": total_tokens,
        "last_turn_tokens": last.get("total_tokens"),
        "context_window": context_window,
        "context_percent": context_percent,
        "rate_limits": {
            "limit_id": rate.get("limit_id"),
            "plan_type": rate.get("plan_type"),
            "primary": normalize_limit(rate.get("primary")),
            "secondary": normalize_limit(rate.get("secondary")),
            "rate_limit_reached_type": rate.get("rate_limit_reached_type"),
        },
    }


def tailscale_ip():
    try:
        import subprocess

        out = subprocess.check_output(["ifconfig"], text=True, stderr=subprocess.DEVNULL, timeout=1)
    except Exception:
        return None
    for token in out.replace("\n", " ").split():
        if token.startswith("100.") and token.count(".") == 3:
            return token
    return None


def build_status():
    thread = query_current_thread() or {}
    rollout = parse_rollout(thread.get("rollout_path"))
    goal = query_goal(thread.get("id"))
    last_user = rollout.get("last_user_epoch")
    last_final = rollout.get("last_final_epoch")
    last_event = rollout.get("last_event_epoch") or thread.get("updated_epoch")
    if last_user and (not last_final or last_user > last_final):
        state = {"kind": "running", "label": "RUNNING"}
    elif last_final and (not last_user or last_final >= last_user):
        state = {"kind": "ready", "label": "READY"}
    elif last_event and time.time() - last_event < 45:
        state = {"kind": "running", "label": "LIVE"}
    else:
        state = {"kind": "ready", "label": "READY"}

    public_thread = {
        key: thread.get(key)
        for key in [
            "id",
            "title",
            "cwd",
            "model",
            "reasoning_effort",
            "tokens_used",
            "updated_relative",
            "preview",
            "sidebar_title",
        ]
    }
    public_thread["display_title"] = compact_title(
        (thread.get("sidebar_title"), True),
        (thread.get("title"), False),
        (rollout.get("latest_user_message"), True),
        (thread.get("preview"), True),
    )
    return {
        "server": f"Codex Status on :{PORT}",
        "workspace": str(WORKSPACE),
        "tailscale_ip": tailscale_ip(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "account": query_active_account(),
        "thread": public_thread,
        "goal": goal,
        "latest_user_message": rollout.get("latest_user_message"),
        "latest_assistant_message": rollout.get("latest_assistant_message"),
        "usage": rollout.get("usage") or {},
        "activity": rollout.get("activity") or [],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}")

    def send_headers(self, content_type, status=200, content_length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))
        self.end_headers()

    def send_bytes(self, body, content_type, status=200):
        self.send_headers(content_type, status=status, content_length=len(body))
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_bytes(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/status":
            try:
                body = json.dumps(build_status(), ensure_ascii=False).encode("utf-8")
                self.send_bytes(body, "application/json; charset=utf-8")
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_bytes(body, "application/json; charset=utf-8", status=500)
            return
        self.send_bytes(b"Not found", "text/plain; charset=utf-8", status=404)

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_headers("text/html; charset=utf-8", content_length=len(body))
            return
        if path == "/api/status":
            try:
                body = json.dumps(build_status(), ensure_ascii=False).encode("utf-8")
                self.send_headers("application/json; charset=utf-8", content_length=len(body))
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_headers(
                    "application/json; charset=utf-8",
                    status=500,
                    content_length=len(body),
                )
            return
        self.send_headers("text/plain; charset=utf-8", status=404, content_length=9)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Codex status server: http://0.0.0.0:{PORT}/")
    print(f"Workspace: {WORKSPACE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
