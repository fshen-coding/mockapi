"""PSP 模板离线回归：参数契约、手机号查询及写入前的失败保护。"""
from __future__ import annotations

import unittest
import re
import sqlite3
from contextlib import ExitStack
from unittest.mock import patch

from fastapi import HTTPException

from web.models.requests import PromptTemplateExecuteRequest
from web.routes import prompt_routes as routes
from web.services.audit_store import (
    PSP_IDENTITY_TEMPLATE_LOGIC,
    PSP_IDENTITY_TEMPLATE_TITLE,
)


TEMPLATE = {
    "id": 19,
    "title": PSP_IDENTITY_TEMPLATE_TITLE,
    "logic_type": "sql",
    "logic": PSP_IDENTITY_TEMPLATE_LOGIC,
    "is_disabled": False,
}


def parameters(**overrides):
    return {
        "phone": "13410276504",
        "id_card_match": "Y",
        "psp_type": "P1",
        "psp_subject_type": "PERSONAL",
        "company_name_match": "Y",
        "legal_name_match": "Y",
        **overrides,
    }


def lookup_result(rows):
    return {"success": True, "results": [{"rows": rows}]}


class PSPParameterTests(unittest.TestCase):
    def test_supported_personal_and_enterprise_subjects(self):
        provider_subjects = {
            **{provider: ("PERSONAL", "ENTERPRISE") for provider in ("P1", "P4", "P5", "P6", "P11")},
            "P3": ("CN_ID_CARD", "CREDIT_CODE"),
            "P2": ("0", "1"),
        }
        for provider, subjects in provider_subjects.items():
            for subject in subjects:
                with self.subTest(provider=provider, subject=subject):
                    raw = parameters(psp_type=provider, psp_subject_type=subject)
                    validated = routes._validated_template_params(TEMPLATE, raw)
                    self.assertEqual(validated, raw)
                    rendered, missing = routes._apply_params(TEMPLATE["logic"], validated)
                    self.assertEqual(missing, [])
                    self.assertNotIn("${", rendered)
                    self.assertIn(f"SET @psp_subject_type = '{subject}';", rendered)

    def test_numeric_zero_is_personal_for_p2(self):
        validated = routes._validated_template_params(
            TEMPLATE, parameters(psp_type="P2", psp_subject_type=0)
        )
        self.assertEqual(validated["psp_subject_type"], "0")

    def test_case_and_whitespace_are_normalised(self):
        validated = routes._validated_template_params(
            TEMPLATE,
            parameters(phone=" 13410276504 ", id_card_match=" n ", psp_type=" p3 ", psp_subject_type=" credit_code "),
        )
        self.assertEqual(validated, parameters(id_card_match="N", psp_type="P3", psp_subject_type="CREDIT_CODE"))

    def test_eight_digit_phone_is_accepted(self):
        validated = routes._validated_template_params(TEMPLATE, parameters(phone="12345678"))
        self.assertEqual(validated["phone"], "12345678")

    def test_p8_and_p9_allow_missing_or_empty_subject(self):
        for provider in ("P8", "P9"):
            for value in (None, "", "  "):
                with self.subTest(provider=provider, value=value):
                    validated = routes._validated_template_params(
                        TEMPLATE, parameters(psp_type=provider, psp_subject_type=value)
                    )
                    self.assertEqual(validated["psp_subject_type"], "")
            raw = parameters(psp_type=provider)
            del raw["psp_subject_type"]
            self.assertEqual(routes._validated_template_params(TEMPLATE, raw)["psp_subject_type"], "")

    def test_stale_or_missing_subject_is_rejected_after_provider_switch(self):
        for provider, subject in (("P8", "PERSONAL"), ("P9", "ENTERPRISE"), ("P3", "PERSONAL"), ("P2", "PERSONAL"), ("P1", "CN_ID_CARD"), ("P1", "")):
            with self.subTest(provider=provider, subject=subject), self.assertRaises(ValueError):
                routes._validated_template_params(TEMPLATE, parameters(psp_type=provider, psp_subject_type=subject))
        raw = parameters()
        del raw["psp_subject_type"]
        with self.assertRaises(ValueError):
            routes._validated_template_params(TEMPLATE, raw)

    def test_invalid_and_injected_inputs_are_rejected(self):
        invalid_values = {
            "phone": ("", None, "123456789", "13410276504' OR 1=1 --", "１３４１０２７６５０４"),
            "id_card_match": ("", "YES", "Y'; UPDATE t_user SET id=1; --"),
            "psp_type": ("P7", "P1'; DROP TABLE t_user; --"),
            "psp_subject_type": ("PERSONAL'; DROP TABLE t_user; --",),
            "company_name_match": ("", None, "YES", "N'; SELECT 1; --"),
            "legal_name_match": ("", None, "YES", "N'; SELECT 1; --"),
        }
        for key, values in invalid_values.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    routes._validated_template_params(TEMPLATE, parameters(**{key: value}))

    def test_old_user_id_parameter_is_rejected(self):
        with self.assertRaises(ValueError):
            routes._validated_template_params(TEMPLATE, parameters(user_id=582540921))
        raw = parameters(user_id=582540921)
        del raw["phone"]
        with self.assertRaises(ValueError):
            routes._validated_template_params(TEMPLATE, raw)

    def test_name_flags_are_required_and_normalised(self):
        for key in ("company_name_match", "legal_name_match"):
            raw = parameters()
            del raw[key]
            with self.assertRaises(ValueError):
                routes._validated_template_params(TEMPLATE, raw)
            validated = routes._validated_template_params(TEMPLATE, parameters(**{key: " n "}))
            self.assertEqual(validated[key], "N")

    def test_company_and_legal_names_change_independently(self):
        # 使用实际 SQL 的 CASE 表达式计算四种组合，不触碰业务数据库。
        with sqlite3.connect(":memory:") as connection:
            for company_match in ("Y", "N"):
                for legal_match in ("Y", "N"):
                    bindings = {
                        "kr_company_name": "微山县五金有限公司", "kr_legal_name": "造数香碧",
                        "company_name_match": company_match, "legal_name_match": legal_match,
                    }
                    for field, baseline, flag in (
                        ("psp_subject_name", "kr_company_name", company_match),
                        ("psp_person_name", "kr_legal_name", legal_match),
                    ):
                        with self.subTest(company=company_match, legal=legal_match, field=field):
                            expression = re.search(rf"SET @{field} = (.*?);", TEMPLATE["logic"], re.S).group(1)
                            value = connection.execute("SELECT " + expression, bindings).fetchone()[0]
                            self.assertTrue(value)
                            self.assertEqual(value == bindings[baseline], flag == "Y")
        # P8 的企业名比较字段也必须受同一个开关控制。
        self.assertIn("SET eu.cert_name = @psp_subject_name,", TEMPLATE["logic"])
        self.assertNotIn("@epay_cert_name", TEMPLATE["logic"])


class PSPUserLookupTests(unittest.TestCase):
    def test_unique_user_is_resolved_in_selected_environment(self):
        with patch.object(routes, "_execute_sql", return_value=lookup_result([{"id": "582540921"}])) as execute:
            self.assertEqual(routes._resolve_psp_user_id("13410276504", "uat"), 582540921)
        execute.assert_called_once_with(
            "SELECT id FROM dsb_seller_center.t_user WHERE tel = '13410276504' LIMIT 2", "uat"
        )

    def test_missing_duplicate_failed_and_invalid_user_results_are_rejected(self):
        cases = [
            lookup_result([]),
            lookup_result([{"id": 1}, {"id": 2}]),
            {"success": False, "message": "查询失败"},
            lookup_result([{"id": None}]),
            lookup_result([{"id": 0}]),
            lookup_result([{"id": -1}]),
            lookup_result([{"id": "1; DROP TABLE t_user"}]),
        ]
        for result in cases:
            with self.subTest(result=result), patch.object(routes, "_execute_sql", return_value=result), self.assertRaises(ValueError):
                routes._resolve_psp_user_id("13410276504", "sit")

    def test_lookup_rejects_injection_before_database_access(self):
        with patch.object(routes, "_execute_sql") as execute, self.assertRaises(ValueError):
            routes._resolve_psp_user_id("13410276504' OR 1=1 --", "sit")
        execute.assert_not_called()


class PSPExecutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(routes, "require_valid_username", return_value="tester"))
        self.stack.enter_context(patch.object(routes, "_all_supported_envs", return_value=("sit", "uat")))
        self.stack.enter_context(patch.object(routes.audit_store, "get_prompt_template", return_value=dict(TEMPLATE)))
        self.stack.enter_context(patch.object(routes.audit_store, "record_operation"))
        self.ai = self.stack.enter_context(patch.object(routes, "_ai_materialise", side_effect=AssertionError("测试禁止调用 AI")))
        self.stack.enter_context(patch.object(routes, "_ai_summarise_execution", return_value={"summary": "执行完成"}))
        self.lookup = self.stack.enter_context(patch.object(routes, "_execute_sql"))
        self.write = self.stack.enter_context(patch.object(routes, "_execute_logic", return_value={"success": True}))

    async def execute(self, params):
        return await routes.execute_prompt_template(
            TEMPLATE["id"],
            PromptTemplateExecuteRequest(username="tester", user_input="PSP 校验", env="uat", params=params),
        )

    async def test_missing_or_duplicate_phone_never_writes(self):
        for rows in ([], [{"id": 1}, {"id": 2}]):
            with self.subTest(rows=rows):
                self.lookup.return_value = lookup_result(rows)
                with self.assertRaises(HTTPException) as raised:
                    await self.execute(parameters())
                self.assertEqual(raised.exception.status_code, 400)
                self.write.assert_not_called()
                self.ai.assert_not_called()

    async def test_invalid_parameters_never_query_or_write(self):
        for params in (parameters(phone=""), parameters(user_id=582540921), parameters(psp_type="P8"), {}):
            with self.subTest(params=params), self.assertRaises(HTTPException) as raised:
                await self.execute(params)
            self.assertEqual(raised.exception.status_code, 400)
        self.lookup.assert_not_called()
        self.write.assert_not_called()
        self.ai.assert_not_called()

    async def test_lookup_precedes_write_and_resolved_id_is_returned(self):
        calls = []

        def lookup(*args):
            calls.append("lookup")
            return lookup_result([{"id": 582540921}])

        def write(*args):
            calls.append("write")
            return {"success": True}

        self.lookup.side_effect = lookup
        self.write.side_effect = write
        response = await self.execute(parameters(psp_type="P2", psp_subject_type=0))
        self.assertTrue(response.success)
        self.assertEqual(calls, ["lookup", "write"])
        self.assertEqual(response.data["params"]["resolved_user_id"], 582540921)
        self.assertEqual(self.write.call_args.args[0], "sql")
        self.assertEqual(self.write.call_args.args[2], "uat")
        self.assertNotIn("${", self.write.call_args.args[1])
        self.assertIn("SET @phone = '13410276504';", self.write.call_args.args[1])
        self.assertIn("SET @psp_subject_type = '0';", self.write.call_args.args[1])
        self.ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
