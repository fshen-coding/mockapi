# -*- coding: utf-8 -*-
"""PostgreSQL-backed user/session/operation audit storage."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "postgresql://mockapi:mockapi@127.0.0.1:54329/mockapi"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"


class AuditStore:
    def __init__(self) -> None:
        self.database_url = os.getenv("MOCKAPI_DATABASE_URL", DEFAULT_DATABASE_URL)
        self.enabled = os.getenv("MOCKAPI_AUDIT_ENABLED", "true").lower() != "false"

    @contextmanager
    def connect(self):
        conn = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        if not self.enabled:
            return
        try:
            with self.connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_users (
                        id BIGSERIAL PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        last_login_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id BIGSERIAL PRIMARY KEY,
                        session_id UUID NOT NULL UNIQUE,
                        username TEXT NOT NULL REFERENCES app_users(username),
                        env TEXT NOT NULL,
                        phone_number TEXT NOT NULL,
                        merchant_id TEXT,
                        application_unique_id TEXT,
                        selected_application_unique_id TEXT,
                        session_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        connected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        disconnected_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_operations (
                        id BIGSERIAL PRIMARY KEY,
                        session_id UUID,
                        username TEXT REFERENCES app_users(username),
                        env TEXT,
                        phone_number TEXT,
                        merchant_id TEXT,
                        operation_name TEXT NOT NULL,
                        request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        success BOOLEAN,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS contact_issues (
                        id BIGSERIAL PRIMARY KEY,
                        created_by TEXT REFERENCES app_users(username),
                        issue TEXT NOT NULL,
                        env TEXT,
                        phone_number TEXT,
                        session_id UUID,
                        merchant_id TEXT,
                        status TEXT NOT NULL DEFAULT '待回复',
                        reply TEXT,
                        replied_by TEXT REFERENCES app_users(username),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        replied_at TIMESTAMPTZ,
                        deleted_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS prompt_templates (
                        id BIGSERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        logic_type TEXT NOT NULL CHECK (logic_type IN ('sql', 'http', 'python')),
                        logic TEXT NOT NULL,
                        example_prompt TEXT NOT NULL DEFAULT '',
                        created_by TEXT REFERENCES app_users(username),
                        updated_by TEXT REFERENCES app_users(username),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        deleted_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute("ALTER TABLE prompt_templates ADD COLUMN IF NOT EXISTS example_prompt TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE prompt_templates ADD COLUMN IF NOT EXISTS is_disabled BOOLEAN NOT NULL DEFAULT FALSE")
                # Optional per-template environment lock. When set, the template
                # can only run in that env and the UI disables the picker.
                conn.execute("ALTER TABLE prompt_templates ADD COLUMN IF NOT EXISTS locked_env TEXT")
                # Per-user scenario step parameter overrides. Each row is a JSON
                # blob holding the user-chosen field values for a single step,
                # keyed by (username, scenario_key, step_key). Scenario tree
                # re-uses these overrides on the next run.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scenario_step_overrides (
                        username TEXT NOT NULL REFERENCES app_users(username),
                        scenario_key TEXT NOT NULL,
                        step_key TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        PRIMARY KEY (username, scenario_key, step_key)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_scenario_step_overrides_user "
                    "ON scenario_step_overrides(username)"
                )
                # Global scenario meta overrides: admins can rename scenarios or
                # rewrite their descriptions; all users see the override.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scenario_meta_overrides (
                        scenario_key TEXT PRIMARY KEY,
                        name TEXT,
                        description TEXT,
                        updated_by TEXT REFERENCES app_users(username),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                # Per-user drag-and-drop step ordering per scenario. Stores the
                # desired step_key sequence as a JSONB list; steps that aren't
                # present in the list keep their base-defined position appended
                # afterwards.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scenario_step_order_overrides (
                        username TEXT NOT NULL REFERENCES app_users(username),
                        scenario_key TEXT NOT NULL,
                        step_order JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        PRIMARY KEY (username, scenario_key)
                    )
                    """
                )
                # Global admin-editable step meta: rename title / rewrite
                # description / soft-delete via is_hidden. Visible to every user.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scenario_step_meta_overrides (
                        scenario_key TEXT NOT NULL,
                        step_key TEXT NOT NULL,
                        title TEXT,
                        description TEXT,
                        is_hidden BOOLEAN NOT NULL DEFAULT FALSE,                        updated_by TEXT REFERENCES app_users(username),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        PRIMARY KEY (scenario_key, step_key)
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_username ON user_sessions(username)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_phone ON user_sessions(phone_number)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_operations_session ON user_operations(session_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_operations_username ON user_operations(username)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_operations_created ON user_operations(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_issues_status ON contact_issues(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_issues_created_by ON contact_issues(created_by)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_issues_created ON contact_issues(created_at)")
                # Admin-editable user notes field
                conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS notes TEXT NOT NULL DEFAULT ''")
                # Registration approval workflow: pending → active / rejected
                conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'")
                self.ensure_admin_user(conn)
            log.info("Mock API audit database schema ready")
        except Exception as exc:
            log.warning("Mock API audit database is unavailable: %s", exc)

    def ensure_admin_user(self, conn) -> None:
        row = conn.execute(
            "SELECT username FROM app_users WHERE username = %s",
            (ADMIN_USERNAME,),
        ).fetchone()
        if row:
            return
        conn.execute(
            """
            INSERT INTO app_users (username, password_hash, role)
            VALUES (%s, %s, 'admin')
            """,
            (ADMIN_USERNAME, self.hash_password(ADMIN_PASSWORD)),
        )

    def register_user(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        if username == ADMIN_USERNAME:
            raise ValueError("admin 为管理员账号，不能注册")
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT username FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
            if existing:
                raise ValueError("账号已存在，请返回登录")
            row = conn.execute(
                """
                INSERT INTO app_users (username, password_hash, role, status)
                VALUES (%s, %s, 'user', 'pending')
                RETURNING username, role, status, created_at
                """,
                (username, self.hash_password(password)),
            ).fetchone()
        return dict(row)

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT username, password_hash, role, status FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
            if not row or not self.verify_password(password, row["password_hash"]):
                return None
            if row["status"] == "pending":
                raise PermissionError("pending")
            if row["status"] == "rejected":
                raise PermissionError("rejected")
            conn.execute(
                "UPDATE app_users SET last_login_at = now() WHERE username = %s",
                (username,),
            )
        return {"username": row["username"], "role": row["role"]}

    def user_exists(self, username: str | None) -> bool:
        username = (username or "").strip()
        if not username:
            return False
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
        return bool(row)

    def get_user_role(self, username: str | None) -> str | None:
        username = (username or "").strip()
        if not username:
            return None
        with self.connect() as conn:
            row = conn.execute(
                "SELECT role FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
        return row["role"] if row else None

    # ---------- Admin: user management ----------

    def list_users(self) -> list[dict[str, Any]]:
        """Return all users (id, username, role, status, notes, created_at, last_login_at)."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, username, role, status, notes, created_at, last_login_at
                FROM app_users
                ORDER BY
                    CASE WHEN status = 'pending' THEN 0 ELSE 1 END ASC,
                    created_at ASC
                """
            ).fetchall()
        return [self._normalize_user(row) for row in rows]

    def update_user(self, target_username: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Admin: rename username, reset password, update notes, and/or update status.

        ``payload`` may contain any subset of: ``new_username``, ``new_password``,
        ``notes``, ``status`` ('active' | 'pending' | 'rejected').
        Returns the updated user row, or ``None`` if the target was not found.
        Raises ``ValueError`` if the new username conflicts with an existing account.
        """
        target_username = (target_username or "").strip()
        if not target_username:
            raise ValueError("target_username 不能为空")
        fields: list[str] = []
        params: list[Any] = []
        new_username = (payload.get("new_username") or "").strip()
        if new_username and new_username != target_username:
            fields.append("username = %s")
            params.append(new_username)
        new_password = (payload.get("new_password") or "").strip()
        if new_password:
            fields.append("password_hash = %s")
            params.append(self.hash_password(new_password))
        if "notes" in payload:
            fields.append("notes = %s")
            params.append(payload.get("notes") or "")
        if "status" in payload:
            new_status = (payload.get("status") or "active").strip()
            if new_status not in ("active", "pending", "rejected"):
                raise ValueError(f"不支持的 status 值: {new_status}")
            fields.append("status = %s")
            params.append(new_status)
        if not fields:
            # Nothing to update — return current row as-is
            return self._get_user_row(target_username)
        params.append(target_username)
        with self.connect() as conn:
            # Check new_username uniqueness if renaming
            if new_username and new_username != target_username:
                existing = conn.execute(
                    "SELECT 1 FROM app_users WHERE username = %s",
                    (new_username,),
                ).fetchone()
                if existing:
                    raise ValueError(f"账号「{new_username}」已存在")
            row = conn.execute(
                f"""
                UPDATE app_users
                SET {', '.join(fields)}
                WHERE username = %s
                RETURNING id, username, role, status, notes, created_at, last_login_at
                """,
                params,
            ).fetchone()
        return self._normalize_user(row) if row else None

    def delete_user(self, target_username: str) -> bool:
        """Admin: hard-delete a user and all their associated data.

        Cascades via explicit deletes in the correct FK order because the schema
        does not define ON DELETE CASCADE.  The admin user cannot be deleted.
        """
        target_username = (target_username or "").strip()
        if not target_username:
            return False
        if target_username == ADMIN_USERNAME:
            raise ValueError("不能删除内置管理员账号")
        with self.connect() as conn:
            # Remove FK-dependent rows first
            conn.execute("DELETE FROM scenario_step_order_overrides WHERE username = %s", (target_username,))
            conn.execute("DELETE FROM scenario_step_overrides WHERE username = %s", (target_username,))
            conn.execute("UPDATE scenario_meta_overrides SET updated_by = NULL WHERE updated_by = %s", (target_username,))
            conn.execute("UPDATE scenario_step_meta_overrides SET updated_by = NULL WHERE updated_by = %s", (target_username,))
            conn.execute("UPDATE contact_issues SET replied_by = NULL WHERE replied_by = %s", (target_username,))
            conn.execute("UPDATE contact_issues SET created_by = NULL WHERE created_by = %s", (target_username,))
            conn.execute("UPDATE prompt_templates SET created_by = NULL WHERE created_by = %s", (target_username,))
            conn.execute("UPDATE prompt_templates SET updated_by = NULL WHERE updated_by = %s", (target_username,))
            conn.execute("UPDATE user_operations SET username = NULL WHERE username = %s", (target_username,))
            conn.execute("DELETE FROM user_sessions WHERE username = %s", (target_username,))
            result = conn.execute("DELETE FROM app_users WHERE username = %s", (target_username,))
        return result.rowcount > 0

    def _get_user_row(self, username: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, username, role, status, notes, created_at, last_login_at FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
        return self._normalize_user(row) if row else None

    @staticmethod
    def _normalize_user(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "role": row["role"],
            "status": row.get("status") or "active",
            "notes": row.get("notes") or "",
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "",
            "last_login_at": row["last_login_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("last_login_at") else "",
        }

    def record_session(self, username: str, session_data: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (
                    session_id, username, env, phone_number, merchant_id,
                    application_unique_id, selected_application_unique_id, session_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    env = EXCLUDED.env,
                    phone_number = EXCLUDED.phone_number,
                    merchant_id = EXCLUDED.merchant_id,
                    application_unique_id = EXCLUDED.application_unique_id,
                    selected_application_unique_id = EXCLUDED.selected_application_unique_id,
                    session_payload = EXCLUDED.session_payload
                """,
                (
                    session_data.get("session_id"),
                    username,
                    session_data.get("env"),
                    session_data.get("phone_number"),
                    session_data.get("merchant_id"),
                    session_data.get("application_unique_id"),
                    session_data.get("selected_application_unique_id"),
                    self.json_dumps(session_data),
                ),
            )

    def mark_session_disconnected(self, session_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE user_sessions SET disconnected_at = now() WHERE session_id = %s",
                (session_id,),
            )

    def record_operation(
        self,
        *,
        username: str | None,
        session_data: dict[str, Any] | None,
        operation_name: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        success: bool | None,
    ) -> None:
        username = (username or "").strip()
        if not username:
            raise ValueError("username is required for operation audit")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_operations (
                    session_id, username, env, phone_number, merchant_id,
                    operation_name, request_payload, response_payload, success
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    request_payload.get("session_id"),
                    username,
                    session_data.get("env") if session_data else None,
                    session_data.get("phone_number") if session_data else None,
                    session_data.get("merchant_id") if session_data else None,
                    operation_name,
                    self.json_dumps(request_payload),
                    self.json_dumps(response_payload),
                    success,
                ),
            )

    def list_user_operations(
        self,
        *,
        username: str | None = None,
        phone_number: str | None = None,
        session_id: str | None = None,
        limit: int = 200,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        """Query user_operations with optional filters.

        - username: restrict to a single owner (non-admin callers pass current user)
        - phone_number / session_id: optional filters
        - include_all: admin override that allows cross-user query when username is None
        """
        if not self.enabled:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if username:
            clauses.append("username = %s")
            params.append(username.strip())
        elif not include_all:
            return []
        if phone_number:
            clauses.append("phone_number = %s")
            params.append(phone_number.strip())
        if session_id:
            clauses.append("session_id::text = %s")
            params.append(session_id.strip())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = max(1, min(int(limit or 200), 1000))
        sql = (
            "SELECT id, session_id::text AS session_id, username, env, phone_number, merchant_id, "
            "operation_name, request_payload, response_payload, success, created_at "
            f"FROM user_operations {where} ORDER BY created_at DESC LIMIT %s"
        )
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": str(row["id"]),
                "session_id": row.get("session_id") or "",
                "username": row.get("username") or "",
                "env": row.get("env") or "",
                "phone_number": row.get("phone_number") or "",
                "merchant_id": row.get("merchant_id") or "",
                "operation_name": row.get("operation_name") or "",
                "request_payload": row.get("request_payload") or {},
                "response_payload": row.get("response_payload") or {},
                "success": row.get("success"),
                "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "",
            }
            for row in rows
        ]

    def create_contact_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO contact_issues (
                    created_by, issue, env, phone_number, session_id, merchant_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_by, issue, env, phone_number, session_id, merchant_id,
                    status, reply, replied_by, created_at, replied_at
                """,
                (
                    payload.get("created_by"),
                    payload.get("issue"),
                    payload.get("env"),
                    payload.get("phone_number"),
                    payload.get("session_id") or None,
                    payload.get("merchant_id"),
                ),
            ).fetchone()
        return self.normalize_contact_issue(row)

    def list_contact_issues(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_by, issue, env, phone_number, session_id, merchant_id,
                    status, reply, replied_by, created_at, replied_at
                FROM contact_issues
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self.normalize_contact_issue(row) for row in rows]

    def reply_contact_issue(self, issue_id: int, reply: str, replied_by: str | None) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                UPDATE contact_issues
                SET reply = %s,
                    replied_by = %s,
                    status = '已回复',
                    replied_at = now()
                WHERE id = %s AND deleted_at IS NULL
                RETURNING id, created_by, issue, env, phone_number, session_id, merchant_id,
                    status, reply, replied_by, created_at, replied_at
                """,
                (reply, replied_by, issue_id),
            ).fetchone()
        return self.normalize_contact_issue(row) if row else None

    def delete_contact_issue(self, issue_id: int) -> bool:
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE contact_issues
                SET deleted_at = now()
                WHERE id = %s AND deleted_at IS NULL
                """,
                (issue_id,),
            )
        return result.rowcount > 0

    @staticmethod
    def normalize_contact_issue(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "created_by": row.get("created_by"),
            "issue": row.get("issue"),
            "env": row.get("env") or "-",
            "phone_number": row.get("phone_number") or "-",
            "session_id": str(row.get("session_id") or "-"),
            "merchant_id": row.get("merchant_id") or "-",
            "status": row.get("status") or "待回复",
            "reply": row.get("reply") or "",
            "replied_by": row.get("replied_by") or "",
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "",
            "replied_at": row["replied_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("replied_at") else "",
        }

    # ---------- Prompt templates ----------

    PROMPT_TEMPLATE_TYPES = ("sql", "http", "python")

    def list_prompt_templates(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, description, logic_type, logic, example_prompt, is_disabled,
                    locked_env, created_by, updated_by, created_at, updated_at
                FROM prompt_templates
                WHERE deleted_at IS NULL
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [self.normalize_prompt_template(row) for row in rows]

    def get_prompt_template(self, template_id: int) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, description, logic_type, logic, example_prompt, is_disabled,
                    locked_env, created_by, updated_by, created_at, updated_at
                FROM prompt_templates
                WHERE id = %s AND deleted_at IS NULL
                """,
                (template_id,),
            ).fetchone()
        return self.normalize_prompt_template(row) if row else None

    def list_active_prompt_templates(self) -> list[dict[str, Any]]:
        """Return only templates that admins have not disabled."""
        return [tpl for tpl in self.list_prompt_templates() if not tpl.get("is_disabled")]

    def create_prompt_template(self, payload: dict[str, Any], created_by: str) -> dict[str, Any]:
        title = (payload.get("title") or "").strip()
        if not title:
            raise ValueError("标题不能为空")
        logic_type = (payload.get("logic_type") or "sql").strip().lower()
        if logic_type not in self.PROMPT_TEMPLATE_TYPES:
            raise ValueError(f"不支持的 logic_type: {logic_type}")
        logic = payload.get("logic") or ""
        if not logic.strip():
            raise ValueError("逻辑内容不能为空")
        description = payload.get("description") or ""
        example_prompt = payload.get("example_prompt") or ""
        locked_env_raw = payload.get("locked_env")
        locked_env = (locked_env_raw or "").strip().lower() or None
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO prompt_templates (
                    title, description, logic_type, logic, example_prompt,
                    locked_env, created_by, updated_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, description, logic_type, logic, example_prompt, is_disabled,
                    locked_env, created_by, updated_by, created_at, updated_at
                """,
                (title, description, logic_type, logic, example_prompt,
                 locked_env, created_by, created_by),
            ).fetchone()
        return self.normalize_prompt_template(row)

    def update_prompt_template(self, template_id: int, payload: dict[str, Any], updated_by: str) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = []
        if "title" in payload:
            title = (payload.get("title") or "").strip()
            if not title:
                raise ValueError("标题不能为空")
            fields.append("title = %s")
            params.append(title)
        if "description" in payload:
            fields.append("description = %s")
            params.append(payload.get("description") or "")
        if "logic_type" in payload:
            logic_type = (payload.get("logic_type") or "").strip().lower()
            if logic_type not in self.PROMPT_TEMPLATE_TYPES:
                raise ValueError(f"不支持的 logic_type: {logic_type}")
            fields.append("logic_type = %s")
            params.append(logic_type)
        if "logic" in payload:
            logic = payload.get("logic") or ""
            if not logic.strip():
                raise ValueError("逻辑内容不能为空")
            fields.append("logic = %s")
            params.append(logic)
        if "example_prompt" in payload:
            fields.append("example_prompt = %s")
            params.append(payload.get("example_prompt") or "")
        if "is_disabled" in payload:
            fields.append("is_disabled = %s")
            params.append(bool(payload.get("is_disabled")))
        if "locked_env" in payload:
            locked_env = (payload.get("locked_env") or "").strip().lower() or None
            fields.append("locked_env = %s")
            params.append(locked_env)
        if not fields:
            return self.get_prompt_template(template_id)
        fields.append("updated_by = %s")
        params.append(updated_by)
        fields.append("updated_at = now()")
        params.append(template_id)
        with self.connect() as conn:
            row = conn.execute(
                f"""
                UPDATE prompt_templates
                SET {', '.join(fields)}
                WHERE id = %s AND deleted_at IS NULL
                RETURNING id, title, description, logic_type, logic, example_prompt, is_disabled,
                    locked_env, created_by, updated_by, created_at, updated_at
                """,
                params,
            ).fetchone()
        return self.normalize_prompt_template(row) if row else None

    def delete_prompt_template(self, template_id: int) -> bool:
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE prompt_templates
                SET deleted_at = now()
                WHERE id = %s AND deleted_at IS NULL
                """,
                (template_id,),
            )
        return result.rowcount > 0

    # ---------- Scenario step overrides ----------

    def list_scenario_step_overrides(self, username: str) -> list[dict[str, Any]]:
        if not self.enabled or not (username or "").strip():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT username, scenario_key, step_key, payload, updated_at
                FROM scenario_step_overrides
                WHERE username = %s
                """,
                (username,),
            ).fetchall()
        return [
            {
                "username": row["username"],
                "scenario_key": row["scenario_key"],
                "step_key": row["step_key"],
                "payload": row["payload"] or {},
                "updated_at": (
                    row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
                ),
            }
            for row in rows
        ]

    def upsert_scenario_step_override(
        self,
        username: str,
        scenario_key: str,
        step_key: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        username = (username or "").strip()
        scenario_key = (scenario_key or "").strip()
        step_key = (step_key or "").strip()
        if not username:
            raise ValueError("username is required")
        if not scenario_key:
            raise ValueError("scenario_key is required")
        if not step_key:
            raise ValueError("step_key is required")
        payload = payload if isinstance(payload, dict) else {}
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO scenario_step_overrides (username, scenario_key, step_key, payload, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, now())
                ON CONFLICT (username, scenario_key, step_key)
                DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                RETURNING username, scenario_key, step_key, payload, updated_at
                """,
                (username, scenario_key, step_key, json.dumps(payload, ensure_ascii=False)),
            ).fetchone()
        return {
            "username": row["username"],
            "scenario_key": row["scenario_key"],
            "step_key": row["step_key"],
            "payload": row["payload"] or {},
            "updated_at": (
                row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
            ),
        }

    # ---------- Scenario step order overrides (per-user drag&drop) ----------

    def list_scenario_step_orders(self, username: str) -> list[dict[str, Any]]:
        if not self.enabled or not (username or "").strip():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT username, scenario_key, step_order, updated_at
                FROM scenario_step_order_overrides
                WHERE username = %s
                """,
                (username,),
            ).fetchall()
        return [
            {
                "username": row["username"],
                "scenario_key": row["scenario_key"],
                "step_order": row["step_order"] or [],
                "updated_at": (
                    row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
                ),
            }
            for row in rows
        ]

    def upsert_scenario_step_order(
        self,
        username: str,
        scenario_key: str,
        step_order: list[str] | None,
    ) -> dict[str, Any]:
        username = (username or "").strip()
        scenario_key = (scenario_key or "").strip()
        if not username:
            raise ValueError("username is required")
        if not scenario_key:
            raise ValueError("scenario_key is required")
        step_order = [str(s).strip() for s in (step_order or []) if str(s or "").strip()]
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO scenario_step_order_overrides (username, scenario_key, step_order, updated_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (username, scenario_key)
                DO UPDATE SET step_order = EXCLUDED.step_order, updated_at = now()
                RETURNING username, scenario_key, step_order, updated_at
                """,
                (username, scenario_key, json.dumps(step_order, ensure_ascii=False)),
            ).fetchone()
        return {
            "username": row["username"],
            "scenario_key": row["scenario_key"],
            "step_order": row["step_order"] or [],
            "updated_at": (
                row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
            ),
        }

    # ---------- Scenario step meta overrides (admin-editable, global) ----------

    def list_scenario_step_meta_overrides(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT scenario_key, step_key, title, description, is_hidden,
                    updated_by, updated_at
                FROM scenario_step_meta_overrides
                """
            ).fetchall()
        return [
            {
                "scenario_key": row["scenario_key"],
                "step_key": row["step_key"],
                "title": row.get("title") or "",
                "description": row.get("description") or "",
                "is_hidden": bool(row.get("is_hidden")),
                "updated_by": row.get("updated_by") or "",
                "updated_at": (
                    row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
                ),
            }
            for row in rows
        ]

    def upsert_scenario_step_meta_override(
        self,
        scenario_key: str,
        step_key: str,
        title: str | None,
        description: str | None,
        is_hidden: bool,
        updated_by: str,
    ) -> dict[str, Any]:
        scenario_key = (scenario_key or "").strip()
        step_key = (step_key or "").strip()
        if not scenario_key:
            raise ValueError("scenario_key is required")
        if not step_key:
            raise ValueError("step_key is required")
        clean_title = title if title is None else (title.strip() or None)
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO scenario_step_meta_overrides
                    (scenario_key, step_key, title, description, is_hidden, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (scenario_key, step_key)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    is_hidden = EXCLUDED.is_hidden,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
                RETURNING scenario_key, step_key, title, description, is_hidden,
                    updated_by, updated_at
                """,
                (scenario_key, step_key, clean_title, description, bool(is_hidden), updated_by),
            ).fetchone()
        return {
            "scenario_key": row["scenario_key"],
            "step_key": row["step_key"],
            "title": row.get("title") or "",
            "description": row.get("description") or "",
            "is_hidden": bool(row.get("is_hidden")),
            "updated_by": row.get("updated_by") or "",
            "updated_at": (
                row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
            ),
        }

    def delete_scenario_step_meta_override(
        self,
        scenario_key: str,
        step_key: str,
    ) -> bool:
        scenario_key = (scenario_key or "").strip()
        step_key = (step_key or "").strip()
        if not (scenario_key and step_key):
            return False
        with self.connect() as conn:
            result = conn.execute(
                """
                DELETE FROM scenario_step_meta_overrides
                WHERE scenario_key = %s AND step_key = %s
                """,
                (scenario_key, step_key),
            )
        return result.rowcount > 0

    # ---------- Scenario meta overrides (admin-editable) ----------

    def list_scenario_meta_overrides(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT scenario_key, name, description, updated_by, updated_at
                FROM scenario_meta_overrides
                """
            ).fetchall()
        return [
            {
                "scenario_key": row["scenario_key"],
                "name": row.get("name") or "",
                "description": row.get("description") or "",
                "updated_by": row.get("updated_by") or "",
                "updated_at": (
                    row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
                ),
            }
            for row in rows
        ]

    def upsert_scenario_meta_override(
        self,
        scenario_key: str,
        name: str | None,
        description: str | None,
        updated_by: str,
    ) -> dict[str, Any]:
        scenario_key = (scenario_key or "").strip()
        if not scenario_key:
            raise ValueError("scenario_key is required")
        clean_name = (name or "").strip() or None
        clean_description = description if description is not None else None
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO scenario_meta_overrides (scenario_key, name, description, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (scenario_key)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
                RETURNING scenario_key, name, description, updated_by, updated_at
                """,
                (scenario_key, clean_name, clean_description, updated_by),
            ).fetchone()
        return {
            "scenario_key": row["scenario_key"],
            "name": row.get("name") or "",
            "description": row.get("description") or "",
            "updated_by": row.get("updated_by") or "",
            "updated_at": (
                row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else ""
            ),
        }

    def delete_scenario_step_override(
        self,
        username: str,
        scenario_key: str,
        step_key: str,
    ) -> bool:
        username = (username or "").strip()
        scenario_key = (scenario_key or "").strip()
        step_key = (step_key or "").strip()
        if not (username and scenario_key and step_key):
            return False
        with self.connect() as conn:
            result = conn.execute(
                """
                DELETE FROM scenario_step_overrides
                WHERE username = %s AND scenario_key = %s AND step_key = %s
                """,
                (username, scenario_key, step_key),
            )
        return result.rowcount > 0

    @staticmethod
    def normalize_prompt_template(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "title": row.get("title") or "",
            "description": row.get("description") or "",
            "logic_type": row.get("logic_type") or "sql",
            "logic": row.get("logic") or "",
            "example_prompt": row.get("example_prompt") or "",
            "is_disabled": bool(row.get("is_disabled")),
            "locked_env": row.get("locked_env") or "",
            "created_by": row.get("created_by") or "",
            "updated_by": row.get("updated_by") or "",
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "",
            "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else "",
        }

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
        return f"pbkdf2_sha256${salt}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, salt, expected = encoded.split("$", 2)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
            return hmac.compare_digest(digest.hex(), expected)
        except Exception:
            return False

    @staticmethod
    def json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)


audit_store = AuditStore()
