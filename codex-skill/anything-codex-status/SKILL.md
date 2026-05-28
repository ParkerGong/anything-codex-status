---
name: anything-codex-status
description: Build, start, repair, or persist a phone-friendly Codex status dashboard served from the Mac over Tailscale. Use when the user asks to monitor current Codex task status, 5h quota, weekly quota, recent activity, iPhone/iPad/Android tablet status display, Tailscale status screen, or LaunchAgent persistence for the Codex status web page.
---

# Anything Codex Status

## Quick Start

Use `scripts/codex_status_server.py` as the canonical server. It serves:

- `/` phone-friendly HTML dashboard
- `/api/status` JSON status payload

Default behavior:

- Binds to `0.0.0.0:${CODEX_STATUS_PORT:-8765}`.
- Monitors `CODEX_STATUS_WORKSPACE` when set, otherwise the process working directory.
- Reads Codex state from `${CODEX_HOME:-~/.codex}/state_5.sqlite`, `goals_1.sqlite`, and the selected thread rollout JSONL.
- Extracts real `5h` and weekly quota from rollout `token_count` events when available.
- Requires Tailscale for remote display access; use the Mac `100.x.y.z` address on the phone or tablet.

Start manually:

```bash
CODEX_STATUS_WORKSPACE="/path/to/workspace" python3 scripts/codex_status_server.py
```

Then open:

```text
http://<mac-tailscale-ip>:8765/
```

## Workflow

1. Confirm Tailscale is installed and signed in on both the Mac and the display device.
2. Start or restart `codex_status_server.py` on port `8765`.
3. Visit `/api/status` locally with `curl` and verify `thread`, `usage.rate_limits.primary`, and `usage.rate_limits.secondary`.
4. Open the Tailscale URL on the phone/tablet browser and optionally add it to the home screen.
5. For persistence, install a LaunchAgent with `scripts/install_launch_agent.py`.

## Persistence

Use the installer script to create `~/Library/LaunchAgents/io.github.anything-codex-status.plist`:

```bash
python3 scripts/install_launch_agent.py \
  --workspace "/path/to/workspace" \
  --server-script "/absolute/path/to/scripts/codex_status_server.py" \
  --port 8765 \
  --load
```

If port `8765` is already occupied by a manually started server, stop it before loading the LaunchAgent.

Useful checks:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
launchctl print gui/$(id -u)/io.github.anything-codex-status
tail -n 50 ~/.codex/log/anything-codex-status.err.log
```

## Display Rules

- The dashboard shows the most recently updated Codex thread in the monitored workspace.
- If no thread exists for the monitored workspace, it falls back to the globally most recently updated thread.
- The large Current Task heading should use `thread.display_title`, not the raw database title, because raw titles may contain long first prompts.
- Prefer the sidebar-style `thread_name` from `${CODEX_HOME:-~/.codex}/session_index.jsonl` when deriving `thread.display_title`.
- Recent Activity should deduplicate duplicate `event_msg`/`response_item` records and keep the latest unique activity lines.
- The Task switch should persist in browser `localStorage`; when off, the page should only show active account, plan, 5h quota, and weekly quota information.
- Treat missing quota data as unknown; do not fabricate usage numbers.

## Common Fixes

- If the phone/tablet cannot open the page, confirm Tailscale is connected and open `http://100.x.y.z:8765/`.
- If `/api/status` works but the page looks stale, refresh Safari or restart the LaunchAgent.
- If the service shows the wrong task, set `CODEX_STATUS_WORKSPACE` to the intended workspace or lock the selection logic to a specific thread id.
- If the service cannot bind to the port, find the old process with `lsof -nP -iTCP:8765 -sTCP:LISTEN` and stop that process before restarting.
