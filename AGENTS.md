# Codex Deployment Guide For This Repository

You are helping a user deploy Anything Codex Status on their Mac.

## Primary Goal

Get a local dashboard running safely so the user can open it from a phone or lightweight display over localhost, LAN, or Tailscale.

## Start Here

1. Read `README.md` and `docs/CODEX_INSTALL.md`.
2. Confirm this is the user's intent: a private local dashboard that may show account email, workspace paths, task titles, prompt snippets, and quota information.
3. Prefer a temporary server first. Do not install a persistent LaunchAgent until the user explicitly approves persistence after seeing the privacy warning.
4. Use `CODEX_STATUS_WORKSPACE` to point at the workspace the user wants monitored.
5. Verify `http://127.0.0.1:8765/api/status` before giving the phone URL.

## Useful Commands

Run temporary server:

```bash
CODEX_STATUS_WORKSPACE="/path/to/workspace" CODEX_STATUS_PORT=8765 python3 -m anything_codex_status.server
```

Check API:

```bash
curl http://127.0.0.1:8765/api/status
```

Find Tailscale IP:

```bash
ifconfig | grep '100\.'
```

Install persistent LaunchAgent only with explicit user approval:

```bash
python3 scripts/install_launch_agent.py --workspace "/path/to/workspace" --port 8765 --load
```

## Safety Rules

- Do not expose this dashboard through public tunnels unless the user explicitly understands it is unauthenticated.
- Do not read or print `~/.codex/auth.json` token contents.
- It is okay to read `~/.codex/accounts/registry.json` for account summary fields.
- It is okay to read `state_5.sqlite`, `goals_1.sqlite`, `session_index.jsonl`, and rollout JSONL files for status display.
- Browser polling of `/api/status` does not consume model tokens; it only reads local files.
- If port `8765` is occupied, identify the process and ask before stopping anything you did not start.

## Verification

Run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/anything-codex-status-pycache python3 -m unittest discover -s tests
```

Then verify:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
curl http://127.0.0.1:8765/api/status
```
