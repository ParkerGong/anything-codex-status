# Codex-Assisted Install Manual

This manual is written for Codex or another local coding agent reading the repository on a user's Mac.

## 1. Explain The System

Tell the user:

- The dashboard is a local Python HTTP server.
- It binds to `0.0.0.0` so phones or tablets on the same Tailscale network can reach it.
- It reads local Codex state under `~/.codex`.
- If local Codex pet assets exist under `~/.codex/pets`, it can serve their declared `pet.json` / `spritesheet.webp` for the on-page pet status bubble.
- It does not call a model and does not consume Codex tokens.
- It is unauthenticated, so it should stay on localhost for local checks or Tailscale for remote display access.

## 2. Check Requirements

Run read-only checks:

```bash
python3 --version
test -d ~/.codex && echo "Codex state found"
test -f ~/.codex/state_5.sqlite && echo "state database found"
test -f ~/.codex/session_index.jsonl && echo "session index found"
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Confirm Tailscale is installed and signed in on both the Mac and the display device. Then find the Mac's Tailscale IP:

```bash
ifconfig | grep '100\.'
```

## 3. Choose Workspace

Ask or infer the workspace to monitor. Use the repository root only if the user wants to monitor this repository's Codex thread.

Set:

```bash
CODEX_STATUS_WORKSPACE="/absolute/path/to/workspace"
```

## 4. Run Checks

From the repository root:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/anything-codex-status-pycache \
python3 -m py_compile \
  server.py \
  anything_codex_status/server.py \
  scripts/install_launch_agent.py \
  codex-skill/anything-codex-status/scripts/codex_status_server.py \
  codex-skill/anything-codex-status/scripts/install_launch_agent.py \
  tests/test_server.py

PYTHONPYCACHEPREFIX=/private/tmp/anything-codex-status-pycache \
python3 -m unittest discover -s tests
```

## 5. Start Temporary Server

Start this first:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/anything-codex-status-pycache \
CODEX_STATUS_WORKSPACE="/absolute/path/to/workspace" \
CODEX_STATUS_PORT=8765 \
python3 -m anything_codex_status.server
```

For localhost-only development checks, add `CODEX_STATUS_HOST=127.0.0.1`. The default remains `0.0.0.0` for phone/tablet access over Tailscale.

Verify:

```bash
curl http://127.0.0.1:8765/api/status
curl http://127.0.0.1:8765/api/pets
```

Give the user:

```text
http://127.0.0.1:8765/
http://<mac-tailscale-ip>:8765/
```

## 6. Optional Persistent Deployment

Only proceed if the user explicitly approves persistence.

Explain that LaunchAgent keeps an unauthenticated dashboard running after login.

Install:

```bash
python3 scripts/install_launch_agent.py \
  --workspace "/absolute/path/to/workspace" \
  --port 8765 \
  --load
```

Verify:

```bash
launchctl print gui/$(id -u)/io.github.anything-codex-status
lsof -nP -iTCP:8765 -sTCP:LISTEN
curl http://127.0.0.1:8765/api/status
```

## 7. Optional Skill Installation

Install the bundled skill:

```bash
mkdir -p ~/.codex/skills/anything-codex-status
cp -R codex-skill/anything-codex-status/* ~/.codex/skills/anything-codex-status/
```

Then the user can ask:

```text
Use $anything-codex-status to start or repair my Codex phone status dashboard.
```

## Troubleshooting

If the phone/tablet cannot connect:

- Confirm the Mac and phone/tablet are both connected to Tailscale.
- Use the `100.x.y.z` address, not a campus Wi-Fi address.
- Confirm `lsof -nP -iTCP:8765 -sTCP:LISTEN` shows the server.
- Confirm macOS firewall or network settings are not blocking incoming connections.

If the wrong task appears:

- Set `CODEX_STATUS_WORKSPACE` to the intended workspace.
- Check `/api/status` and inspect `thread.cwd`, `thread.display_title`, and `workspace`.

If quota is unknown:

- The current rollout may not yet contain a `token_count` event.
- Continue a Codex task until Codex writes a new quota sample.
