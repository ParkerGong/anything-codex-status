import json
import tempfile
import unittest
from pathlib import Path

from anything_codex_status import server


class ServerHelpersTest(unittest.TestCase):
    def test_compact_title_prefers_short_database_title(self):
        title = server.compact_title(
            ("Short task", False),
            ("This fallback is much longer and should not be used.", True),
        )

        self.assertEqual(title, "Short task")

    def test_parse_rollout_deduplicates_activity_and_extracts_usage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rollout = Path(tmpdir) / "rollout.jsonl"
            rows = [
                {
                    "timestamp": "2026-05-28T01:00:00Z",
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Build the status screen"},
                },
                {
                    "timestamp": "2026-05-28T01:00:01Z",
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": "Working", "phase": "update"},
                },
                {
                    "timestamp": "2026-05-28T01:00:02Z",
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": "Working", "phase": "update"},
                },
                {
                    "timestamp": "2026-05-28T01:00:03Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 1000},
                            "last_token_usage": {"total_tokens": 120},
                            "model_context_window": 2000,
                        },
                        "rate_limits": {
                            "limit_id": "codex",
                            "plan_type": "plus",
                            "primary": {"used_percent": 42, "window_minutes": 300},
                            "secondary": {"used_percent": 7, "window_minutes": 10080},
                        },
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            parsed = server.parse_rollout(rollout)

        self.assertEqual(parsed["latest_user_message"], "Build the status screen")
        self.assertEqual(parsed["usage"]["total_tokens"], 1000)
        self.assertEqual(parsed["usage"]["last_turn_tokens"], 120)
        self.assertEqual(parsed["usage"]["context_percent"], 50)
        self.assertEqual(parsed["usage"]["rate_limits"]["primary"]["used_percent"], 42)
        repeated_activity = [
            line for line in parsed["activity"] if line.endswith("CODEX Working")
        ]
        self.assertEqual(len(repeated_activity), 1)

    def test_skill_server_copy_matches_package_server(self):
        root = Path(__file__).resolve().parents[1]
        package_server = root / "anything_codex_status" / "server.py"
        skill_server = (
            root
            / "codex-skill"
            / "anything-codex-status"
            / "scripts"
            / "codex_status_server.py"
        )

        self.assertEqual(package_server.read_text(), skill_server.read_text())


if __name__ == "__main__":
    unittest.main()
