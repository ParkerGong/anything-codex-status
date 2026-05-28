import json
import sqlite3
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

    def test_query_sidebar_title_uses_session_index_thread_name(self):
        old_index = server.SESSION_INDEX
        with tempfile.TemporaryDirectory() as tmpdir:
            index = Path(tmpdir) / "session_index.jsonl"
            rows = [
                {"id": "thread-1", "thread_name": "Old title"},
                {"id": "thread-2", "thread_name": "Other title"},
                {"id": "thread-1", "thread_name": "Sidebar title"},
            ]
            index.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            server.SESSION_INDEX = index
            try:
                title = server.query_sidebar_title("thread-1")
            finally:
                server.SESSION_INDEX = old_index

        self.assertEqual(title, "Sidebar title")

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

    def test_parse_rollout_treats_final_answer_and_task_complete_as_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rollout = Path(tmpdir) / "rollout.jsonl"
            rows = [
                {
                    "timestamp": "2026-05-28T01:00:00Z",
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Start temporary server"},
                },
                {
                    "timestamp": "2026-05-28T01:00:10Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": "Server is running",
                        "phase": "final_answer",
                    },
                },
                {
                    "timestamp": "2026-05-28T01:00:11Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "completed_at": 1779930011,
                        "last_agent_message": "Server is running",
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            parsed = server.parse_rollout(rollout)

        self.assertEqual(parsed["last_user_epoch"], 1779930000)
        self.assertEqual(parsed["last_final_epoch"], 1779930011)
        self.assertEqual(parsed["latest_assistant_message"], "Server is running")

    def test_parse_rollout_falls_back_from_zero_non_codex_quota_bucket(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rollout = Path(tmpdir) / "rollout.jsonl"
            rows = [
                {
                    "timestamp": "2026-05-28T01:00:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 1000},
                            "last_token_usage": {"total_tokens": 100},
                        },
                        "rate_limits": {
                            "limit_id": "codex",
                            "plan_type": "prolite",
                            "primary": {"used_percent": 22.0, "window_minutes": 300},
                            "secondary": {"used_percent": 18.0, "window_minutes": 10080},
                        },
                    },
                },
                {
                    "timestamp": "2026-05-28T01:01:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {"total_tokens": 2000},
                            "last_token_usage": {"total_tokens": 200},
                        },
                        "rate_limits": {
                            "limit_id": "codex_bengalfox",
                            "plan_type": "prolite",
                            "primary": {"used_percent": 0.0, "window_minutes": 300},
                            "secondary": {"used_percent": 0.0, "window_minutes": 10080},
                        },
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            parsed = server.parse_rollout(rollout)

        self.assertEqual(parsed["usage"]["total_tokens"], 2000)
        self.assertEqual(parsed["usage"]["last_turn_tokens"], 200)
        rate = parsed["usage"]["rate_limits"]
        self.assertEqual(rate["limit_id"], "codex")
        self.assertEqual(rate["fallback_from_limit_id"], "codex_bengalfox")
        self.assertEqual(rate["primary"]["used_percent"], 22.0)
        self.assertEqual(rate["secondary"]["used_percent"], 18.0)

    def test_query_current_thread_skips_subagent_threads(self):
        old_state_db = server.STATE_DB
        old_workspace = server.WORKSPACE
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            db = Path(tmpdir) / "state.sqlite"
            with sqlite3.connect(db) as con:
                con.execute(
                    """
                    CREATE TABLE threads (
                      id TEXT PRIMARY KEY,
                      title TEXT,
                      cwd TEXT,
                      model TEXT,
                      reasoning_effort TEXT,
                      tokens_used INTEGER,
                      updated_at_ms INTEGER,
                      updated_at INTEGER,
                      preview TEXT,
                      rollout_path TEXT,
                      archived INTEGER,
                      thread_source TEXT
                    )
                    """
                )
                con.execute(
                    """
                    INSERT INTO threads VALUES
                    ('user-thread', 'Real task', ?, 'gpt', 'high', 100, 1000, 1, 'User preview', '', 0, 'user'),
                    ('review-thread', 'The following is the Codex agent history', ?, 'gpt', 'low', 200, 2000, 2, 'Review preview', '', 0, 'subagent')
                    """,
                    (str(workspace), str(workspace)),
                )
            server.STATE_DB = db
            server.WORKSPACE = workspace
            try:
                thread = server.query_current_thread()
            finally:
                server.STATE_DB = old_state_db
                server.WORKSPACE = old_workspace

        self.assertEqual(thread["id"], "user-thread")
        self.assertEqual(thread["title"], "Real task")

    def test_query_active_account_returns_public_summary_only(self):
        old_registry = server.ACCOUNTS_REGISTRY
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "activeAccountKey": "acct-2",
                        "items": [
                            {"accountKey": "acct-1", "email": "old@example.com"},
                            {
                                "accountKey": "acct-2",
                                "email": "user@example.com",
                                "profileName": "User Name",
                                "accountName": "Personal",
                                "workspaceName": "Personal",
                                "plan": "plus",
                                "authMode": "chatgpt",
                                "hasActiveSubscription": True,
                                "snapshotPath": "/private/path/auth.json",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            server.ACCOUNTS_REGISTRY = registry
            try:
                account = server.query_active_account()
            finally:
                server.ACCOUNTS_REGISTRY = old_registry

        self.assertEqual(account["email"], "user@example.com")
        self.assertEqual(account["plan"], "plus")
        self.assertNotIn("snapshotPath", account)

    def test_list_pet_packages_returns_public_manifest(self):
        old_pets_dir = server.PETS_DIR
        with tempfile.TemporaryDirectory() as tmpdir:
            pets_dir = Path(tmpdir) / "pets"
            pet_dir = pets_dir / "duodong"
            pet_dir.mkdir(parents=True)
            (pet_dir / "spritesheet.webp").write_bytes(b"webp")
            (pet_dir / "pet.json").write_text(
                json.dumps(
                    {
                        "id": "ignored-manifest-id",
                        "displayName": "Duo Dong",
                        "description": "Local test pet",
                        "spritesheetPath": "spritesheet.webp",
                        "kind": "creature",
                        "privateField": "not returned",
                    }
                ),
                encoding="utf-8",
            )
            server.PETS_DIR = pets_dir
            try:
                pets = server.list_pet_packages()
                image = server.read_pet_spritesheet("duodong")
            finally:
                server.PETS_DIR = old_pets_dir

        self.assertEqual(len(pets), 1)
        self.assertEqual(pets[0]["id"], "duodong")
        self.assertEqual(pets[0]["display_name"], "Duo Dong")
        self.assertEqual(pets[0]["spritesheet_url"], "/pets/duodong/spritesheet.webp")
        self.assertEqual(pets[0]["states"]["running"], 7)
        self.assertNotIn("privateField", pets[0])
        self.assertEqual(image, b"webp")

    def test_pet_spritesheet_path_cannot_escape_pet_directory(self):
        old_pets_dir = server.PETS_DIR
        with tempfile.TemporaryDirectory() as tmpdir:
            pets_dir = Path(tmpdir) / "pets"
            pet_dir = pets_dir / "duodong"
            pet_dir.mkdir(parents=True)
            (pets_dir / "secret.webp").write_bytes(b"secret")
            (pet_dir / "pet.json").write_text(
                json.dumps({"displayName": "Bad pet", "spritesheetPath": "../secret.webp"}),
                encoding="utf-8",
            )
            server.PETS_DIR = pets_dir
            try:
                pets = server.list_pet_packages()
                image = server.read_pet_spritesheet("duodong")
                escaped = server.read_pet_spritesheet("../secret")
            finally:
                server.PETS_DIR = old_pets_dir

        self.assertEqual(pets, [])
        self.assertIsNone(image)
        self.assertIsNone(escaped)

    def test_dashboard_contains_task_visibility_toggle(self):
        html = server.INDEX_HTML

        self.assertIn('id="showTaskToggle"', html)
        self.assertIn('id="showPetToggle"', html)
        self.assertIn('id="petDock"', html)
        self.assertIn("compact-mode", html)
        self.assertIn("codex-status-show-task", html)
        self.assertIn("codex-status-show-pet", html)
        self.assertIn('fetch("/api/pets"', html)
        self.assertIn("function detectPetFrameCounts", html)
        self.assertIn("statusToPetState", html)
        self.assertIn('state.kind === "ready"', html)
        self.assertIn(".pet-spinner.busy", html)
        self.assertIn('id="account"', html)
        self.assertIn('id="accountPlan"', html)
        self.assertIn("function displayPlan", html)
        self.assertIn('plan.startsWith("pro")', html)

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
