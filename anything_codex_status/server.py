#!/usr/bin/env python3
import json
import os
import sqlite3
import struct
import time
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None


PORT = int(os.environ.get("CODEX_STATUS_PORT", "8765"))
HOST = os.environ.get("CODEX_STATUS_HOST", "0.0.0.0")
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
WORKSPACE_ENV = os.environ.get("CODEX_STATUS_WORKSPACE")
WORKSPACE = Path(WORKSPACE_ENV).expanduser().resolve() if WORKSPACE_ENV else Path.cwd().resolve()
STATE_DB = CODEX_HOME / "state_5.sqlite"
GOALS_DB = CODEX_HOME / "goals_1.sqlite"
ACCOUNTS_REGISTRY = CODEX_HOME / "accounts" / "registry.json"
SESSION_INDEX = CODEX_HOME / "session_index.jsonl"
PETS_DIR = CODEX_HOME / "pets"
CODEX_CONFIG = CODEX_HOME / "config.toml"
CODEX_GLOBAL_STATE = CODEX_HOME / ".codex-global-state.json"
CODEX_APP = Path(os.environ.get("CODEX_STATUS_CODEX_APP", "/Applications/Codex.app"))
CODEX_APP_ASAR = CODEX_APP / "Contents" / "Resources" / "app.asar"
PET_FRAME_WIDTH = 192
PET_FRAME_HEIGHT = 208
PET_FRAMES_PER_ROW = 8
PET_STATES = [
    "idle",
    "running-right",
    "running-left",
    "waving",
    "jumping",
    "failed",
    "waiting",
    "running",
    "review",
]
FINAL_PHASES = {"final", "final_answer"}
OFFICIAL_PET_ASSETS = [
    {
        "id": "codex",
        "asset_ref": "codex",
        "display_name": "Codex",
        "description": "The original Codex companion.",
        "spritesheet_path": "webview/assets/codex-spritesheet-v4-Bl6P89d_.webp",
    },
    {
        "id": "dewey",
        "asset_ref": "dewey",
        "display_name": "Dewey",
        "description": "A tidy duck for calm workspace days.",
        "spritesheet_path": "webview/assets/dewey-spritesheet-v4-gAYk_M9g.webp",
    },
    {
        "id": "fireball",
        "asset_ref": "fireball",
        "display_name": "Fireball",
        "description": "Hot path energy for fast iteration.",
        "spritesheet_path": "webview/assets/fireball-spritesheet-v4-BtU8R9Qp.webp",
    },
    {
        "id": "rocky",
        "asset_ref": "rocky",
        "display_name": "Rocky",
        "description": "A steady rock when the diff gets large.",
        "spritesheet_path": "webview/assets/rocky-spritesheet-v4-3RlTi26B.webp",
    },
    {
        "id": "seedy",
        "asset_ref": "seedy",
        "display_name": "Seedy",
        "description": "Small green shoots for new ideas.",
        "spritesheet_path": "webview/assets/seedy-spritesheet-v4-CdlE_fn9.webp",
    },
    {
        "id": "stacky",
        "asset_ref": "stacky",
        "display_name": "Stacky",
        "description": "A balanced stack for deep work.",
        "spritesheet_path": "webview/assets/stacky-spritesheet-v4-CaUJd4fY.webp",
    },
    {
        "id": "bsod",
        "asset_ref": "bsod",
        "display_name": "BSOD",
        "description": "A compact blue-screen companion.",
        "spritesheet_path": "webview/assets/bsod-spritesheet-v4-BRrRVy1T.webp",
    },
    {
        "id": "null-signal",
        "asset_ref": "null-signal",
        "display_name": "Null Signal",
        "description": "Quiet signal from the void.",
        "spritesheet_path": "webview/assets/null-signal-spritesheet-v4-CCoTR-8t.webp",
    },
]
OFFICIAL_PET_ASSETS_BY_ID = {item["id"]: item for item in OFFICIAL_PET_ASSETS}


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

    .pet-dock {
      position: fixed;
      right: max(12px, env(safe-area-inset-right));
      bottom: max(10px, env(safe-area-inset-bottom));
      z-index: 20;
      display: flex;
      align-items: flex-end;
      justify-content: flex-end;
      gap: 9px;
      max-width: min(430px, calc(100vw - 24px));
      pointer-events: none;
    }

    .pet-dock[hidden] { display: none; }

    .pet-bubble {
      position: relative;
      width: min(260px, calc(100vw - 154px));
      margin-bottom: 24px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: var(--shadow);
      color: var(--ink);
    }

    .pet-bubble::after {
      content: "";
      position: absolute;
      width: 12px;
      height: 12px;
      right: -7px;
      bottom: 18px;
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      transform: rotate(-45deg);
    }

    .pet-bubble-top {
      display: flex;
      align-items: center;
      gap: 7px;
      min-width: 0;
      font-size: 12px;
      font-weight: 820;
    }

    .pet-spinner {
      width: 12px;
      height: 12px;
      flex: 0 0 auto;
      border: 2px solid var(--ok);
      border-radius: 50%;
      animation: none;
    }

    .pet-spinner.busy {
      border-color: rgba(13, 141, 125, 0.22);
      border-top-color: var(--accent);
      animation: pet-spin 840ms linear infinite;
    }

    .pet-spinner.failed {
      border-color: var(--bad);
    }

    .pet-bubble-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .pet-bubble-text {
      margin-top: 5px;
      color: #303937;
      font-size: 12px;
      line-height: 1.32;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      overflow-wrap: anywhere;
    }

    .pet-stage {
      --pet-scale: 0.58;
      width: calc(192px * var(--pet-scale));
      height: calc(208px * var(--pet-scale));
      overflow: hidden;
      flex: 0 0 auto;
      filter: drop-shadow(0 12px 18px rgba(23, 27, 29, 0.22));
    }

    .pet-sprite {
      width: 192px;
      height: 208px;
      background-repeat: no-repeat;
      background-size: 1536px 1872px;
      image-rendering: auto;
      transform: scale(var(--pet-scale));
      transform-origin: top left;
    }

    @keyframes pet-spin {
      to { transform: rotate(360deg); }
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
      .pet-dock { max-width: 330px; }
      .pet-bubble { width: min(210px, calc(100vw - 138px)); margin-bottom: 16px; }
      .pet-stage { --pet-scale: 0.48; }
    }

    @media (min-width: 760px) {
      .shell { padding: 24px; }
      .grid { grid-template-columns: 1.1fr 0.9fr; }
      .headline { font-size: 28px; }
      .pet-stage { --pet-scale: 0.68; }
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
        <label class="switch" title="Show pet">
          <input type="checkbox" id="showPetToggle" checked>
          <span class="switch-track"><span class="switch-thumb"></span></span>
          <span>Pet</span>
        </label>
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

    <div class="pet-dock" id="petDock" hidden>
      <div class="pet-bubble" id="petBubble">
        <div class="pet-bubble-top">
          <span class="pet-spinner" id="petSpinner"></span>
          <span class="pet-bubble-title" id="petBubbleTitle">SYNC</span>
        </div>
        <div class="pet-bubble-text" id="petBubbleText">Loading pet...</div>
      </div>
      <div class="pet-stage" aria-hidden="true">
        <div class="pet-sprite" id="petSprite"></div>
      </div>
    </div>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    const fmt = new Intl.NumberFormat("en-US");
    const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
    const taskToggle = $("showTaskToggle");
    const petToggle = $("showPetToggle");
    const petRows = {
      idle: 0,
      "running-right": 1,
      "running-left": 2,
      waving: 3,
      jumping: 4,
      failed: 5,
      waiting: 6,
      running: 7,
      review: 8,
    };
    const pet = {
      id: null,
      ready: false,
      loading: false,
      frame: 0,
      row: petRows.idle,
      state: "idle",
      timer: null,
      frameWidth: 192,
      frameHeight: 208,
      framesPerRow: 8,
      frameCounts: Array(9).fill(8),
      spritesheetUrl: null,
      imageLoaded: false,
      imageRetry: 0,
      lastPetCheck: 0,
    };
    let lastStatusData = null;

    function applyTaskVisibility(showTask, persist = true) {
      document.body.classList.toggle("compact-mode", !showTask);
      taskToggle.checked = showTask;
      if (persist) {
        localStorage.setItem("codex-status-show-task", showTask ? "1" : "0");
      }
      if (lastStatusData) updatePet(lastStatusData);
    }

    function applyPetVisibility(showPet, persist = true) {
      petToggle.checked = showPet;
      $("petDock").hidden = !showPet || !pet.ready;
      if (persist) {
        localStorage.setItem("codex-status-show-pet", showPet ? "1" : "0");
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

    function drawPetFrame() {
      const count = currentPetFrameCount();
      if (pet.frame >= count) pet.frame = 0;
      $("petSprite").style.backgroundPosition =
        `${pet.frame * -pet.frameWidth}px ${pet.row * -pet.frameHeight}px`;
    }

    function currentPetFrameCount() {
      return Math.max(1, pet.frameCounts[pet.row] || pet.framesPerRow || 1);
    }

    function startPetAnimation() {
      if (pet.timer) return;
      pet.timer = setInterval(() => {
        pet.frame = (pet.frame + 1) % currentPetFrameCount();
        drawPetFrame();
      }, 130);
    }

    function loadImage(url) {
      return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = reject;
        image.src = url;
      });
    }

    function cacheBustedPetUrl(url) {
      const separator = url.includes("?") ? "&" : "?";
      return `${url}${separator}r=${Date.now()}`;
    }

    function setPetBackground(url, retry = false) {
      const displayUrl = retry ? cacheBustedPetUrl(url) : url;
      $("petSprite").style.backgroundImage = `url("${displayUrl}")`;
      loadImage(displayUrl)
        .then((image) => {
          if (pet.spritesheetUrl !== url) return;
          pet.imageLoaded = true;
          pet.frameCounts = detectPetFrameCounts(image);
          drawPetFrame();
        })
        .catch(() => {
          if (pet.spritesheetUrl !== url) return;
          pet.imageLoaded = false;
        });
    }

    function detectPetFrameCounts(image) {
      const rows = Math.max(1, Math.floor(image.naturalHeight / pet.frameHeight));
      const cols = Math.max(1, Math.floor(image.naturalWidth / pet.frameWidth));
      const fallback = Array(rows).fill(cols);
      try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        if (!ctx) return fallback;
        ctx.drawImage(image, 0, 0);
        return Array.from({ length: rows }, (_, row) => {
          for (let col = cols - 1; col >= 0; col -= 1) {
            const pixels = ctx.getImageData(
              col * pet.frameWidth,
              row * pet.frameHeight,
              pet.frameWidth,
              pet.frameHeight
            ).data;
            for (let offset = 3; offset < pixels.length; offset += 4) {
              if (pixels[offset] > 8) return col + 1;
            }
          }
          return 1;
        });
      } catch (error) {
        return fallback;
      }
    }

    async function loadPets(force = false) {
      if (pet.loading) return;
      pet.loading = true;
      pet.lastPetCheck = Date.now();
      try {
        const res = await fetch("/api/pets", { cache: "no-store" });
        const data = await res.json();
        const selected = (data.pets || []).find((item) => item.id === data.selected) || data.pets?.[0];
        if (!selected?.spritesheet_url) {
          pet.ready = false;
          $("petDock").hidden = true;
          return;
        }
        if (
          !force &&
          pet.id === selected.id &&
          pet.spritesheetUrl === selected.spritesheet_url
        ) {
          if (!pet.imageLoaded && pet.imageRetry < 3) {
            pet.imageRetry += 1;
            setPetBackground(selected.spritesheet_url, true);
          }
          return;
        }
        pet.frameWidth = selected.frame_width || 192;
        pet.frameHeight = selected.frame_height || 208;
        pet.framesPerRow = selected.frames_per_row || 8;
        pet.id = selected.id;
        pet.spritesheetUrl = selected.spritesheet_url;
        pet.imageLoaded = false;
        pet.imageRetry = 0;
        pet.frameCounts = Array(9).fill(pet.framesPerRow || 8);
        pet.ready = true;
        pet.frame = 0;
        pet.row = petRows[pet.state] ?? petRows.idle;
        setPetBackground(selected.spritesheet_url);
        drawPetFrame();
        startPetAnimation();
        applyPetVisibility(localStorage.getItem("codex-status-show-pet") !== "0", false);
        if (lastStatusData) updatePet(lastStatusData);
      } catch (error) {
        if (!pet.ready) {
          $("petDock").hidden = true;
        }
      } finally {
        pet.loading = false;
      }
    }

    function maybeRefreshPets() {
      if (Date.now() - pet.lastPetCheck > 10000) {
        loadPets();
      }
    }

    function statusToPetState(data) {
      const state = data?.state || {};
      if (state.kind === "failed" || state.label === "OFFLINE") return "failed";
      if (state.kind === "running" || state.label === "LIVE") return "running";
      if (state.kind === "ready" || state.label === "READY") return "idle";
      const activity = data?.activity || [];
      const latest = activity.length ? activity[activity.length - 1] : "";
      if (latest.includes("TOOL start")) return "running";
      if (latest.includes("USER ")) return "review";
      return "idle";
    }

    function petSpinnerClass(data, nextState) {
      const state = data?.state || {};
      if (nextState === "failed") return "pet-spinner failed";
      if (state.kind === "running" || state.label === "LIVE" || nextState === "running") {
        return "pet-spinner busy";
      }
      return "pet-spinner idle";
    }

    function latestActivityText(data) {
      if (!taskToggle.checked) return "";
      const activity = data?.activity || [];
      const latest = activity.length ? activity[activity.length - 1] : "";
      return latest || data?.latest_user_message || data?.thread?.display_title || "";
    }

    function updatePet(data) {
      lastStatusData = data;
      if (!pet.ready) return;
      const nextState = statusToPetState(data);
      const previousRow = pet.row;
      const previousState = pet.state;
      pet.state = nextState;
      pet.row = petRows[nextState] ?? petRows.idle;
      if (previousState !== nextState || previousRow !== pet.row || pet.frame >= currentPetFrameCount()) {
        pet.frame = 0;
      }
      drawPetFrame();

      const stateLabel = data?.state?.label || "SYNC";
      const title = data?.thread?.display_title || "Codex Status";
      $("petSpinner").className = petSpinnerClass(data, nextState);
      $("petBubbleTitle").textContent = taskToggle.checked ? `${stateLabel} · ${title}` : stateLabel;
      $("petBubbleText").textContent = latestActivityText(data);
      $("petBubble").hidden = !taskToggle.checked;
      applyPetVisibility(petToggle.checked, false);
    }

    async function refresh() {
      try {
        const res = await fetch("/api/status", { cache: "no-store" });
        const data = await res.json();
        lastStatusData = data;
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
        updatePet(data);
        maybeRefreshPets();
      } catch (error) {
        $("stateText").textContent = "OFFLINE";
        $("dot").className = "dot";
        $("activity").textContent = error.message;
        updatePet({
          state: { kind: "failed", label: "OFFLINE" },
          thread: { display_title: "Codex Status" },
          activity: [error.message],
        });
      }
    }

    taskToggle.addEventListener("change", () => applyTaskVisibility(taskToggle.checked));
    petToggle.addEventListener("change", () => applyPetVisibility(petToggle.checked));
    applyTaskVisibility(localStorage.getItem("codex-status-show-task") !== "0", false);
    applyPetVisibility(localStorage.getItem("codex-status-show-pet") !== "0", false);
    loadPets();
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
              AND archived = 0
              AND COALESCE(thread_source, '') != 'subagent'
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
                WHERE archived = 0
                  AND COALESCE(thread_source, '') != 'subagent'
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


def quote_pet_id(pet_id):
    return quote(pet_id, safe="")


def resolve_pet_dir(pet_id):
    if isinstance(pet_id, str) and pet_id.startswith("custom:"):
        pet_id = pet_id.split(":", 1)[1]
    if not pet_id or pet_id in {".", ".."} or "/" in pet_id or "\\" in pet_id:
        return None
    try:
        root = PETS_DIR.resolve()
        candidate = (PETS_DIR / pet_id).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate if candidate.is_dir() else None


def load_pet_manifest(pet_dir):
    manifest_path = pet_dir / "pet.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return manifest if isinstance(manifest, dict) else None


def resolve_pet_spritesheet(pet_dir, manifest):
    spritesheet = manifest.get("spritesheetPath")
    if not spritesheet or Path(str(spritesheet)).is_absolute():
        return None
    try:
        root = pet_dir.resolve()
        image_path = (pet_dir / str(spritesheet)).resolve()
        image_path.relative_to(root)
    except (OSError, ValueError):
        return None
    return image_path if image_path.is_file() else None


def pet_state_map():
    return {name: index for index, name in enumerate(PET_STATES)}


def public_pet_package(pet_dir):
    manifest = load_pet_manifest(pet_dir)
    if not manifest:
        return None
    spritesheet = resolve_pet_spritesheet(pet_dir, manifest)
    if not spritesheet:
        return None
    pet_id = f"custom:{pet_dir.name}"
    return {
        "id": pet_id,
        "asset_ref": "codex",
        "source": "custom",
        "local_id": pet_dir.name,
        "display_name": manifest.get("displayName") or manifest.get("display_name") or pet_id,
        "description": manifest.get("description"),
        "kind": manifest.get("kind"),
        "spritesheet_url": f"/pets/{quote_pet_id(pet_id)}/spritesheet.webp",
        "frame_width": PET_FRAME_WIDTH,
        "frame_height": PET_FRAME_HEIGHT,
        "frames_per_row": PET_FRAMES_PER_ROW,
        "states": pet_state_map(),
    }


@lru_cache(maxsize=4)
def load_asar_header(asar_path):
    path = Path(asar_path)
    with path.open("rb") as handle:
        raw_header = handle.read(16)
        if len(raw_header) != 16:
            return None
        _, packed_size, _, header_size = struct.unpack("<IIII", raw_header)
        header_bytes = handle.read(header_size)
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return {"base_offset": 8 + packed_size, "header": header}


def asar_entry(header, relative_path):
    node = header
    for part in relative_path.split("/"):
        files = node.get("files") if isinstance(node, dict) else None
        if not isinstance(files, dict) or part not in files:
            return None
        node = files[part]
    return node if isinstance(node, dict) else None


def iter_asar_file_paths(node, prefix=""):
    files = node.get("files") if isinstance(node, dict) else None
    if not isinstance(files, dict):
        return
    for name, child in sorted(files.items()):
        relative_path = f"{prefix}/{name}" if prefix else name
        child_files = child.get("files") if isinstance(child, dict) else None
        if isinstance(child_files, dict):
            yield from iter_asar_file_paths(child, relative_path)
        else:
            yield relative_path


def read_asar_file(asar_path, relative_path):
    try:
        archive = load_asar_header(str(asar_path))
        if not archive:
            return None
        entry = asar_entry(archive["header"], relative_path)
        if not entry or entry.get("unpacked"):
            return None
        size = int(entry.get("size"))
        offset = int(entry.get("offset"))
        with Path(asar_path).open("rb") as handle:
            handle.seek(archive["base_offset"] + offset)
            return handle.read(size)
    except (OSError, TypeError, ValueError):
        return None


def asar_has_file(asar_path, relative_path):
    try:
        archive = load_asar_header(str(asar_path))
        return bool(archive and asar_entry(archive["header"], relative_path))
    except OSError:
        return False


@lru_cache(maxsize=8)
def official_spritesheet_paths(asar_path):
    archive = load_asar_header(str(asar_path))
    if not archive:
        return {}
    prefixes = {
        asset["id"]: f"{asset['id']}-spritesheet-"
        for asset in OFFICIAL_PET_ASSETS
    }
    found = {}
    for relative_path in iter_asar_file_paths(archive["header"]):
        if not relative_path.startswith("webview/assets/") or not relative_path.endswith(".webp"):
            continue
        filename = relative_path.rsplit("/", 1)[-1]
        for pet_id, prefix in prefixes.items():
            if filename.startswith(prefix):
                found.setdefault(pet_id, relative_path)
                break
    return found


def official_spritesheet_path(asset):
    explicit_path = asset.get("spritesheet_path")
    if explicit_path and asar_has_file(CODEX_APP_ASAR, explicit_path):
        return explicit_path
    return official_spritesheet_paths(str(CODEX_APP_ASAR)).get(asset["id"])


def official_pet_package(asset):
    if not official_spritesheet_path(asset):
        return None
    pet_id = asset["id"]
    return {
        "id": pet_id,
        "asset_ref": asset["asset_ref"],
        "source": "official",
        "display_name": asset["display_name"],
        "description": asset["description"],
        "kind": "official",
        "spritesheet_url": f"/pets/{quote_pet_id(pet_id)}/spritesheet.webp",
        "frame_width": PET_FRAME_WIDTH,
        "frame_height": PET_FRAME_HEIGHT,
        "frames_per_row": PET_FRAMES_PER_ROW,
        "states": pet_state_map(),
    }


def list_official_pet_packages():
    if not CODEX_APP_ASAR.is_file():
        return []
    packages = []
    for asset in OFFICIAL_PET_ASSETS:
        package = official_pet_package(asset)
        if package:
            packages.append(package)
    return packages


def list_custom_pet_packages():
    if not PETS_DIR.is_dir():
        return []
    packages = []
    try:
        pet_dirs = sorted(PETS_DIR.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []
    for pet_dir in pet_dirs:
        resolved = resolve_pet_dir(pet_dir.name)
        if not resolved:
            continue
        package = public_pet_package(resolved)
        if package:
            packages.append(package)
    return packages


def list_pet_packages():
    return list_official_pet_packages() + list_custom_pet_packages()


def parse_selected_avatar_id_toml_fallback(text):
    in_desktop = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_desktop = line.strip("[]").strip() == "desktop"
            continue
        if not in_desktop or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "selected-avatar-id":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            return value[1:-1]
        return value or None
    return None


def read_selected_avatar_id_from_config():
    if not CODEX_CONFIG.is_file():
        return None
    try:
        text = CODEX_CONFIG.read_text(encoding="utf-8")
    except OSError:
        return None
    if tomllib is None:
        return parse_selected_avatar_id_toml_fallback(text)
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return parse_selected_avatar_id_toml_fallback(text)
    value = (config.get("desktop") or {}).get("selected-avatar-id")
    return value if isinstance(value, str) and value else None


def read_selected_avatar_id_from_global_state():
    if not CODEX_GLOBAL_STATE.is_file():
        return None
    try:
        state = json.loads(CODEX_GLOBAL_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    atoms = state.get("electron-persisted-atom-state") or {}
    value = atoms.get("selected-avatar-id")
    return value if isinstance(value, str) and value else None


def query_selected_avatar_id():
    override = os.environ.get("CODEX_STATUS_PET_ID")
    if override:
        return override
    return read_selected_avatar_id_from_config() or read_selected_avatar_id_from_global_state()


def selected_pet_package_id(packages):
    if not packages:
        return None
    ids = {package["id"] for package in packages}
    selected = query_selected_avatar_id()
    candidates = []
    if selected:
        candidates.append(selected)
        if selected.startswith("custom:"):
            candidates.append(selected.split(":", 1)[1])
        else:
            candidates.append(f"custom:{selected}")
    candidates.extend(["codex", packages[0]["id"]])
    for candidate in candidates:
        if candidate in ids:
            return candidate
    return packages[0]["id"]


def read_pet_spritesheet(pet_id):
    official_asset = OFFICIAL_PET_ASSETS_BY_ID.get(pet_id)
    if official_asset:
        spritesheet_path = official_spritesheet_path(official_asset)
        if not spritesheet_path:
            return None
        return read_asar_file(CODEX_APP_ASAR, spritesheet_path)
    pet_dir = resolve_pet_dir(pet_id)
    if not pet_dir:
        return None
    manifest = load_pet_manifest(pet_dir)
    if not manifest:
        return None
    spritesheet = resolve_pet_spritesheet(pet_dir, manifest)
    if not spritesheet:
        return None
    try:
        return spritesheet.read_bytes()
    except OSError:
        return None


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
        "server": f"Codex Status on {HOST}:{PORT}",
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

    def send_headers(self, content_type, status=200, content_length=None, cache_control="no-store"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))
        self.end_headers()

    def send_bytes(self, body, content_type, status=200, cache_control="no-store"):
        self.send_headers(
            content_type,
            status=status,
            content_length=len(body),
            cache_control=cache_control,
        )
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

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
        if path == "/api/pets":
            pets = list_pet_packages()
            body = json.dumps(
                {"pets": pets, "selected": selected_pet_package_id(pets)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_bytes(body, "application/json; charset=utf-8")
            return
        parts = path.split("/")
        if len(parts) == 4 and parts[1] == "pets" and parts[3] == "spritesheet.webp":
            image = read_pet_spritesheet(unquote(parts[2]))
            if image is not None:
                self.send_bytes(image, "image/webp", cache_control="private, max-age=3600")
                return
            self.send_bytes(b"Not found", "text/plain; charset=utf-8", status=404)
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
        if path == "/api/pets":
            pets = list_pet_packages()
            body = json.dumps(
                {"pets": pets, "selected": selected_pet_package_id(pets)},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_headers("application/json; charset=utf-8", content_length=len(body))
            return
        parts = path.split("/")
        if len(parts) == 4 and parts[1] == "pets" and parts[3] == "spritesheet.webp":
            image = read_pet_spritesheet(unquote(parts[2]))
            if image is not None:
                self.send_headers(
                    "image/webp",
                    content_length=len(image),
                    cache_control="private, max-age=3600",
                )
                return
            self.send_headers("text/plain; charset=utf-8", status=404, content_length=9)
            return
        self.send_headers("text/plain; charset=utf-8", status=404, content_length=9)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Codex status server: http://{HOST}:{PORT}/")
    print(f"Workspace: {WORKSPACE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
