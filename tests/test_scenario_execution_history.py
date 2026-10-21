"""执行历史 PostgreSQL 集成测试，使用独立 schema，不读写已有业务记录。"""
import os
import unittest
import uuid
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routes import auth_guard, scenario_routes
from web.services.audit_store import AuditStore


@unittest.skipUnless(os.getenv("MOCKAPI_HISTORY_TEST_DATABASE_URL"), "需要显式配置测试 PostgreSQL")
class ScenarioHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ["MOCKAPI_HISTORY_TEST_DATABASE_URL"]
        cls.schema = "history_test_" + uuid.uuid4().hex
        with psycopg.connect(cls.url) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        cls.store = AuditStore()
        cls.store.database_url = make_conninfo(cls.url, options=f"-csearch_path={cls.schema}")
        cls.store.init_schema()
        cls.store.register_user("alice", "test-password")
        cls.store.register_user("bob", "test-password")
        cls.patches = [patch.object(scenario_routes, "audit_store", cls.store), patch.object(auth_guard, "audit_store", cls.store)]
        for item in cls.patches:
            item.start()
        app = FastAPI()
        app.include_router(scenario_routes.router)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for item in cls.patches:
            item.stop()
        with psycopg.connect(cls.url) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def setUp(self):
        with self.store.connect() as conn:
            conn.execute("DELETE FROM scenario_execution_history")

    def save(self, record_id="run-1", username="alice", **fields):
        record = {"id": record_id, "scenario": "DS-CNY", "status": "完成", "steps": [{"response": {"large": "x" * 10000}}], "variables": {"phone": "12345678"}, "context": {"env": "uat"}, **fields}
        result = self.client.post("/api/scenario-overrides/execution-history", json={"username": username, "record": record})
        self.assertEqual(result.status_code, 200, result.text)
        return record

    def test_persistence_summary_and_lazy_detail(self):
        record = self.save()
        response = self.client.get("/api/scenario-overrides/execution-history", params={"username": "alice"}).json()["data"]
        self.assertEqual(len(response["items"]), 1)
        self.assertNotIn("steps", response["items"][0])
        self.assertNotIn("variables", response["items"][0])
        self.assertNotIn("context", response["items"][0])
        # A new store/connection still sees the saved record.
        fresh = AuditStore()
        fresh.database_url = self.store.database_url
        self.assertEqual(fresh.get_scenario_execution("alice", "run-1"), record)
        detail = self.client.get("/api/scenario-overrides/execution-history/run-1", params={"username": "alice"})
        self.assertEqual(detail.json()["data"], record)

    def test_retry_does_not_duplicate_or_overwrite(self):
        record = self.save()
        self.save(status="失败")
        self.assertEqual(self.store.get_scenario_execution("alice", "run-1"), record)
        self.assertEqual(len(self.store.list_scenario_executions("alice", 100, 0)), 1)

    def test_user_isolation_and_missing_detail(self):
        self.save()
        self.assertEqual(self.store.list_scenario_executions("bob", 100, 0), [])
        response = self.client.get("/api/scenario-overrides/execution-history/run-1", params={"username": "bob"})
        self.assertEqual(response.status_code, 404)
        self.save(username="bob", status="失败")
        self.assertEqual(self.store.get_scenario_execution("alice", "run-1")["status"], "完成")

    def test_pagination_and_latest_first(self):
        for number in range(3):
            self.save(record_id=f"run-{number}")
        first = self.client.get("/api/scenario-overrides/execution-history", params={"username": "alice", "limit": 2}).json()["data"]
        self.assertEqual([item["id"] for item in first["items"]], ["run-2", "run-1"])
        self.assertTrue(first["has_more"])
        last = self.client.get("/api/scenario-overrides/execution-history", params={"username": "alice", "limit": 2, "offset": 2}).json()["data"]
        self.assertEqual([item["id"] for item in last["items"]], ["run-0"])
        self.assertFalse(last["has_more"])

    def test_invalid_user_and_pagination(self):
        url = "/api/scenario-overrides/execution-history"
        self.assertEqual(self.client.get(url, params={"username": "unknown"}).status_code, 403)
        self.assertEqual(self.client.get(url, params={"username": "alice", "offset": -1}).status_code, 422)
        self.assertEqual(self.client.get(url, params={"username": "alice", "limit": 201}).status_code, 422)
        self.assertEqual(self.client.post(url, json={"username": "alice", "record": {"id": ""}}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
