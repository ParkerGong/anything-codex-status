# Anything Codex Status

A small local web dashboard for monitoring the current Codex desktop task from a phone, Kindle browser, or other lightweight display.

It reads Codex's local state and rollout logs, then serves a responsive status page with:

- current task status
- short task title and latest user request
- model and reasoning effort
- thread/session token counters
- 5h quota and weekly quota when `token_count` events are available
- recent activity with duplicate rows collapsed
- Tailscale-friendly access from an iPhone or other device

## Requirements

- Python 3.9+
- Codex desktop local state under `~/.codex`
- macOS for the included LaunchAgent installer
- Tailscale or another private network if viewing from another device

## Quick Start

Run it from the project root:

```bash
python3 -m anything_codex_status.server
```

Then open the page locally:

```text
http://127.0.0.1:8765/
```

From an iPhone over Tailscale, open:

```text
http://<mac-tailscale-ip>:8765/
```

For a specific workspace:

```bash
CODEX_STATUS_WORKSPACE="/path/to/workspace" python3 -m anything_codex_status.server
```

Optional settings:

```bash
CODEX_STATUS_PORT=8765
CODEX_HOME="$HOME/.codex"
```

## Install From Source

```bash
python3 -m pip install -e .
anything-codex-status
```

The editable install exposes the `anything-codex-status` command while keeping local development changes live.

## Install as a macOS LaunchAgent

To keep the dashboard running after login:

```bash
python3 scripts/install_launch_agent.py \
  --workspace "/path/to/workspace" \
  --port 8765 \
  --load
```

Check status:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
curl http://127.0.0.1:8765/api/status
```

Remove the LaunchAgent:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/io.github.anything-codex-status.plist
rm ~/Library/LaunchAgents/io.github.anything-codex-status.plist
```

## Codex Skill

The `codex-skill/anything-codex-status` folder contains a reusable Codex skill for rebuilding, repairing, or reinstalling the dashboard.

To install it manually:

```bash
mkdir -p ~/.codex/skills/anything-codex-status
cp -R codex-skill/anything-codex-status/* ~/.codex/skills/anything-codex-status/
```

Then ask Codex:

```text
Use $anything-codex-status to start or repair my Codex phone status dashboard.
```

## Development

Run the local checks:

```bash
python3 -m py_compile server.py anything_codex_status/server.py scripts/install_launch_agent.py codex-skill/anything-codex-status/scripts/codex_status_server.py codex-skill/anything-codex-status/scripts/install_launch_agent.py
python3 -m unittest discover -s tests
```

## Privacy And Security

This project reads local Codex files from `~/.codex`. It does not send data to any external service. If you expose the page beyond your local machine, use a private network such as Tailscale and avoid public unauthenticated tunnels.

The dashboard may display local workspace paths, task titles, recent prompt snippets, and usage counters. Treat the page as private operational telemetry, not a public status page.
