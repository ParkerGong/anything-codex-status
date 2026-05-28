#!/usr/bin/env python3
import argparse
import os
import plistlib
import subprocess
from pathlib import Path


DEFAULT_LABEL = "io.github.anything-codex-status"


def main():
    parser = argparse.ArgumentParser(description="Install the Codex status display LaunchAgent.")
    parser.add_argument("--workspace", required=True, help="Workspace whose Codex thread should be monitored.")
    parser.add_argument("--port", default="8765", help="HTTP port to serve.")
    parser.add_argument("--python", default="/usr/bin/python3", help="Python executable to run.")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="LaunchAgent label.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Project root containing the anything_codex_status package.",
    )
    parser.add_argument("--load", action="store_true", help="Load/restart the LaunchAgent now.")
    args = parser.parse_args()

    home = Path.home()
    project_root = Path(args.project_root).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    launch_agents = home / "Library" / "LaunchAgents"
    log_dir = home / ".codex" / "log"
    launch_agents.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_path = launch_agents / f"{args.label}.plist"
    plist = {
        "Label": args.label,
        "ProgramArguments": [args.python, "-m", "anything_codex_status.server"],
        "WorkingDirectory": str(project_root),
        "EnvironmentVariables": {
            "CODEX_STATUS_WORKSPACE": str(workspace),
            "CODEX_STATUS_PORT": str(args.port),
            "PYTHONPATH": str(project_root),
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_dir / "anything-codex-status.out.log"),
        "StandardErrorPath": str(log_dir / "anything-codex-status.err.log"),
    }
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)

    if args.load:
        uid = os.getuid()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)], check=False)
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
        subprocess.run(["launchctl", "enable", f"gui/{uid}/{args.label}"], check=False)
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{args.label}"], check=False)

    print(plist_path)


if __name__ == "__main__":
    main()
