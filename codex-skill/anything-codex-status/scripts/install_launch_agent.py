#!/usr/bin/env python3
import argparse
import os
import plistlib
import subprocess
from pathlib import Path


LABEL = "io.github.anything-codex-status"


def main():
    parser = argparse.ArgumentParser(description="Install the Codex status display LaunchAgent.")
    parser.add_argument("--workspace", required=True, help="Workspace whose Codex thread should be monitored.")
    parser.add_argument("--port", default="8765", help="HTTP port to serve.")
    parser.add_argument(
        "--server-script",
        default=str(Path(__file__).with_name("codex_status_server.py")),
        help="Path to codex_status_server.py.",
    )
    parser.add_argument("--python", default="/usr/bin/python3", help="Python executable to run.")
    parser.add_argument("--load", action="store_true", help="Load/restart the LaunchAgent now.")
    args = parser.parse_args()

    home = Path.home()
    launch_agents = home / "Library" / "LaunchAgents"
    log_dir = home / ".codex" / "log"
    launch_agents.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_path = launch_agents / f"{LABEL}.plist"
    plist = {
        "Label": LABEL,
        "ProgramArguments": [args.python, str(Path(args.server_script).expanduser().resolve())],
        "WorkingDirectory": str(Path(args.workspace).expanduser().resolve()),
        "EnvironmentVariables": {
            "CODEX_STATUS_WORKSPACE": str(Path(args.workspace).expanduser().resolve()),
            "CODEX_STATUS_PORT": str(args.port),
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
        subprocess.run(["launchctl", "enable", f"gui/{uid}/{LABEL}"], check=False)
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"], check=False)

    print(plist_path)


if __name__ == "__main__":
    main()
