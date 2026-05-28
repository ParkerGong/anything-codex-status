import json
import os
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from anything_codex_status import server


class ServerHelpersTest(unittest.TestCase):
    def write_fake_asar(self, path, entries):
        header = {"files": {}}
        offset = 0
        payload = bytearray()
        for name, data in entries.items():
            node = header
            parts = name.split("/")
            for part in parts[:-1]:
                node = node["files"].setdefault(part, {"files": {}})
            node["files"][parts[-1]] = {"size": len(data), "offset": str(offset)}
            payload.extend(data)
            offset += len(data)
        header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
        packed_size = len(header_bytes) + 9
        base_offset = 8 + packed_size
        path.write_bytes(
            struct.pack("<IIII", 4, packed_size, len(header_bytes) + 5, len(header_bytes))
            + header_bytes
            + b"\0" * (base_offset - 16 - len(header_bytes))
            + bytes(payload)
        )

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
        old_asar = server.CODEX_APP_ASAR
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
            server.CODEX_APP_ASAR = Path(tmpdir) / "missing.asar"
            try:
                pets = server.list_pet_packages()
                image = server.read_pet_spritesheet("custom:duodong")
            finally:
                server.PETS_DIR = old_pets_dir
                server.CODEX_APP_ASAR = old_asar

        self.assertEqual(len(pets), 1)
        self.assertEqual(pets[0]["id"], "custom:duodong")
        self.assertEqual(pets[0]["local_id"], "duodong")
        self.assertEqual(pets[0]["source"], "custom")
        self.assertEqual(pets[0]["display_name"], "Duo Dong")
        self.assertEqual(pets[0]["spritesheet_url"], "/pets/custom%3Aduodong/spritesheet.webp")
        self.assertEqual(pets[0]["states"]["running"], 7)
        self.assertNotIn("privateField", pets[0])
        self.assertEqual(image, b"webp")

    def test_pet_spritesheet_path_cannot_escape_pet_directory(self):
        old_pets_dir = server.PETS_DIR
        old_asar = server.CODEX_APP_ASAR
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
            server.CODEX_APP_ASAR = Path(tmpdir) / "missing.asar"
            try:
                pets = server.list_pet_packages()
                image = server.read_pet_spritesheet("custom:duodong")
                escaped = server.read_pet_spritesheet("custom:../secret")
            finally:
                server.PETS_DIR = old_pets_dir
                server.CODEX_APP_ASAR = old_asar

        self.assertEqual(pets, [])
        self.assertIsNone(image)
        self.assertIsNone(escaped)

    def test_official_pet_package_reads_spritesheet_from_codex_asar(self):
        old_asar = server.CODEX_APP_ASAR
        with tempfile.TemporaryDirectory() as tmpdir:
            asar = Path(tmpdir) / "app.asar"
            self.write_fake_asar(
                asar,
                {"webview/assets/codex-spritesheet-v4-Bl6P89d_.webp": b"official-webp"},
            )
            server.CODEX_APP_ASAR = asar
            server.load_asar_header.cache_clear()
            server.official_spritesheet_paths.cache_clear()
            try:
                pets = server.list_official_pet_packages()
                image = server.read_pet_spritesheet("codex")
            finally:
                server.CODEX_APP_ASAR = old_asar
                server.load_asar_header.cache_clear()
                server.official_spritesheet_paths.cache_clear()

        self.assertEqual(len(pets), 1)
        self.assertEqual(pets[0]["id"], "codex")
        self.assertEqual(pets[0]["source"], "official")
        self.assertEqual(pets[0]["spritesheet_url"], "/pets/codex/spritesheet.webp")
        self.assertEqual(image, b"official-webp")

    def test_official_pet_package_survives_spritesheet_hash_change(self):
        old_asar = server.CODEX_APP_ASAR
        with tempfile.TemporaryDirectory() as tmpdir:
            asar = Path(tmpdir) / "app.asar"
            self.write_fake_asar(
                asar,
                {"webview/assets/codex-spritesheet-v5-NewHash.webp": b"new-official-webp"},
            )
            server.CODEX_APP_ASAR = asar
            server.load_asar_header.cache_clear()
            server.official_spritesheet_paths.cache_clear()
            try:
                pets = server.list_official_pet_packages()
                image = server.read_pet_spritesheet("codex")
            finally:
                server.CODEX_APP_ASAR = old_asar
                server.load_asar_header.cache_clear()
                server.official_spritesheet_paths.cache_clear()

        self.assertEqual(len(pets), 1)
        self.assertEqual(pets[0]["id"], "codex")
        self.assertEqual(image, b"new-official-webp")

    def test_selected_pet_package_follows_codex_avatar_setting(self):
        old_config = server.CODEX_CONFIG
        old_global_state = server.CODEX_GLOBAL_STATE
        old_override = os.environ.pop("CODEX_STATUS_PET_ID", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config.toml"
            global_state = Path(tmpdir) / "state.json"
            config.write_text('[desktop]\nselected-avatar-id = "custom:ikun"\n', encoding="utf-8")
            server.CODEX_CONFIG = config
            server.CODEX_GLOBAL_STATE = global_state
            try:
                selected = server.selected_pet_package_id(
                    [{"id": "codex"}, {"id": "custom:duodong"}, {"id": "custom:ikun"}]
                )
            finally:
                server.CODEX_CONFIG = old_config
                server.CODEX_GLOBAL_STATE = old_global_state
                if old_override is not None:
                    os.environ["CODEX_STATUS_PET_ID"] = old_override

        self.assertEqual(selected, "custom:ikun")

    def test_selected_pet_package_reads_config_without_tomllib(self):
        old_config = server.CODEX_CONFIG
        old_global_state = server.CODEX_GLOBAL_STATE
        old_tomllib = server.tomllib
        old_override = os.environ.pop("CODEX_STATUS_PET_ID", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config.toml"
            global_state = Path(tmpdir) / "state.json"
            config.write_text(
                'model = "gpt"\n[desktop]\nselected-avatar-id = "custom:ikun"\n',
                encoding="utf-8",
            )
            server.CODEX_CONFIG = config
            server.CODEX_GLOBAL_STATE = global_state
            server.tomllib = None
            try:
                selected = server.selected_pet_package_id(
                    [{"id": "codex"}, {"id": "custom:ikun"}]
                )
            finally:
                server.CODEX_CONFIG = old_config
                server.CODEX_GLOBAL_STATE = old_global_state
                server.tomllib = old_tomllib
                if old_override is not None:
                    os.environ["CODEX_STATUS_PET_ID"] = old_override

        self.assertEqual(selected, "custom:ikun")

    def test_dashboard_contains_task_visibility_toggle(self):
        html = server.INDEX_HTML

        self.assertIn('id="showTaskToggle"', html)
        self.assertIn('id="showPetToggle"', html)
        self.assertIn('id="petDock"', html)
        self.assertIn("compact-mode", html)
        self.assertIn("codex-status-show-task", html)
        self.assertIn("codex-status-show-pet", html)
        self.assertIn('fetch("/api/pets"', html)
        self.assertIn("style.backgroundImage", html)
        self.assertIn("function maybeRefreshPets", html)
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
