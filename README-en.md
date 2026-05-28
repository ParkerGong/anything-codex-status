# Anything Codex Status

Turn an idle phone or tablet that can install and sign in to Tailscale into a private Codex status screen.

The main README is written in Chinese first: [简体中文](README.md).

## External Requirement

Remote display access depends on Tailscale. The Mac running Codex and the phone/tablet used as the status screen must be in the same tailnet. Tailscale's open-source repository is [tailscale/tailscale](https://github.com/tailscale/tailscale).

## What It Does

- Shows active Codex account and plan.
- Shows 5h and weekly quota windows.
- Uses the Codex sidebar-style short title for the current task.
- Shows recent request and activity.
- Provides a `Task` switch for an account-and-quota-only view.
- Uses Tailscale for phone/tablet dashboards.

## Recommended Install Flow

Give this repository to Codex on the target Mac and ask:

```text
Read this repository and help me deploy Anything Codex Status.
Start a temporary server first, verify /api/status, then give me the localhost and Tailscale URLs.
Only install a persistent LaunchAgent after I explicitly approve it.
```

## Manual Quick Start

```bash
git clone https://github.com/ParkerGong/anything-codex-status.git
cd anything-codex-status
CODEX_STATUS_WORKSPACE="/path/to/workspace" CODEX_STATUS_PORT=8765 python3 -m anything_codex_status.server
```

Open:

```text
http://127.0.0.1:8765/
http://<mac-tailscale-ip>:8765/
```

## Security

The dashboard is unauthenticated and may display account email, local paths, task titles, prompt snippets, and quota information. Use localhost for local checks or Tailscale for remote display access. Browser refreshes read local files and do not consume Codex tokens.
