# -*- coding: utf-8 -*-
"""Web 适配器：将 DPUMockService 的 input() 调用改为参数传入，返回结构化结果"""
import sys
import json
import os
import random
import logging
import re
import uuid
import time
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import pymysql

# 确保能导入项目根目录的 mock_sit 模块
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mock_sit import (
    DPUMockService, DatabaseExecutor, ApiConfig, DatabaseConfig,
    DPUStatus, RepaymentStatus, DrawdownFailureReason, ReturnedFailureReason,
    generate_uuid37, get_utc_time, get_current_time, calculate_future_date,
    validate_numeric_input, validate_phone_number, SCRIPT_DIR,
    fetch_sms_verification_code,
    log, faker
)
import requests as http_requests

log = logging.getLogger("mock_sit")


class WebDPUMockService(DPUMockService):
    """Web 适配器：所有 input() 改为方法参数，所有方法返回结构化 dict"""

    # 备用公司名。business-info 选了它时，director-info 自动套用「测近智」法人档案
    # （身份证正反面走 DOWSURE_CNY_BACKUP_DIRECTOR_ID_*，回落到默认 DIRECTOR_ID_*）。
    _DOWSURE_BACKUP_COMPANY_CN_NAME = "测广州市昆袄祝山脸从股份有限公司"

    # 仓库内 DOWSURE CNY 测试证件图（营业执照 / 法人身份证正反）。运行时上传到当前
    # 环境的 dpu-file 网关换取 objectKey，实现全环境自适应，不再依赖 .env 里会过期、
    # 且绑死单一环境的固定 key。所有 user 共用同一份仓库图片（跟随镜像发布）。
    _DOWSURE_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "dowsure_cny"
    _DOWSURE_ASSET_FILES = {
        "business_license": "business_license.png",
        "director_id_front": "director_id_front.png",
        "director_id_back": "director_id_back.png",
    }

    @staticmethod
    def _remove_test_offer_suffix(db: DatabaseExecutor, phone_number: str) -> dict:
        """Remove TESTOFFER from the latest 3PL authorization ID atomically."""
        suffix = "TESTOFFER"
        try:
            db.conn.begin()
            db.cursor.execute(
                """
                SELECT auth.authorization_id
                FROM dpu_seller_center.dpu_auth_token AS auth
                JOIN dpu_seller_center.dpu_users AS users
                  ON users.merchant_id = auth.merchant_id
                WHERE users.phone_number = %s
                  AND auth.authorization_party = '3PL'
                ORDER BY auth.created_at DESC
                LIMIT 1
                FOR UPDATE
                """,
                (phone_number,),
            )
            row = db.cursor.fetchone()
            if not row or not row[0]:
                raise ValueError("未找到手机号对应的 3PL authorization_id")

            old_offer_id = str(row[0])
            if not old_offer_id.endswith(suffix):
                raise ValueError("3PL authorization_id 不包含 TESTOFFER 后缀")
            new_offer_id = old_offer_id[:-len(suffix)]
            if not new_offer_id:
                raise ValueError("移除 TESTOFFER 后 authorization_id 为空")

            db.cursor.execute(
                """
                UPDATE dpu_seller_center.dpu_auth_token
                SET authorization_id = %s
                WHERE authorization_id = %s AND authorization_party = '3PL'
                """,
                (new_offer_id, old_offer_id),
            )
            auth_rows = db.cursor.rowcount
            db.cursor.execute(
                """
                UPDATE dpu_seller_center.dpu_3pl_shop_performance
                SET amazon_3pl_offer_id = %s
                WHERE amazon_3pl_offer_id = %s
                """,
                (new_offer_id, old_offer_id),
            )
            performance_rows = db.cursor.rowcount
            db.cursor.execute(
                """
                UPDATE dpu_seller_center.dpu_shops
                SET shop_reference_id = %s
                WHERE shop_reference_id = %s
                """,
                (new_offer_id, old_offer_id),
            )
            shop_rows = db.cursor.rowcount
            db.conn.commit()
            return {
                "old_offerid": old_offer_id,
                "new_offerid": new_offer_id,
                "updated_rows": {
                    "authorization": auth_rows,
                    "shop_performance": performance_rows,
                    "shops": shop_rows,
                },
            }
        except Exception:
            if db.conn:
                db.conn.rollback()
            raise

    def __init__(self, phone_number: str, db_executor: DatabaseExecutor):
        # 将类变量覆盖为实例变量，避免多会话并发串扰
        self.selected_application_unique_id: Optional[str] = None
        self.generated_selling_partner_id: Optional[str] = None
        self.session_user_token: str = ""
        # 已上传证件图的 objectKey 缓存，按 (env, asset) 复用，避免同环境同图重复上传。
        self._dowsure_asset_cache = {}
        self.cached_lender_repayment_id: Optional[str] = None
        self.dowsure_application_code: Optional[str] = None
        self.dowsure_credit_contract_no: Optional[str] = None
        self.dowsure_loan_code: Optional[str] = None
        self.dowsure_loan_contract_no: Optional[str] = None
        self.hsbc_psp_pending_account_id_by_merchant: Dict[str, str] = {}
        self.hsbc_psp_completed_account_ids_in_session: set = set()
        super().__init__(phone_number, db_executor)

    # ======================== 辅助方法 ========================

    def select_application(self, application_unique_id: Optional[str]) -> None:
        """Bind subsequent webhook payloads to the chosen dpu_application."""
        self.selected_application_unique_id = str(application_unique_id or "").strip() or None

    @property
    def application_unique_id(self) -> Optional[str]:
        if self.selected_application_unique_id:
            return self.selected_application_unique_id
        return super().application_unique_id

    @property
    def credit_offer_application_unique_id(self) -> Optional[str]:
        if not self.selected_application_unique_id:
            return super().credit_offer_application_unique_id

        sql = (
            "SELECT application_unique_id FROM dpu_credit_offer "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f"AND application_unique_id = {self._sql_literal(self.selected_application_unique_id)} "
            "ORDER BY created_at DESC LIMIT 1"
        )
        return self.db_executor.execute_sql(sql) or self.selected_application_unique_id

    def _resolve_platform_seller_id(self, platform_seller_id: Optional[str] = None) -> Optional[str]:
        """解析 SP 状态更新所需 seller_id。

        优先级：
        1. 前端显式传入的 platform_seller_id
        2. 当前 session 中已生成的 selling_partner_id
        3. 根据当前 merchant_id 从 dpu_manual_offer 反查最新 platform_seller_id
        """
        if platform_seller_id and str(platform_seller_id).strip():
            return str(platform_seller_id).strip()

        if self.generated_selling_partner_id:
            return self.generated_selling_partner_id

        if not self.merchant_id:
            return None

        sql = (
            "SELECT platform_seller_id "
            "FROM dpu_seller_center.dpu_manual_offer "
            f"WHERE merchant_id = '{self.merchant_id}' "
            "AND platform_seller_id IS NOT NULL "
            "AND platform_seller_id != '' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        seller_id = self.db_executor.execute_sql(sql)
        if seller_id:
            self.generated_selling_partner_id = seller_id
            log.info(f"根据 merchant_id 自动查询到 platform_seller_id: {seller_id}")
        return seller_id

    @staticmethod
    def _sql_literal(value: Optional[str]) -> str:
        """Quote a small SQL literal for legacy execute_sql helpers."""
        if value is None:
            return "NULL"
        return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"

    def _calculate_repayment_amounts(
        self,
        drawdown_info: Dict[str, Any],
        principal_amount: float,
    ) -> tuple[float, float, float, Dict[str, float]]:
        """Calculate repayment interest, total amount, and remaining principal from dpu_drawdown."""
        raw_outstanding_amount = drawdown_info.get("outstanding_amount")
        raw_total_interest_rate = drawdown_info.get("total_interest_rate")
        if raw_outstanding_amount is None:
            raise ValueError("dpu_drawdown.outstanding_amount为空，无法计算还款剩余本金")
        if raw_total_interest_rate is None:
            raise ValueError("dpu_drawdown.total_interest_rate为空，无法计算interestPaidAmount")

        db_outstanding_amount = float(raw_outstanding_amount)
        annual_interest_rate = float(raw_total_interest_rate)
        if annual_interest_rate > 1:
            annual_interest_rate = annual_interest_rate / 100

        remaining_outstanding_amount = round(db_outstanding_amount - float(principal_amount), 2)
        if remaining_outstanding_amount < 0:
            log.warning(
                "本次还款本金大于数据库未结清金额 | principal=%s | db_outstanding_amount=%s，剩余未结清金额按0处理",
                principal_amount,
                db_outstanding_amount,
            )
            remaining_outstanding_amount = 0.00

        monthly_interest_rate = annual_interest_rate / 12
        interest_amount = round(db_outstanding_amount * monthly_interest_rate, 2)
        total_amount = round(float(principal_amount) + interest_amount, 2)
        log.info(
            "还款金额计算 | db_outstanding_amount=%.2f | annual_interest_rate=%.6f | monthly_interest_rate=%.6f | "
            "interestPaidAmount=%.2f | principalPaidAmount=%.2f | outstandingAmount=%.2f",
            db_outstanding_amount,
            annual_interest_rate,
            monthly_interest_rate,
            interest_amount,
            float(principal_amount),
            remaining_outstanding_amount,
        )
        return interest_amount, total_amount, remaining_outstanding_amount, {
            "db_outstanding_amount": db_outstanding_amount,
            "annual_interest_rate": annual_interest_rate,
            "monthly_interest_rate": monthly_interest_rate,
            "interest_base_amount": db_outstanding_amount,
            "interest_periods_per_year": 12,
        }

    def _get_drawdown_info_for_repayment(self, loan_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        resolved_loan_code = str(loan_code or "").strip()
        if not resolved_loan_code:
            if not self.merchant_id:
                return None
            sql = f"""
                SELECT merchant_id, loan_id, lender_loan_id, lender_drawdown_id,
                       outstanding_amount, total_interest_rate
                FROM dpu_drawdown
                WHERE merchant_id = {self._sql_literal(self.merchant_id)}
                ORDER BY created_at DESC LIMIT 1
            """
            return self.db_executor.execute_query(sql)

        if not self.merchant_id:
            return None
        sql = f"""
            SELECT merchant_id, loan_id, lender_loan_id, lender_drawdown_id, outstanding_amount, total_interest_rate
            FROM dpu_drawdown
            WHERE merchant_id = {self._sql_literal(self.merchant_id)}
            AND (
                lender_loan_id = {self._sql_literal(resolved_loan_code)}
                OR lender_drawdown_id = {self._sql_literal(resolved_loan_code)}
            )
            ORDER BY created_at DESC LIMIT 1
        """
        drawdown_info = self.db_executor.execute_query(sql)
        if drawdown_info:
            log.info("根据还款选中 loanCode 查询放款记录成功: %s", drawdown_info)
        else:
            log.error("未查询到指定放款记录 | merchant_id=%s | loanCode=%s", self.merchant_id, resolved_loan_code)
        return drawdown_info

    def _wait_for_drawdown_submitted(
        self,
        lender_approved_offer_id: str,
        timeout_seconds: int = 90,
        interval_seconds: int = 3,
    ) -> dict:
        """Wait until dpu_drawdown has a loan_id and status=SUBMITTED."""
        if not self.merchant_id:
            return {"success": False, "error": "merchant_id为空，无法等待dpu_drawdown放款记录"}
        if not lender_approved_offer_id:
            return {"success": False, "error": "lender_approved_offer_id为空，无法等待dpu_drawdown放款记录"}

        deadline = time.time() + timeout_seconds
        attempt = 0
        last_row = None
        poll_history = []
        while time.time() < deadline:
            attempt += 1
            sql = f"""
                SELECT id, merchant_id, loan_id, lender_loan_id, lender_drawdown_id,
                       lender_approved_offer_id, status, created_at, updated_at
                FROM dpu_drawdown
                WHERE merchant_id = {self._sql_literal(self.merchant_id)}
                  AND lender_approved_offer_id = {self._sql_literal(lender_approved_offer_id)}
                ORDER BY created_at DESC LIMIT 1
            """
            row = self.db_executor.execute_query(sql)
            last_row = row
            loan_id = str((row or {}).get("loan_id") or "").strip()
            row_status = str((row or {}).get("status") or "").strip().upper()
            poll_history.append({
                "attempt": attempt,
                "found": bool(row),
                "loan_id": loan_id or None,
                "status": row_status or None,
                "lender_loan_id": (row or {}).get("lender_loan_id"),
                "updated_at": (row or {}).get("updated_at"),
            })
            if row and loan_id and row_status == "SUBMITTED":
                return {
                    "success": True,
                    "row": row,
                    "poll_attempts": attempt,
                    "poll_history": poll_history[-10:],
                }
            time.sleep(interval_seconds)

        return {
            "success": False,
            "error": "等待窗口内未拿到 dpu_drawdown.loan_id 且 status=SUBMITTED，暂不调用 disbursement.completed",
            "retryable": True,
            "retry_after": 20,
            "merchant_id": self.merchant_id,
            "lender_approved_offer_id": lender_approved_offer_id,
            "last_row": last_row,
            "poll_attempts": attempt,
            "poll_history": poll_history[-10:],
        }

    @staticmethod
    def _lookup_user_token(db_executor: DatabaseExecutor, phone_number: str) -> str:
        """Fetch the latest user token when signup does not return one."""
        if not phone_number:
            return ""
        try:
            columns = db_executor.execute_query_all("SHOW COLUMNS FROM dpu_users LIKE 'token'")
        except Exception as exc:
            log.warning(f"Lookup user token schema check skipped: {exc}")
            return ""
        if not columns:
            log.warning("Lookup user token skipped: dpu_users.token column is not available in this environment")
            return ""
        phone_literal = WebDPUMockService._sql_literal(phone_number)
        sql = (
            "SELECT token FROM dpu_users "
            f"WHERE phone_number = {phone_literal} "
            "AND token IS NOT NULL AND token != '' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        try:
            token = db_executor.execute_sql(sql)
        except Exception as exc:
            log.warning(f"Lookup user token skipped: {exc}")
            return ""
        return str(token or "").strip()

    def _login_user_token(self, currency: str = "USD", funder_resource: str = "HSBC") -> str:
        """Login the current test user and cache the returned token on this session."""
        phone_number = str(self.phone_number or "").strip()
        if not phone_number:
            return ""
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency or self.preferred_currency or "USD",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource or "HSBC",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/149.0.0.0 Safari/537.36",
        }
        verification_payload = {
            "areaCode": "+86",
            "code": "LOGIN_VERIFICATION",
            "phone": phone_number,
        }
        verification_url = f"{self.api_config.base_url}/dpu-user/auth/verification-codes"
        login_url = f"{self.api_config.base_url}/dpu-user/auth/login"
        try:
            verification_resp = http_requests.post(
                verification_url,
                json=verification_payload,
                headers=headers,
                timeout=30,
            )
            verification_body = {}
            try:
                verification_body = verification_resp.json()
            except ValueError:
                verification_body = {}
            if verification_resp.status_code == 429:
                log.warning("登录验证码触发被限流，尝试使用短信表中最近验证码继续登录")
            else:
                verification_resp.raise_for_status()
            if verification_resp.status_code != 429 and verification_body and verification_body.get("isSuccess") is False:
                log.warning(f"登录验证码触发失败: {verification_body}")
                return ""
            verification_code = fetch_sms_verification_code(self.db_executor, phone_number, timeout=30, interval=1)
            login_payload = {
                "areaCode": "+86",
                "phone": phone_number,
                "code": verification_code,
                "password": "Aa11111111..",
            }
            login_resp = http_requests.post(login_url, json=login_payload, headers=headers, timeout=30)
            login_resp.raise_for_status()
            login_body = login_resp.json()
            token = str(((login_body.get("data") or {}).get("token")) or "").strip()
            if token:
                self.session_user_token = token
                return token
            log.warning(f"登录成功但未返回 token: {login_body}")
        except Exception as exc:
            log.warning(f"登录获取用户 token 失败: {exc}")
        return ""

    def _build_manual_offer_lookup_sql(
        self,
        selling_partner_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        ready_only: bool = True,
        limit: int = 1,
    ) -> Optional[str]:
        conditions = []
        if selling_partner_id:
            conditions.append(f"platform_seller_id = {self._sql_literal(selling_partner_id)}")
        if merchant_id:
            conditions.append(f"merchant_id = {self._sql_literal(merchant_id)}")
        if not conditions:
            return None

        ready_condition = (
            "AND idempotency_key IS NOT NULL AND idempotency_key != '' "
            "AND platform_offer_id IS NOT NULL AND platform_offer_id != '' "
            if ready_only
            else ""
        )
        return (
            "SELECT id, merchant_id, merchant_account_id, platform_seller_id, "
            "idempotency_key, platform_offer_id, send_status, created_at, updated_at "
            "FROM dpu_seller_center.dpu_manual_offer "
            f"WHERE ({' OR '.join(conditions)}) "
            f"{ready_condition}"
            "ORDER BY created_at DESC "
            f"LIMIT {int(limit)}"
        )

    def _get_manual_offer_debug_rows(
        self,
        selling_partner_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
    ) -> list[dict]:
        sql = self._build_manual_offer_lookup_sql(
            selling_partner_id=selling_partner_id,
            merchant_id=merchant_id,
            ready_only=False,
            limit=5,
        )
        if not sql:
            return []

        try:
            rows = self.db_executor.execute_query_all(sql)
        except AttributeError:
            first_row = self.db_executor.execute_query(sql)
            rows = [first_row] if first_row else []
        except Exception as exc:
            return [{"error": str(exc), "sql": sql}]

        if not rows:
            return []
        if isinstance(rows, dict):
            return [rows]
        return rows

    def _wait_for_manual_offer(
        self,
        selling_partner_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        timeout_seconds: int = 30,
        interval_seconds: int = 2,
    ) -> Optional[dict]:
        """Poll dpu_manual_offer until platform_offer_id and idempotency_key are available."""
        deadline = time.time() + timeout_seconds
        sql = self._build_manual_offer_lookup_sql(
            selling_partner_id=selling_partner_id,
            merchant_id=merchant_id,
            ready_only=True,
            limit=1,
        )
        if not sql:
            return None

        while time.time() < deadline:
            row = self.db_executor.execute_query(sql)
            if row and row.get("idempotency_key") and row.get("platform_offer_id"):
                resolved_seller_id = row.get("platform_seller_id")
                if resolved_seller_id:
                    self.generated_selling_partner_id = resolved_seller_id
                return row
            time.sleep(interval_seconds)
        return None

    def _resolve_latest_platform_offer_id(self, offer_id: Optional[str] = None) -> Optional[str]:
        cleaned_offer_id = str(offer_id or "").strip()
        if cleaned_offer_id and not (cleaned_offer_id.startswith("${") and cleaned_offer_id.endswith("}")):
            return cleaned_offer_id
        manual_offer_row = self._wait_for_manual_offer(
            selling_partner_id=self.generated_selling_partner_id,
            merchant_id=self.merchant_id,
            timeout_seconds=5,
            interval_seconds=1,
        )
        if manual_offer_row and manual_offer_row.get("platform_offer_id"):
            return manual_offer_row.get("platform_offer_id")
        return None

    @staticmethod
    def _normalize_shop_performance_custom_sql(custom_sql: str, resolved_offer_id: str) -> tuple[bool, str, str]:
        sql = (custom_sql or "").strip()
        if not sql:
            return False, "", "custom_sql is empty"
        sql = sql.replace("${platform_offer_id}", resolved_offer_id).replace("${offer_id}", resolved_offer_id).strip()
        if sql.endswith(";"):
            sql = sql[:-1].strip()
        if ";" in sql:
            return False, sql, "自定义 SQL 只允许单条 UPDATE，不能包含多个语句。"
        compact_sql = re.sub(r"\s+", " ", sql).strip()
        if not re.match(r"^UPDATE\s+(?:dpu_seller_center\.)?dpu_3pl_shop_performance\s+SET\s+", compact_sql, re.IGNORECASE):
            return False, sql, "自定义 SQL 必须更新 dpu_seller_center.dpu_3pl_shop_performance 表。"
        if not re.search(r"\sWHERE\s+", compact_sql, re.IGNORECASE):
            return False, sql, "自定义 SQL 必须包含 WHERE 条件。"
        if not re.search(r"\bamazon_3pl_offer_id\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s,)]+)", compact_sql, re.IGNORECASE):
            return False, sql, "WHERE 条件必须使用 amazon_3pl_offer_id = '...' 限定目标店铺。"
        forbidden = re.search(r"\b(DELETE|INSERT|REPLACE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|CALL)\b", compact_sql, re.IGNORECASE)
        if forbidden:
            return False, sql, f"自定义 SQL 不允许包含 {forbidden.group(1).upper()}。"
        runtime_offer_literal = "'" + str(resolved_offer_id).replace("\\", "\\\\").replace("'", "''") + "'"
        sql = re.sub(
            r"(\bamazon_3pl_offer_id\s*=\s*)(?:'[^']*'|\"[^\"]*\"|[^\s,)]+)",
            lambda match: f"{match.group(1)}{runtime_offer_literal}",
            sql,
            count=1,
            flags=re.IGNORECASE,
        )
        return True, sql, ""

    @staticmethod
    def _explain_shop_performance_sql_error(exc: Exception) -> dict:
        raw_error = str(exc)
        lower_error = raw_error.lower()
        suggestions = []
        if "unknown column" in lower_error:
            suggestions.append("字段名不存在或拼写不一致，请核对 dpu_3pl_shop_performance 表字段。")
        if "syntax" in lower_error:
            suggestions.append("SQL 语法错误，请确认 SET 字段之间使用英文逗号，字符串使用单引号。")
        if "doesn't exist" in lower_error or "does not exist" in lower_error:
            suggestions.append("表名或库名不存在，请确认使用 dpu_seller_center.dpu_3pl_shop_performance。")
        if "truncated" in lower_error or "incorrect" in lower_error:
            suggestions.append("字段类型不匹配，请确认数值字段不要传字符串，枚举/日期格式符合数据库要求。")
        if "safe update" in lower_error:
            suggestions.append("数据库开启安全更新，请确认 WHERE amazon_3pl_offer_id 条件存在且能命中记录。")
        if not suggestions:
            suggestions.append("请先检查 SQL 是否为单条 UPDATE，WHERE 是否限定 amazon_3pl_offer_id，字段名和字段类型是否正确。")
        return {
            "title": "数据库执行失败解析",
            "raw_error": raw_error,
            "suggestions": suggestions,
        }

    def update_shop_performance_cny_boost_web(
        self,
        offer_id: Optional[str] = None,
        access_type: Optional[str] = None,
        custom_sql: Optional[str] = None,
    ) -> dict:
        resolved_offer_id = self._resolve_latest_platform_offer_id(offer_id)
        if not resolved_offer_id:
            return {
                "success": False,
                "error": "未查询到前置步骤生成的 platform_offer_id，无法更新 dpu_3pl_shop_performance",
                "offer_id": offer_id,
            }

        offer_literal = self._sql_literal(resolved_offer_id)
        normalized_access = (access_type or "").strip() or "webank准入ccb准入"
        if custom_sql and custom_sql.strip():
            is_valid, sql, validation_error = self._normalize_shop_performance_custom_sql(custom_sql, resolved_offer_id)
            if not is_valid:
                return {
                    "success": False,
                    "error": validation_error,
                    "ai_error_analysis": {
                        "title": "自定义 SQL 校验失败",
                        "raw_error": validation_error,
                        "suggestions": [
                            "请提供单条 UPDATE dpu_seller_center.dpu_3pl_shop_performance 语句。",
                            "必须包含 WHERE amazon_3pl_offer_id = '真实 offerId'。",
                        ],
                    },
                    "offer_id": resolved_offer_id,
                    "custom_sql": sql,
                }
            try:
                self.db_executor.execute_sql(sql)
            except Exception as exc:  # noqa: BLE001 - return analysis to UI
                return {
                    "success": False,
                    "error": f"自定义 SQL 执行失败: {exc}",
                    "ai_error_analysis": self._explain_shop_performance_sql_error(exc),
                    "offer_id": resolved_offer_id,
                    "custom_sql": sql,
                }
            return {
                "success": True,
                "offer_id": resolved_offer_id,
                "access_type": normalized_access,
                "access_type_effective": False,
                "custom_sql_used": True,
                "updated_table": "dpu_3pl_shop_performance",
                "where": {"amazon_3pl_offer_id": resolved_offer_id},
                "sql": sql.strip(),
            }

        # webank准入ccb准入：正常准入的经营数据（大额，真实店铺数据，NORMAL）。
        webank_set_clause = """SET amazon_tenure = 666125, last13week_fba_rate = 427.5,
    last3month_fba_inventory_value = 1200000, latest_fba_inventory_value = 11500000,
    primary_category_last3month_sales_value = 5400010,
    marketplace_country = 'US', primary_product_category = 'Electronics',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 400000000, year1_disbursements_value = 380000000,
    year2_sales_value = 350000000, year2_disbursements_value = 320000000,
    quarter1_sales_value = 60500000, quarter2_sales_value = 51000000,
    quarter3_sales_value = 46500000, quarter4_sales_value = 43500000,
    quarter5_sales_value = 40500000, quarter6_sales_value = 37500000,
    quarter7_sales_value = 35000000, quarter8_sales_value = 32500000,
    quarter1_disbursements_value = 57500000, quarter2_disbursements_value = 48000000,
    quarter3_disbursements_value = 44000000, quarter4_disbursements_value = 41000000,
    quarter5_disbursements_value = 38000000, quarter6_disbursements_value = 35000000,
    quarter7_disbursements_value = 32500000, quarter8_disbursements_value = 30000000,
    month1_sales_value = 22000000, month2_sales_value = 20000000,
    month3_sales_value = 18500000, month4_sales_value = 17000000,
    month5_sales_value = 15500000, month6_sales_value = 14500000,
    month7_sales_value = 13500000, month8_sales_value = 12500000,
    month9_sales_value = 11500000, month10_sales_value = 10750000,
    month11_sales_value = 10000000, month12_sales_value = 9500000,
    month1_disbursements_value = 21000000, month2_disbursements_value = 19000000,
    month3_disbursements_value = 17500000, month4_disbursements_value = 16000000,
    month5_disbursements_value = 15000000, month6_disbursements_value = 14000000,
    month7_disbursements_value = 13000000, month8_disbursements_value = 12000000,
    month9_disbursements_value = 11000000, month10_disbursements_value = 10000000,
    month11_disbursements_value = 9500000, month12_disbursements_value = 9000000,
    week1_sales_value = 6250037.5, week2_sales_value = 5900000,
    week3_sales_value = 5500000, week4_sales_value = 5250000,
    week5_sales_value = 4900000, week6_sales_value = 4600000,
    week1_disbursements_value = 5925010, week2_disbursements_value = 5250000,
    week3_disbursements_value = 4900000, week4_disbursements_value = 5600000,
    week5_disbursements_value = 4750000, week6_disbursements_value = 4400000,
    ttm_orders = 76000, ttm_cancellations = 120, ttm_returns = 450,
    ttm_feedback = 3200, ttm_negative_feedback = 90,
    ttm_late_shipments = 80, ttm_order_defects = 30, ttm_seller_warnings = 5"""

        # webank不准入ccb准入：webank 通过、ccb 不通过（小额、真实店铺数据、NORMAL）。
        webank_only_set_clause = """SET amazon_tenure = 98915, last13week_fba_rate = 500,
    last3month_fba_inventory_value = 304274, latest_fba_inventory_value = 3318967,
    primary_category_last3month_sales_value = 32400,
    marketplace_country = 'US', primary_product_category = 'Home Improvement',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 250000, year1_disbursements_value = 225000,
    year2_sales_value = 0, year2_disbursements_value = 0,
    quarter1_sales_value = 192631, quarter2_sales_value = 219249,
    quarter3_sales_value = 54549.5, quarter4_sales_value = 0,
    quarter5_sales_value = 0, quarter6_sales_value = 0,
    quarter7_sales_value = 0, quarter8_sales_value = 0,
    quarter1_disbursements_value = 185000, quarter2_disbursements_value = 205000,
    quarter3_disbursements_value = 52000, quarter4_disbursements_value = 0,
    quarter5_disbursements_value = 0, quarter6_disbursements_value = 0,
    quarter7_disbursements_value = 0, quarter8_disbursements_value = 0,
    month1_sales_value = 87312.5, month2_sales_value = 31739.5,
    month3_sales_value = 58134.5, month4_sales_value = 83489,
    month5_sales_value = 88879, month6_sales_value = 40981.5,
    month7_sales_value = 45176.5, month8_sales_value = 29368.5,
    month9_sales_value = 1348.5, month10_sales_value = 0,
    month11_sales_value = 0, month12_sales_value = 0,
    month1_disbursements_value = 84000, month2_disbursements_value = 30500,
    month3_disbursements_value = 56000, month4_disbursements_value = 80000,
    month5_disbursements_value = 85000, month6_disbursements_value = 39000,
    month7_disbursements_value = 43000, month8_disbursements_value = 28000,
    month9_disbursements_value = 1500, month10_disbursements_value = 0,
    month11_disbursements_value = 0, month12_disbursements_value = 0,
    week1_sales_value = 20341, week2_sales_value = 37790,
    week3_sales_value = 11643, week4_sales_value = 17538.5,
    week5_sales_value = 16195.5, week6_sales_value = 3248,
    week1_disbursements_value = 19500, week2_disbursements_value = 36000,
    week3_disbursements_value = 11000, week4_disbursements_value = 16500,
    week5_disbursements_value = 15000, week6_disbursements_value = 3000,
    ttm_orders = 17750, ttm_cancellations = 10, ttm_returns = 160,
    ttm_feedback = 10, ttm_negative_feedback = 0,
    ttm_late_shipments = 0, ttm_order_defects = 0, ttm_seller_warnings = 0"""

        # webank不准入ccb不准入：两侧都拒绝（year1_disbursements 异常偏低=40000000）。
        both_fail_set_clause = """SET amazon_tenure = 666125, last13week_fba_rate = 427.5,
    last3month_fba_inventory_value = 1200000, latest_fba_inventory_value = 11500000,
    primary_category_last3month_sales_value = 5400010,
    marketplace_country = 'US', primary_product_category = 'Electronics',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 400000000, year1_disbursements_value = 40000000,
    year2_sales_value = 350000000, year2_disbursements_value = 320000000,
    quarter1_sales_value = 60500000, quarter2_sales_value = 51000000,
    quarter3_sales_value = 46500000, quarter4_sales_value = 43500000,
    quarter5_sales_value = 40500000, quarter6_sales_value = 37500000,
    quarter7_sales_value = 35000000, quarter8_sales_value = 32500000,
    quarter1_disbursements_value = 57500000, quarter2_disbursements_value = 48000000,
    quarter3_disbursements_value = 44000000, quarter4_disbursements_value = 41000000,
    quarter5_disbursements_value = 38000000, quarter6_disbursements_value = 35000000,
    quarter7_disbursements_value = 32500000, quarter8_disbursements_value = 30000000,
    month1_sales_value = 22000000, month2_sales_value = 20000000,
    month3_sales_value = 18500000, month4_sales_value = 17000000,
    month5_sales_value = 15500000, month6_sales_value = 14500000,
    month7_sales_value = 13500000, month8_sales_value = 12500000,
    month9_sales_value = 11500000, month10_sales_value = 10750000,
    month11_sales_value = 10000000, month12_sales_value = 9500000,
    month1_disbursements_value = 21000000, month2_disbursements_value = 19000000,
    month3_disbursements_value = 17500000, month4_disbursements_value = 16000000,
    month5_disbursements_value = 15000000, month6_disbursements_value = 14000000,
    month7_disbursements_value = 13000000, month8_disbursements_value = 12000000,
    month9_disbursements_value = 11000000, month10_disbursements_value = 10000000,
    month11_disbursements_value = 9500000, month12_disbursements_value = 9000000,
    week1_sales_value = 6250037.5, week2_sales_value = 5900000,
    week3_sales_value = 5500000, week4_sales_value = 5250000,
    week5_sales_value = 4900000, week6_sales_value = 4600000,
    week1_disbursements_value = 5925010, week2_disbursements_value = 5250000,
    week3_disbursements_value = 4900000, week4_disbursements_value = 5600000,
    week5_disbursements_value = 4750000, week6_disbursements_value = 4400000,
    ttm_orders = 76000, ttm_cancellations = 120, ttm_returns = 450,
    ttm_feedback = 3200, ttm_negative_feedback = 90,
    ttm_late_shipments = 80, ttm_order_defects = 30, ttm_seller_warnings = 5"""


        # 店铺7：销售/放款均为大额健康数据，但账号状态 SUSPENDED（封停）。
        # 真实店铺样本，放款按真实月/周值，seller_status=SUSPENDED 是与其它分支的本质区别。
        suspended_high_sales_set_clause = """SET amazon_tenure = 666125, last13week_fba_rate = 427.5,
    last3month_fba_inventory_value = 1200000, latest_fba_inventory_value = 11500000,
    primary_category_last3month_sales_value = 5400010,
    marketplace_country = 'US', primary_product_category = 'Electronics',
    seller_status = 'SUSPENDED', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 400000000, year1_disbursements_value = 380000000,
    year2_sales_value = 350000000, year2_disbursements_value = 320000000,
    quarter1_sales_value = 60500000, quarter2_sales_value = 51000000,
    quarter3_sales_value = 46500000, quarter4_sales_value = 43500000,
    quarter5_sales_value = 40500000, quarter6_sales_value = 37500000,
    quarter7_sales_value = 35000000, quarter8_sales_value = 32500000,
    quarter1_disbursements_value = 57500000, quarter2_disbursements_value = 48000000,
    quarter3_disbursements_value = 44000000, quarter4_disbursements_value = 41000000,
    quarter5_disbursements_value = 38000000, quarter6_disbursements_value = 35000000,
    quarter7_disbursements_value = 32500000, quarter8_disbursements_value = 30000000,
    month1_sales_value = 22000000, month2_sales_value = 20000000,
    month3_sales_value = 18500000, month4_sales_value = 17000000,
    month5_sales_value = 15500000, month6_sales_value = 14500000,
    month7_sales_value = 13500000, month8_sales_value = 12500000,
    month9_sales_value = 11500000, month10_sales_value = 10750000,
    month11_sales_value = 10000000, month12_sales_value = 9500000,
    month1_disbursements_value = 21000000, month2_disbursements_value = 19000000,
    month3_disbursements_value = 17500000, month4_disbursements_value = 16000000,
    month5_disbursements_value = 15000000, month6_disbursements_value = 14000000,
    month7_disbursements_value = 13000000, month8_disbursements_value = 12000000,
    month9_disbursements_value = 11000000, month10_disbursements_value = 10000000,
    month11_disbursements_value = 9500000, month12_disbursements_value = 9000000,
    week1_sales_value = 6250037.5, week2_sales_value = 5900000,
    week3_sales_value = 5500000, week4_sales_value = 5250000,
    week5_sales_value = 4900000, week6_sales_value = 4600000,
    week1_disbursements_value = 5925010, week2_disbursements_value = 5250000,
    week3_disbursements_value = 4900000, week4_disbursements_value = 5600000,
    week5_disbursements_value = 4750000, week6_disbursements_value = 4400000,
    ttm_orders = 76000, ttm_cancellations = 120, ttm_returns = 450,
    ttm_feedback = 3200, ttm_negative_feedback = 90,
    ttm_late_shipments = 80, ttm_order_defects = 30, ttm_seller_warnings = 5"""


        # 店铺5：大额健康数据，seller_status=NORMAL（与店铺7数值一致，仅状态不同）。真实店铺样本。
        shop5_set_clause = """SET amazon_tenure = 666125, last13week_fba_rate = 427.5,
    last3month_fba_inventory_value = 1200000, latest_fba_inventory_value = 11500000,
    primary_category_last3month_sales_value = 5400010,
    marketplace_country = 'US', primary_product_category = 'Electronics',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 400000000, year1_disbursements_value = 380000000,
    year2_sales_value = 350000000, year2_disbursements_value = 320000000,
    quarter1_sales_value = 60500000, quarter2_sales_value = 51000000,
    quarter3_sales_value = 46500000, quarter4_sales_value = 43500000,
    quarter5_sales_value = 40500000, quarter6_sales_value = 37500000,
    quarter7_sales_value = 35000000, quarter8_sales_value = 32500000,
    quarter1_disbursements_value = 57500000, quarter2_disbursements_value = 48000000,
    quarter3_disbursements_value = 44000000, quarter4_disbursements_value = 41000000,
    quarter5_disbursements_value = 38000000, quarter6_disbursements_value = 35000000,
    quarter7_disbursements_value = 32500000, quarter8_disbursements_value = 30000000,
    month1_sales_value = 22000000, month2_sales_value = 20000000,
    month3_sales_value = 18500000, month4_sales_value = 17000000,
    month5_sales_value = 15500000, month6_sales_value = 14500000,
    month7_sales_value = 13500000, month8_sales_value = 12500000,
    month9_sales_value = 11500000, month10_sales_value = 10750000,
    month11_sales_value = 10000000, month12_sales_value = 9500000,
    month1_disbursements_value = 21000000, month2_disbursements_value = 19000000,
    month3_disbursements_value = 17500000, month4_disbursements_value = 16000000,
    month5_disbursements_value = 15000000, month6_disbursements_value = 14000000,
    month7_disbursements_value = 13000000, month8_disbursements_value = 12000000,
    month9_disbursements_value = 11000000, month10_disbursements_value = 10000000,
    month11_disbursements_value = 9500000, month12_disbursements_value = 9000000,
    week1_sales_value = 6250037.5, week2_sales_value = 5900000,
    week3_sales_value = 5500000, week4_sales_value = 5250000,
    week5_sales_value = 4900000, week6_sales_value = 4600000,
    week1_disbursements_value = 5925010, week2_disbursements_value = 5250000,
    week3_disbursements_value = 4900000, week4_disbursements_value = 5600000,
    week5_disbursements_value = 4750000, week6_disbursements_value = 4400000,
    ttm_orders = 76000, ttm_cancellations = 120, ttm_returns = 450,
    ttm_feedback = 3200, ttm_negative_feedback = 90,
    ttm_late_shipments = 80, ttm_order_defects = 30, ttm_seller_warnings = 5"""


        # 店铺6：小额、近一年有销售、seller_status=NORMAL。真实店铺样本（销售逐月衰减到0）。
        shop6_set_clause = """SET amazon_tenure = 98915, last13week_fba_rate = 500,
    last3month_fba_inventory_value = 304274, latest_fba_inventory_value = 3318967,
    primary_category_last3month_sales_value = 32400,
    marketplace_country = 'US', primary_product_category = 'Home Improvement',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 932859, year1_disbursements_value = 900000,
    year2_sales_value = 0, year2_disbursements_value = 0,
    quarter1_sales_value = 192631, quarter2_sales_value = 219249,
    quarter3_sales_value = 54549.5, quarter4_sales_value = 0,
    quarter5_sales_value = 0, quarter6_sales_value = 0,
    quarter7_sales_value = 0, quarter8_sales_value = 0,
    quarter1_disbursements_value = 185000, quarter2_disbursements_value = 205000,
    quarter3_disbursements_value = 52000, quarter4_disbursements_value = 0,
    quarter5_disbursements_value = 0, quarter6_disbursements_value = 0,
    quarter7_disbursements_value = 0, quarter8_disbursements_value = 0,
    month1_sales_value = 87312.5, month2_sales_value = 31739.5,
    month3_sales_value = 58134.5, month4_sales_value = 83489,
    month5_sales_value = 88879, month6_sales_value = 40981.5,
    month7_sales_value = 45176.5, month8_sales_value = 29368.5,
    month9_sales_value = 1348.5, month10_sales_value = 0,
    month11_sales_value = 0, month12_sales_value = 0,
    month1_disbursements_value = 84000, month2_disbursements_value = 30500,
    month3_disbursements_value = 56000, month4_disbursements_value = 80000,
    month5_disbursements_value = 85000, month6_disbursements_value = 39000,
    month7_disbursements_value = 43000, month8_disbursements_value = 28000,
    month9_disbursements_value = 1500, month10_disbursements_value = 0,
    month11_disbursements_value = 0, month12_disbursements_value = 0,
    week1_sales_value = 20341, week2_sales_value = 37790,
    week3_sales_value = 11643, week4_sales_value = 17538.5,
    week5_sales_value = 16195.5, week6_sales_value = 3248,
    week1_disbursements_value = 19500, week2_disbursements_value = 36000,
    week3_disbursements_value = 11000, week4_disbursements_value = 16500,
    week5_disbursements_value = 15000, week6_disbursements_value = 3000,
    ttm_orders = 17750, ttm_cancellations = 10, ttm_returns = 160,
    ttm_feedback = 10, ttm_negative_feedback = 0,
    ttm_late_shipments = 0, ttm_order_defects = 0, ttm_seller_warnings = 0"""


        # 店铺9：与店铺5数值一致，但 year1_disbursements=40000000（放款/销售严重不匹配），NORMAL。
        shop9_set_clause = """SET amazon_tenure = 666125, last13week_fba_rate = 427.5,
    last3month_fba_inventory_value = 1200000, latest_fba_inventory_value = 11500000,
    primary_category_last3month_sales_value = 5400010,
    marketplace_country = 'US', primary_product_category = 'Electronics',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 400000000, year1_disbursements_value = 40000000,
    year2_sales_value = 350000000, year2_disbursements_value = 320000000,
    quarter1_sales_value = 60500000, quarter2_sales_value = 51000000,
    quarter3_sales_value = 46500000, quarter4_sales_value = 43500000,
    quarter5_sales_value = 40500000, quarter6_sales_value = 37500000,
    quarter7_sales_value = 35000000, quarter8_sales_value = 32500000,
    quarter1_disbursements_value = 57500000, quarter2_disbursements_value = 48000000,
    quarter3_disbursements_value = 44000000, quarter4_disbursements_value = 41000000,
    quarter5_disbursements_value = 38000000, quarter6_disbursements_value = 35000000,
    quarter7_disbursements_value = 32500000, quarter8_disbursements_value = 30000000,
    month1_sales_value = 22000000, month2_sales_value = 20000000,
    month3_sales_value = 18500000, month4_sales_value = 17000000,
    month5_sales_value = 15500000, month6_sales_value = 14500000,
    month7_sales_value = 13500000, month8_sales_value = 12500000,
    month9_sales_value = 11500000, month10_sales_value = 10750000,
    month11_sales_value = 10000000, month12_sales_value = 9500000,
    month1_disbursements_value = 21000000, month2_disbursements_value = 19000000,
    month3_disbursements_value = 17500000, month4_disbursements_value = 16000000,
    month5_disbursements_value = 15000000, month6_disbursements_value = 14000000,
    month7_disbursements_value = 13000000, month8_disbursements_value = 12000000,
    month9_disbursements_value = 11000000, month10_disbursements_value = 10000000,
    month11_disbursements_value = 9500000, month12_disbursements_value = 9000000,
    week1_sales_value = 6250037.5, week2_sales_value = 5900000,
    week3_sales_value = 5500000, week4_sales_value = 5250000,
    week5_sales_value = 4900000, week6_sales_value = 4600000,
    week1_disbursements_value = 5925010, week2_disbursements_value = 5250000,
    week3_disbursements_value = 4900000, week4_disbursements_value = 5600000,
    week5_disbursements_value = 4750000, week6_disbursements_value = 4400000,
    ttm_orders = 76000, ttm_cancellations = 120, ttm_returns = 450,
    ttm_feedback = 3200, ttm_negative_feedback = 90,
    ttm_late_shipments = 80, ttm_order_defects = 30, ttm_seller_warnings = 5"""


        # 店铺11：与店铺5数值一致（大额、真实放款、NORMAL），但 ttm_returns=40000（退货异常）。
        shop11_set_clause = """SET amazon_tenure = 666125, last13week_fba_rate = 427.5,
    last3month_fba_inventory_value = 1200000, latest_fba_inventory_value = 11500000,
    primary_category_last3month_sales_value = 5400010,
    marketplace_country = 'US', primary_product_category = 'Electronics',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 400000000, year1_disbursements_value = 380000000,
    year2_sales_value = 350000000, year2_disbursements_value = 320000000,
    quarter1_sales_value = 60500000, quarter2_sales_value = 51000000,
    quarter3_sales_value = 46500000, quarter4_sales_value = 43500000,
    quarter5_sales_value = 40500000, quarter6_sales_value = 37500000,
    quarter7_sales_value = 35000000, quarter8_sales_value = 32500000,
    quarter1_disbursements_value = 57500000, quarter2_disbursements_value = 48000000,
    quarter3_disbursements_value = 44000000, quarter4_disbursements_value = 41000000,
    quarter5_disbursements_value = 38000000, quarter6_disbursements_value = 35000000,
    quarter7_disbursements_value = 32500000, quarter8_disbursements_value = 30000000,
    month1_sales_value = 22000000, month2_sales_value = 20000000,
    month3_sales_value = 18500000, month4_sales_value = 17000000,
    month5_sales_value = 15500000, month6_sales_value = 14500000,
    month7_sales_value = 13500000, month8_sales_value = 12500000,
    month9_sales_value = 11500000, month10_sales_value = 10750000,
    month11_sales_value = 10000000, month12_sales_value = 9500000,
    month1_disbursements_value = 21000000, month2_disbursements_value = 19000000,
    month3_disbursements_value = 17500000, month4_disbursements_value = 16000000,
    month5_disbursements_value = 15000000, month6_disbursements_value = 14000000,
    month7_disbursements_value = 13000000, month8_disbursements_value = 12000000,
    month9_disbursements_value = 11000000, month10_disbursements_value = 10000000,
    month11_disbursements_value = 9500000, month12_disbursements_value = 9000000,
    week1_sales_value = 6250037.5, week2_sales_value = 5900000,
    week3_sales_value = 5500000, week4_sales_value = 5250000,
    week5_sales_value = 4900000, week6_sales_value = 4600000,
    week1_disbursements_value = 5925010, week2_disbursements_value = 5250000,
    week3_disbursements_value = 4900000, week4_disbursements_value = 5600000,
    week5_disbursements_value = 4750000, week6_disbursements_value = 4400000,
    ttm_orders = 76000, ttm_cancellations = 120, ttm_returns = 40000,
    ttm_feedback = 3200, ttm_negative_feedback = 90,
    ttm_late_shipments = 80, ttm_order_defects = 30, ttm_seller_warnings = 5"""


        # 店铺12：与店铺6数值一致（小额、衰减、NORMAL），但 ttm_returns=10000（退货异常）。
        shop12_set_clause = """SET amazon_tenure = 98915, last13week_fba_rate = 500,
    last3month_fba_inventory_value = 304274, latest_fba_inventory_value = 3318967,
    primary_category_last3month_sales_value = 32400,
    marketplace_country = 'US', primary_product_category = 'Home Improvement',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 932859, year1_disbursements_value = 900000,
    year2_sales_value = 0, year2_disbursements_value = 0,
    quarter1_sales_value = 192631, quarter2_sales_value = 219249,
    quarter3_sales_value = 54549.5, quarter4_sales_value = 0,
    quarter5_sales_value = 0, quarter6_sales_value = 0,
    quarter7_sales_value = 0, quarter8_sales_value = 0,
    quarter1_disbursements_value = 185000, quarter2_disbursements_value = 205000,
    quarter3_disbursements_value = 52000, quarter4_disbursements_value = 0,
    quarter5_disbursements_value = 0, quarter6_disbursements_value = 0,
    quarter7_disbursements_value = 0, quarter8_disbursements_value = 0,
    month1_sales_value = 87312.5, month2_sales_value = 31739.5,
    month3_sales_value = 58134.5, month4_sales_value = 83489,
    month5_sales_value = 88879, month6_sales_value = 40981.5,
    month7_sales_value = 45176.5, month8_sales_value = 29368.5,
    month9_sales_value = 1348.5, month10_sales_value = 0,
    month11_sales_value = 0, month12_sales_value = 0,
    month1_disbursements_value = 84000, month2_disbursements_value = 30500,
    month3_disbursements_value = 56000, month4_disbursements_value = 80000,
    month5_disbursements_value = 85000, month6_disbursements_value = 39000,
    month7_disbursements_value = 43000, month8_disbursements_value = 28000,
    month9_disbursements_value = 1500, month10_disbursements_value = 0,
    month11_disbursements_value = 0, month12_disbursements_value = 0,
    week1_sales_value = 20341, week2_sales_value = 37790,
    week3_sales_value = 11643, week4_sales_value = 17538.5,
    week5_sales_value = 16195.5, week6_sales_value = 3248,
    week1_disbursements_value = 19500, week2_disbursements_value = 36000,
    week3_disbursements_value = 11000, week4_disbursements_value = 16500,
    week5_disbursements_value = 15000, week6_disbursements_value = 3000,
    ttm_orders = 17750, ttm_cancellations = 10, ttm_returns = 10000,
    ttm_feedback = 10, ttm_negative_feedback = 0,
    ttm_late_shipments = 0, ttm_order_defects = 0, ttm_seller_warnings = 0"""


        # 店铺14：小额、逐月单调递减、近一年销售、NORMAL。真实店铺样本。
        shop14_set_clause = """SET amazon_tenure = 98915, last13week_fba_rate = 500,
    last3month_fba_inventory_value = 304274, latest_fba_inventory_value = 3318967,
    primary_category_last3month_sales_value = 28500,
    marketplace_country = 'US', primary_product_category = 'Home Improvement',
    seller_status = 'NORMAL', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 90000, year1_disbursements_value = 75000,
    year2_sales_value = 0, year2_disbursements_value = 0,
    quarter1_sales_value = 28500, quarter2_sales_value = 24000,
    quarter3_sales_value = 19500, quarter4_sales_value = 15000,
    quarter5_sales_value = 0, quarter6_sales_value = 0,
    quarter7_sales_value = 0, quarter8_sales_value = 0,
    quarter1_disbursements_value = 25500, quarter2_disbursements_value = 21000,
    quarter3_disbursements_value = 16500, quarter4_disbursements_value = 12000,
    quarter5_disbursements_value = 0, quarter6_disbursements_value = 0,
    quarter7_disbursements_value = 0, quarter8_disbursements_value = 0,
    month1_sales_value = 10000, month2_sales_value = 9500,
    month3_sales_value = 9000, month4_sales_value = 8500,
    month5_sales_value = 8000, month6_sales_value = 7500,
    month7_sales_value = 7000, month8_sales_value = 6500,
    month9_sales_value = 6000, month10_sales_value = 5500,
    month11_sales_value = 5000, month12_sales_value = 4500,
    month1_disbursements_value = 9000, month2_disbursements_value = 8500,
    month3_disbursements_value = 8000, month4_disbursements_value = 7500,
    month5_disbursements_value = 7000, month6_disbursements_value = 6500,
    month7_disbursements_value = 6000, month8_disbursements_value = 5500,
    month9_disbursements_value = 5000, month10_disbursements_value = 4500,
    month11_disbursements_value = 4000, month12_disbursements_value = 3500,
    week1_sales_value = 2500, week2_sales_value = 2400,
    week3_sales_value = 2300, week4_sales_value = 2200,
    week5_sales_value = 2100, week6_sales_value = 2000,
    week1_disbursements_value = 2200, week2_disbursements_value = 2100,
    week3_disbursements_value = 2000, week4_disbursements_value = 1900,
    week5_disbursements_value = 1800, week6_disbursements_value = 1700,
    ttm_orders = 17750, ttm_cancellations = 10, ttm_returns = 160,
    ttm_feedback = 10, ttm_negative_feedback = 0,
    ttm_late_shipments = 0, ttm_order_defects = 0, ttm_seller_warnings = 0"""


        # 店铺16：与店铺14数值一致（小额、逐月递减），但 seller_status=SUSPENDED（封停）。
        shop16_set_clause = """SET amazon_tenure = 98915, last13week_fba_rate = 500,
    last3month_fba_inventory_value = 304274, latest_fba_inventory_value = 3318967,
    primary_category_last3month_sales_value = 28500,
    marketplace_country = 'US', primary_product_category = 'Home Improvement',
    seller_status = 'SUSPENDED', report_card_data_date = '2026-07-22 00:00:00',
    year1_sales_value = 90000, year1_disbursements_value = 75000,
    year2_sales_value = 0, year2_disbursements_value = 0,
    quarter1_sales_value = 28500, quarter2_sales_value = 24000,
    quarter3_sales_value = 19500, quarter4_sales_value = 15000,
    quarter5_sales_value = 0, quarter6_sales_value = 0,
    quarter7_sales_value = 0, quarter8_sales_value = 0,
    quarter1_disbursements_value = 25500, quarter2_disbursements_value = 21000,
    quarter3_disbursements_value = 16500, quarter4_disbursements_value = 12000,
    quarter5_disbursements_value = 0, quarter6_disbursements_value = 0,
    quarter7_disbursements_value = 0, quarter8_disbursements_value = 0,
    month1_sales_value = 10000, month2_sales_value = 9500,
    month3_sales_value = 9000, month4_sales_value = 8500,
    month5_sales_value = 8000, month6_sales_value = 7500,
    month7_sales_value = 7000, month8_sales_value = 6500,
    month9_sales_value = 6000, month10_sales_value = 5500,
    month11_sales_value = 5000, month12_sales_value = 4500,
    month1_disbursements_value = 9000, month2_disbursements_value = 8500,
    month3_disbursements_value = 8000, month4_disbursements_value = 7500,
    month5_disbursements_value = 7000, month6_disbursements_value = 6500,
    month7_disbursements_value = 6000, month8_disbursements_value = 5500,
    month9_disbursements_value = 5000, month10_disbursements_value = 4500,
    month11_disbursements_value = 4000, month12_disbursements_value = 3500,
    week1_sales_value = 2500, week2_sales_value = 2400,
    week3_sales_value = 2300, week4_sales_value = 2200,
    week5_sales_value = 2100, week6_sales_value = 2000,
    week1_disbursements_value = 2200, week2_disbursements_value = 2100,
    week3_disbursements_value = 2000, week4_disbursements_value = 1900,
    week5_disbursements_value = 1800, week6_disbursements_value = 1700,
    ttm_orders = 17750, ttm_cancellations = 10, ttm_returns = 160,
    ttm_feedback = 10, ttm_negative_feedback = 0,
    ttm_late_shipments = 0, ttm_order_defects = 0, ttm_seller_warnings = 0"""

        if normalized_access == "webank不准入ccb准入":
            set_clause = webank_only_set_clause
        elif normalized_access == "webank准入ccb不准入":
            # 与 webank准入ccb准入 相同，仅 ttm_returns 提高到 40000（退货异常触发 ccb 拒绝）。
            set_clause = webank_set_clause.replace(
                "ttm_returns = 450", "ttm_returns = 40000"
            )
        elif normalized_access == "webank不准入ccb不准入":
            set_clause = both_fail_set_clause
        elif normalized_access == "店铺7":
            set_clause = suspended_high_sales_set_clause
        elif normalized_access == "店铺5":
            set_clause = shop5_set_clause
        elif normalized_access == "店铺6":
            set_clause = shop6_set_clause
        elif normalized_access == "店铺8":
            # 店铺8 与店铺6 数据一致，仅名称不同（复用 shop6_set_clause）。
            set_clause = shop6_set_clause
        elif normalized_access == "店铺9":
            set_clause = shop9_set_clause
        elif normalized_access == "店铺10":
            # 店铺10 与店铺7 数据一致，仅名称不同（复用 suspended_high_sales_set_clause）。
            set_clause = suspended_high_sales_set_clause
        elif normalized_access == "店铺11":
            set_clause = shop11_set_clause
        elif normalized_access == "店铺12":
            set_clause = shop12_set_clause
        elif normalized_access == "店铺13":
            # 店铺13 与店铺7 数据一致，仅名称不同（复用 suspended_high_sales_set_clause）。
            set_clause = suspended_high_sales_set_clause
        elif normalized_access == "店铺14":
            set_clause = shop14_set_clause
        elif normalized_access == "店铺15":
            # 店铺15 与店铺14 数据一致，仅名称不同（复用 shop14_set_clause）。
            set_clause = shop14_set_clause
        elif normalized_access == "店铺16":
            set_clause = shop16_set_clause
        else:
            # webank准入ccb准入 共用大额准入数据
            set_clause = webank_set_clause

        sql = (
            "UPDATE dpu_3pl_shop_performance\n"
            f"{set_clause}\n"
            f"WHERE amazon_3pl_offer_id = {offer_literal}\n"
        )
        self.db_executor.execute_sql(sql)
        return {
            "success": True,
            "offer_id": resolved_offer_id,
            "access_type": normalized_access,
            "updated_table": "dpu_3pl_shop_performance",
            "where": {"amazon_3pl_offer_id": resolved_offer_id},
            "sql": sql.strip(),
        }

    @classmethod
    def list_shop_performance_builtin_presets_web(cls) -> list[dict]:
        access_types = [
            "webank准入ccb准入",
            "webank不准入ccb准入",
            "webank准入ccb不准入",
            "webank不准入ccb不准入",
            "店铺5",
            "店铺6",
            "店铺7",
            "店铺8",
            "店铺9",
            "店铺10",
            "店铺11",
            "店铺12",
            "店铺13",
            "店铺14",
            "店铺15",
            "店铺16",
        ]
        placeholder_offer_id = "__PLATFORM_OFFER_ID__"

        class _NoopDatabase:
            @staticmethod
            def execute_sql(sql: str):
                return None

        service = cls.__new__(cls)
        service.db_executor = _NoopDatabase()
        service._resolve_latest_platform_offer_id = lambda offer_id=None: placeholder_offer_id

        presets = []
        for access_type in access_types:
            result = service.update_shop_performance_cny_boost_web(
                offer_id=placeholder_offer_id,
                access_type=access_type,
            )
            sql = str(result.get("sql") or "").replace(
                f"'{placeholder_offer_id}'",
                "'${platform_offer_id}'",
            )
            presets.append({
                "name": access_type,
                "custom_sql": sql,
            })
        return presets

    def check_kiosk_seller_id_web(self, offer_id=None, timeout_seconds=300, interval_seconds=5):
        resolved_offer_id = self._resolve_latest_platform_offer_id(offer_id)
        if not resolved_offer_id:
            return {"success": False, "error": "no offerId from previous steps", "offer_id": offer_id}
        sql = ("SELECT seller_id FROM dpu_kiosk_query_record "
               f"WHERE offer_id = {self._sql_literal(resolved_offer_id)} LIMIT 1")
        deadline = time.time() + max(int(timeout_seconds), interval_seconds)
        attempts = 0
        while True:
            attempts += 1
            try:
                seller_id = self.db_executor.execute_sql(sql)
            except Exception as exc:
                return {"success": False, "error": f"query dpu_kiosk_query_record failed: {exc}",
                        "offer_id": resolved_offer_id, "sql": sql, "attempts": attempts}
            if seller_id is not None and str(seller_id).strip():
                return {"success": True, "offer_id": resolved_offer_id, "seller_id": str(seller_id).strip(),
                        "queried_table": "dpu_kiosk_query_record", "sql": sql, "attempts": attempts}
            if time.time() >= deadline:
                return {"success": False, "retryable": True, "retry_after": 15,
                        "error": "timeout: dpu_kiosk_query_record has no seller_id for this offer yet",
                        "offer_id": resolved_offer_id, "sql": sql, "attempts": attempts}
            time.sleep(max(int(interval_seconds), 1))

    def ensure_application_context_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        tier_code: Optional[int] = None,
        offer_id: Optional[str] = None,
    ) -> dict:
        """Create or bind the FP application row for the scenario's application step."""
        application_unique_id = self.application_unique_id
        limit_application_unique_id = self.dpu_limit_application_id
        lender_approved_offer_id = self.credit_offer_lender_approved_offer_id

        bootstrap_steps = []
        if not application_unique_id:
            bootstrap_result = self._create_fp_application(
                journey=journey,
                currency=currency,
                funder_resource=funder_resource,
                tier_code=tier_code,
                offer_id=offer_id,
            )
            bootstrap_steps = bootstrap_result.get("steps", [])
            if not bootstrap_result.get("success"):
                return {
                    "success": False,
                    "merchant_id": self.merchant_id,
                    "application_unique_id": None,
                    "limit_application_unique_id": None,
                    "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id,
                    "journey": journey,
                    "currency": currency or self.preferred_currency,
                    "funder_resource": funder_resource or "FUNDPARK",
                    "error": bootstrap_result.get("error", "创建申请单上下文失败"),
                    "steps": bootstrap_steps,
                }
            application_unique_id = bootstrap_result.get("application_unique_id") or self.application_unique_id
            limit_application_unique_id = bootstrap_result.get("limit_application_unique_id") or self.dpu_limit_application_id
            lender_approved_offer_id = bootstrap_result.get("lender_approved_offer_id") or self.credit_offer_lender_approved_offer_id
        elif not self.selected_application_unique_id:
            self.select_application(application_unique_id)

        return {
            "success": bool(application_unique_id),
            "merchant_id": self.merchant_id,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": limit_application_unique_id,
            "lender_approved_offer_id": lender_approved_offer_id,
            "journey": journey,
            "currency": currency or self.preferred_currency,
            "funder_resource": funder_resource or "FUNDPARK",
            "error": None if application_unique_id else "未查询到 dpu_application.application_unique_id",
            "steps": bootstrap_steps,
        }

    def _ensure_credit_offer_lender_approved_offer_id(
        self,
        application_unique_id: Optional[str] = None,
        approved_amount: Optional[float] = None,
    ) -> Optional[str]:
        """Ensure approved-offer uses a lender id that exists on dpu_credit_offer."""
        resolved_application_unique_id = application_unique_id or self.application_unique_id
        if not self.merchant_id or not resolved_application_unique_id:
            return None

        existing_id = self.credit_offer_lender_approved_offer_id
        if existing_id:
            return existing_id

        generated_id = self.lender_approved_offer_id or f"lender-{resolved_application_unique_id}"
        currency = self.preferred_currency or "USD"
        amount_sql = ""
        if approved_amount is not None:
            amount_sql = (
                f"approved_limit_currency={self._sql_literal(currency)}, "
                f"approved_limit_amount={round(float(approved_amount), 2):.2f}, "
            )

        self.db_executor.execute_sql(
            "UPDATE dpu_seller_center.dpu_credit_offer "
            "SET "
            f"lender_approved_offer_id=COALESCE(NULLIF(lender_approved_offer_id, ''), {self._sql_literal(generated_id)}), "
            f"{amount_sql}"
            "updated_at=NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f"AND application_unique_id = {self._sql_literal(resolved_application_unique_id)}"
        )
        return self.credit_offer_lender_approved_offer_id

    def _create_fp_application(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        tier_code: Optional[int] = None,
        offer_id: Optional[str] = None,
    ) -> dict:
        """Create only the application row owned by the UI's create-application step."""
        if not self.merchant_id:
            return {"success": False, "error": "未获取到 merchant_id，无法创建申请单上下文", "steps": []}

        steps = []
        auth_token = str(self.session_user_token or "").strip()
        if not auth_token:
            auth_token = self._lookup_user_token(self.db_executor, self.phone_number)
        if not auth_token:
            return {"success": False, "error": "未查询到用户 token，无法创建申请单上下文", "steps": steps}

        product_currency = currency or self.preferred_currency or "USD"
        resource = funder_resource or "FUNDPARK"
        resolved_tier_code = tier_code if tier_code is not None else ("1" if journey == "200K" else "2")
        common_headers = {
            "Authorization": f"Bearer {auth_token}",
            "content-type": "application/json",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": resource,
            "product-currency": product_currency,
            "referer": f"{self._build_portal_base_url(self.db_executor.env)}/",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        }

        create_payload = {"tierCode": resolved_tier_code, "tierSnapshotValue": 0}
        if offer_id is not None:
            create_payload["offerId"] = offer_id
        create_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/create"
        create_result = self._do_post_custom_with_retry(
            create_url,
            "创建申请单",
            json_data=create_payload,
            headers=common_headers,
            attempts=3,
            require_json_data=True,
        )
        created_application_unique_id = None
        if create_result.get("success"):
            create_payload_result = create_result.get("response_json") or {}
            if isinstance(create_payload_result, dict):
                created_application_unique_id = create_payload_result.get("data")
        steps.append({
            "step": "fundpark-application.create",
            "endpoint": create_url,
            "payload": create_payload,
            "result": create_result,
        })
        if not create_result.get("success"):
            return {"success": False, "error": "fundpark-application/create 失败", "steps": steps}

        application_unique_id = self._wait_for_application_unique_id(timeout_seconds=120) or created_application_unique_id
        if not application_unique_id:
            return {"success": False, "error": "等待 dpu_application.application_unique_id 超时", "steps": steps}

        self.select_application(application_unique_id)
        return {
            "success": True,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": self.dpu_limit_application_id,
            "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id,
            "currency": product_currency,
            "funder_resource": resource,
            "tier_code": resolved_tier_code,
            "steps": steps,
        }

    def _bootstrap_fp_application_context(self, journey: Optional[str] = None) -> dict:
        """Run the remaining FP application preparation needed before tail webhooks."""
        steps = []
        for runner in (
            self.submit_fp_business_profile_web,
            self.submit_fp_director_info_web,
            self.select_fp_offer_limit_web,
            self.activate_fp_offer_quote_web,
            self.link_fp_sp_3pl_shops_web,
            self.run_fp_scheduled_tasks_and_poll_submitted_web,
        ):
            result = runner(journey)
            steps.extend(result.get("steps", []))
            if not result.get("success"):
                result["steps"] = steps
                return result
        return {
            "success": True,
            "application_unique_id": self.application_unique_id,
            "limit_application_unique_id": self.dpu_limit_application_id,
            "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id,
            "steps": steps,
        }

    def _application_headers_or_error(
        self,
        steps: list,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> tuple[Optional[dict], Optional[dict]]:
        application_unique_id = self.application_unique_id
        if not application_unique_id:
            create_result = self._create_fp_application(journey=None)
            steps.extend(create_result.get("steps", []))
            if not create_result.get("success"):
                return None, create_result
            application_unique_id = create_result.get("application_unique_id") or self.application_unique_id
        self.select_application(application_unique_id)

        auth_token = str(self.session_user_token or "").strip()
        if not auth_token:
            auth_token = self._lookup_user_token(self.db_executor, self.phone_number)
        if not auth_token:
            return None, {"success": False, "error": "未查询到用户 token，无法准备申请单上下文", "steps": steps}

        return {
            "Authorization": f"Bearer {auth_token}",
            "content-type": "application/json",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource or "FUNDPARK",
            "product-currency": currency or self.preferred_currency or "USD",
            "referer": f"{self._build_portal_base_url(self.db_executor.env)}/",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        }, None

    def _upload_dowsure_asset(
        self,
        asset: str,
        common_headers: Optional[dict],
        image_template_id: Optional[str] = None,
    ) -> dict:
        """把仓库内的 DOWSURE 证件图上传到当前环境的 dpu-file 网关，返回 objectKey + url。

        用当前 session 的鉴权头（common_headers 里的 Authorization）上传，所以自动落到
        当前环境（uat 传 uat、reg 传 reg），全环境自适应。同一 (env, asset) 在进程内只
        上传一次，结果缓存复用。失败抛 RuntimeError，让上层步骤明确报错。
        """
        env = self.db_executor.env
        selected_template_id = str(image_template_id or "").strip()
        if selected_template_id.startswith("builtin:"):
            selected_template_id = ""

        filename = ""
        content_type = "image/png"
        file_data = None
        source_version = "builtin"
        if selected_template_id:
            from web.services.audit_store import audit_store

            try:
                template_id = int(selected_template_id)
            except ValueError as exc:
                raise RuntimeError(f"图片模板 ID 无效: {selected_template_id}") from exc
            image_template = audit_store.get_company_image_template(template_id)
            if not image_template:
                raise RuntimeError(f"图片模板不存在: {selected_template_id}")
            if image_template.get("image_type") != asset:
                raise RuntimeError(
                    f"图片模板类型不匹配: 需要 {asset}，实际 {image_template.get('image_type')}"
                )
            filename = str(image_template.get("filename") or "image.png")
            content_type = str(image_template.get("content_type") or "image/png")
            file_data = image_template.get("file_data")
            source_version = f"{selected_template_id}:{image_template.get('updated_at', '')}"

        cache_key = (env, asset, source_version)
        cached = self._dowsure_asset_cache.get(cache_key)
        if cached and cached.get("file_key"):
            return cached

        file_path = None
        if file_data is None:
            filename = self._DOWSURE_ASSET_FILES.get(asset)
            if not filename:
                raise RuntimeError(f"未知的 DOWSURE 证件图: {asset}")
            file_path = self._DOWSURE_ASSET_DIR / filename
            if not file_path.is_file():
                raise RuntimeError(f"仓库缺少证件图文件: {file_path}")

        upload_url = f"{self.api_config.base_url}/dpu-file/files/upload/addFile"
        # 复用申请单鉴权头，但去掉 content-type，交给 requests 生成 multipart boundary。
        upload_headers = {k: v for k, v in (common_headers or {}).items() if k.lower() != "content-type"}
        try:
            if file_data is not None:
                resp = http_requests.post(
                    upload_url,
                    headers=upload_headers,
                    files={"files": (filename, file_data, content_type)},
                    timeout=60,
                )
            else:
                with open(file_path, "rb") as fh:
                    resp = http_requests.post(
                        upload_url,
                        headers=upload_headers,
                        files={"files": (filename, fh, content_type)},
                        timeout=60,
                    )
        except http_requests.exceptions.RequestException as exc:
            raise RuntimeError(f"上传 {asset} 到 {upload_url} 失败: {exc}")
        if resp.status_code >= 400:
            raise RuntimeError(f"上传 {asset} 返回 HTTP {resp.status_code}: {(resp.text or '')[:300]}")
        try:
            payload = resp.json()
        except Exception:
            raise RuntimeError(f"上传 {asset} 响应非 JSON: {(resp.text or '')[:300]}")

        file_key = self._extract_upload_object_key(payload)
        if not file_key:
            raise RuntimeError(f"上传 {asset} 未解析出 objectKey: {json.dumps(payload, ensure_ascii=False)[:300]}")
        url = self._extract_upload_url(payload) or (
            f"{self.api_config.base_url.split('//')[-1]}"  # 占位，仅在无 url 时退化
        )
        result = {
            "file_key": file_key,
            "url": url or "",
            "filename": filename,
            "content_type": content_type,
        }
        self._dowsure_asset_cache[cache_key] = result
        return result

    @staticmethod
    def _extract_upload_object_key(payload) -> str:
        key_names = ("objectKey", "fileKey", "object_key", "file_key", "key")

        def _from_dict(d):
            for name in key_names:
                v = d.get(name)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return ""

        if isinstance(payload, dict):
            direct = _from_dict(payload)
            if direct:
                return direct
            data = payload.get("data")
            if isinstance(data, dict):
                nested = _from_dict(data)
                if nested:
                    return nested
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return _from_dict(data[0])
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return _from_dict(payload[0])
        return ""

    @staticmethod
    def _extract_upload_url(payload) -> str:
        url_names = ("url", "fileUrl", "thumbnailUrl", "presignedUrl")

        def _from_dict(d):
            for name in url_names:
                v = d.get(name)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return ""

        if isinstance(payload, dict):
            direct = _from_dict(payload)
            if direct:
                return direct
            data = payload.get("data")
            if isinstance(data, dict):
                return _from_dict(data)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return _from_dict(data[0])
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return _from_dict(payload[0])
        return ""

    def _build_business_info_payload(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        cn_name: Optional[str] = None,
        common_headers: Optional[dict] = None,
        company_template: Optional[dict] = None,
        business_license_image_id: Optional[str] = None,
    ) -> dict:
        if (currency or self.preferred_currency or "").upper() == "USD" and (funder_resource or "").upper() == "HSBC":
            # DMF (HSBC + USD) 注册场景下的邓白氏 business-info 提交。regNo 需要
            # 是 8 位数字且每次不同，避免后端按 reg 号判重导致失败。
            reg_no = f"{random.randint(10_000_000, 99_999_999)}"
            return {
                "isDraft": False,
                "data": {
                    "bizDetail": {
                        "enName": "Fshen Testing Co., Ltd.",
                        "cnName": "",
                        "regNo": reg_no,
                        "companyDate": "11/06/2026",
                        "country": "Hong Kong",
                        "countryCode": "HK",
                        "area": "CAUSEWAY BAY HK",
                        "areaCode": "00",
                        "applicationId": "",
                        "address": "Harbour Town 16F",
                        "mailAddressFlag": "Y",
                        "mailArea": None,
                        "mailAreaCode": "",
                        "mailCountry": "Hong Kong",
                        "mailCountryCode": "HK",
                        "mailOfficeAddress1": "",
                        "relationshipHsbcGroupFlag": "N",
                        "relationshipHsbcGroupCountry": "",
                        "relationshipHsbcGroupCountryCode": "",
                    },
                },
                "clear": True,
            }
        if (currency or self.preferred_currency or "").upper() == "CNY" and (funder_resource or "").upper() == "DOWSURE":
            # 运行时把仓库内营业执照图上传到当前环境，拿该环境的 objectKey（全环境自适应）。
            # 上传失败或拿不到鉴权头时，回落到 .env 里的固定 key，保证不中断流程。
            business_license_file_key = ""
            business_license_url = ""
            business_license_filename = ""
            try:
                uploaded = self._upload_dowsure_asset(
                    "business_license",
                    common_headers,
                    business_license_image_id,
                )
                business_license_file_key = uploaded.get("file_key", "")
                business_license_url = uploaded.get("url", "")
                business_license_filename = str(uploaded.get("filename") or "").strip()
            except Exception as exc:
                if business_license_image_id and not str(business_license_image_id).startswith("builtin:"):
                    raise
                log.warning("business_license 运行时上传失败，回落到 .env key: %s", exc)
            if not business_license_file_key:
                business_license_file_key = os.getenv("DOWSURE_CNY_BUSINESS_LICENSE_FILE_KEY", "").strip()
            if not business_license_file_key:
                raise RuntimeError("营业执照上传失败且未配置 DOWSURE_CNY_BUSINESS_LICENSE_FILE_KEY")
            if not business_license_url:
                business_license_url = os.getenv("DOWSURE_CNY_BUSINESS_LICENSE_URL", "").strip() or (
                    "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/"
                    f"{business_license_file_key}"
                )
            template = company_template if isinstance(company_template, dict) else {}
            effective_cn_name = str(template.get("cnName") or cn_name or "").strip() or "广州测试科技有限公司"
            # 记录本次 business-info 选择的公司名，供 director-info 自动跟随
            # （选了备用公司则套用「测近智」法人档）。
            self._dowsure_selected_company_cn_name = effective_cn_name
            # 企业地址跟随公司：备用公司→甘肃省兰州市盘快饺题路247号301，默认→广州市天河区测试路1号。
            is_backup_company = effective_cn_name == self._DOWSURE_BACKUP_COMPANY_CN_NAME
            default_business_address = "甘肃省兰州市盘快饺题路247号301" if is_backup_company else "广州市天河区测试路1号"
            business_address = str(template.get("address") or "").strip() or default_business_address
            # 注册号跟随公司：备用公司→914401000747111984，默认→91440101MA5D6YRJ0X。
            default_business_reg_no = "914401000747111984" if is_backup_company else "91440101MA5D6YRJ0X"
            business_reg_no = str(template.get("regNo") or "").strip() or default_business_reg_no
            contact_number = template.get("contactNumber") if isinstance(template.get("contactNumber"), dict) else {}
            return {
                "step": "2",
                "isDraft": False,
                "data": {
                    "bizDetail": {
                        "enName": str(template.get("enName") or ""),
                        "cnName": effective_cn_name,
                        "regNo": business_reg_no,
                        "contactNumber": {
                            "countryCode": str(contact_number.get("countryCode") or "+86"),
                            "number": self.phone_number,
                        },
                        "address": business_address,
                        "operationAddressFlag": template.get("operationAddressFlag") is not False,
                        "operationAddress": str(template.get("operationAddress") or ""),
                        "id": "bac1c4e04d86407c8927b1fe9e072859",
                        "businessDocName": (
                            business_license_filename
                            or str(template.get("businessDocName") or "营业执照.png")
                        ),
                        "businessLicenseFileKey": business_license_file_key,
                        "businessLicenseUrl": business_license_url,
                    },
                },
                "clear": False,
            }

        return {
            "step": "2",
            "isDraft": False,
            "data": {
                "bizDetail": {
                    "id": None,
                    "applicationId": None,
                    "enName": "Testing Co., Ltd.",
                    "cnName": "",
                    "regNo": "00000001",
                    "companyDate": None,
                    "country": None,
                    "countryCode": None,
                    "area": None,
                    "areaCode": None,
                    "address": None,
                    "mailAddressFlag": None,
                    "mailArea": None,
                    "mailAreaCode": None,
                    "mailCountry": None,
                    "mailCountryCode": None,
                    "mailOfficeAddress1": None,
                    "relationshipHsbcGroupFlag": None,
                    "relationshipHsbcGroupCountry": None,
                    "relationshipHsbcGroupCountryCode": None,
                    "companyType": None,
                    "registeredCountryCode": None,
                    "contactNumber": None,
                    "operationAddressFlag": None,
                    "operationAddress": None,
                },
                "bizInfo": {
                    "topBuyers": ["China", "Hong Kong", "Macao"],
                    "topSuppliers": ["China"],
                    "fundingCountry": "Hong Kong",
                    "industry": "Furniture",
                    "mainProducts": "Home Improvement",
                    "initWealth": ["savings"],
                    "fundSources": ["bizOperations"],
                    "ongoingWealth": ["operationProfit"],
                },
            },
            "clear": True,
        }

    def submit_fp_business_profile_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        cn_name: Optional[str] = None,
        company_template: Optional[dict] = None,
        business_license_image_id: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        business_info_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/business-info"
        business_info_payload = self._build_business_info_payload(
            currency,
            funder_resource,
            cn_name,
            common_headers,
            company_template,
            business_license_image_id,
        )
        business_info_result = self._do_post_custom(
            business_info_url,
            "提交 business-info",
            json_data=business_info_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.business-info",
            "endpoint": business_info_url,
            "payload": business_info_payload,
            "result": business_info_result,
        })
        if not business_info_result.get("success"):
            return {"success": False, "error": "business-info 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_fp_registration_documents_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """DMF (HSBC USD) 第 11 步：上传邓白氏企业资料（四个证照文档）。"""
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/submit-registration-documents"
        # 四个证照文件预先上传到 S3，objectKey 已固定。S3 签名 URL 会过期但
        # 服务端只校验 objectKey，签名串保持原始示例值即可。
        payload = {
            "certificateOfIncorporationDoc": {
                "name": "download.png",
                "objectKey": "uploads/default/default/default/file_20260630100615_230f0028ca0e.png",
                "thumbnailUrl": (
                    "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/uploads/default/default/default/"
                    "file_20260630100615_230f0028ca0e.png?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                    "&X-Amz-Date=20260630T020616Z&X-Amz-SignedHeaders=host&X-Amz-Expires=1799"
                    "&X-Amz-Credential=AKIAVYYKAJWB2OBVR4OJ%2F20260630%2Fap-east-1%2Fs3%2Faws4_request"
                    "&X-Amz-Signature=e949ea8be4f6d454e8141b255fc5cf3642d87118d7c2216402c12e9e602ae8a6"
                ),
                "thumbnailObjectKey": "uploads/default/default/default/file_20260630100615_230f0028ca0e.png",
            },
            "businessRegistrationCertificateDoc": {
                "name": "Business Registration Certificate@3x-DOOWuimI.png",
                "objectKey": "uploads/default/default/default/file_20260630100616_97c834bdefff.png",
                "thumbnailUrl": (
                    "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/uploads/default/default/default/"
                    "file_20260630100616_97c834bdefff.png?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                    "&X-Amz-Date=20260630T020616Z&X-Amz-SignedHeaders=host&X-Amz-Expires=1799"
                    "&X-Amz-Credential=AKIAVYYKAJWB2OBVR4OJ%2F20260630%2Fap-east-1%2Fs3%2Faws4_request"
                    "&X-Amz-Signature=10032cde3494f0375f75b26b1844854216bd7a1021cbcf7cd3037eb4c10bb8ea"
                ),
                "thumbnailObjectKey": "uploads/default/default/default/file_20260630100616_97c834bdefff.png",
            },
            "memorandumOfAssociationDoc": {
                "name": "Memorandum of Association@3x-B115gjvL.png",
                "objectKey": "uploads/default/default/default/file_20260630100617_2e49f3728282.png",
                "thumbnailUrl": (
                    "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/uploads/default/default/default/"
                    "file_20260630100617_2e49f3728282.png?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                    "&X-Amz-Date=20260630T020617Z&X-Amz-SignedHeaders=host&X-Amz-Expires=1799"
                    "&X-Amz-Credential=AKIAVYYKAJWB2OBVR4OJ%2F20260630%2Fap-east-1%2Fs3%2Faws4_request"
                    "&X-Amz-Signature=994748ebbbe2b748e0f2d8bd2f7482af1b2f44114e5f0fa8932aa5eea66c525a"
                ),
                "thumbnailObjectKey": "uploads/default/default/default/file_20260630100617_2e49f3728282.png",
            },
            "annualReturnDoc": {
                "name": "Annual Return@3x-Djw-EgXL.png",
                "objectKey": "uploads/default/default/default/file_20260630100618_ebbb56044e61.png",
                "thumbnailUrl": (
                    "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/uploads/default/default/default/"
                    "file_20260630100618_ebbb56044e61.png?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                    "&X-Amz-Date=20260630T020618Z&X-Amz-SignedHeaders=host&X-Amz-Expires=1800"
                    "&X-Amz-Credential=AKIAVYYKAJWB2OBVR4OJ%2F20260630%2Fap-east-1%2Fs3%2Faws4_request"
                    "&X-Amz-Signature=611954c8112c7bb8d20954856e9d36596a3e480d4d91b2106d47ee77ca294b37"
                ),
                "thumbnailObjectKey": "uploads/default/default/default/file_20260630100618_ebbb56044e61.png",
            },
        }
        result = self._do_post_custom(
            url,
            "提交 submit-registration-documents",
            json_data=payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.submit-registration-documents",
            "endpoint": url,
            "payload": payload,
            "result": result,
        })
        if not result.get("success"):
            return {"success": False, "error": "submit-registration-documents 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_fp_director_info_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        name_cn: Optional[str] = None,
        address_detail: Optional[str] = None,
        director_template: Optional[dict] = None,
        director_id_front_image_id: Optional[str] = None,
        director_id_back_image_id: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        director_info_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/director-info"
        director_info_payload = self._build_director_info_payload(
            currency,
            funder_resource,
            name_cn,
            address_detail,
            common_headers,
            director_template,
            director_id_front_image_id,
            director_id_back_image_id,
        )
        director_info_result = self._do_post_custom(
            director_info_url,
            "提交 director-info",
            json_data=director_info_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.director-info",
            "endpoint": director_info_url,
            "payload": director_info_payload,
            "result": director_info_result,
        })
        if not director_info_result.get("success"):
            return {"success": False, "error": "director-info 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def poll_dmf_application_ready_web(
        self,
        timeout_seconds: int = 300,
        interval_seconds: int = 5,
        use_latest_submitted_application: bool = False,
    ) -> dict:
        """DMF 第 15 步：轮询申请单到位状态。

        三个条件同时满足才算成功：
          1) dpu_application.application_status = 'SUBMITTED'
          2) dpu_application.sanction_status   = 'NOT_HIT'
          3) dpu_lender_shop_data_transmission.fund_application_id 有值
             （按 application_unique_id 关联，至少存在一行非空）
        超时则返回最近一次的实际取值，方便排查卡在哪里。
        """
        steps: list = []
        application_unique_id = self.application_unique_id or self.selected_application_unique_id
        submitted_application_sql = None
        selected_submitted_application_row = None
        if use_latest_submitted_application:
            merchant_id = self.merchant_id
            if not merchant_id:
                return {
                    "success": False,
                    "error": "当前 session 没有 merchant_id，无法查询最新 SUBMITTED 申请单",
                    "steps": steps,
                }
            submitted_application_sql = (
                "SELECT * FROM dpu_seller_center.dpu_application "
                f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
                "AND application_status = 'SUBMITTED' "
                "ORDER BY created_at DESC LIMIT 1"
            )

        if not application_unique_id and not use_latest_submitted_application:
            return {
                "success": False,
                "error": "当前 session 没有 application_unique_id，请先完成创建申请单步骤",
                "steps": steps,
            }

        deadline = time.time() + max(int(timeout_seconds), interval_seconds)
        attempts = 0
        app_status = sanction_status = fund_application_id = None
        history: list = []
        app_sql = fund_sql = ""

        while True:
            attempts += 1
            app_row = None
            fund_row = None
            if use_latest_submitted_application:
                try:
                    selected_submitted_application_row = self.db_executor.execute_query(submitted_application_sql)
                except Exception as exc:
                    history.append({"attempt": attempts, "error": f"最新 SUBMITTED dpu_application 查询失败: {exc}"})
                    selected_submitted_application_row = None
                submitted_application_unique_id = str(
                    (selected_submitted_application_row or {}).get("application_unique_id") or ""
                ).strip()
                if submitted_application_unique_id:
                    application_unique_id = submitted_application_unique_id
                    self.select_application(application_unique_id)
                else:
                    history.append({
                        "attempt": attempts,
                        "submitted_application_found": False,
                        "reason": "未查询到最新 application_status=SUBMITTED 的新申请单",
                    })

            if not application_unique_id:
                if time.time() >= deadline:
                    return {
                        "success": False,
                        "error": "轮询超时：未查询到最新 application_status=SUBMITTED 的新申请单",
                        "retryable": True,
                        "retry_after": 20,
                        "submitted_application_query_sql": submitted_application_sql,
                        "attempts": attempts,
                        "steps": steps,
                    }
                time.sleep(max(int(interval_seconds), 1))
                continue

            app_sql = (
                "SELECT application_status, sanction_status "
                "FROM dpu_seller_center.dpu_application "
                f"WHERE application_unique_id = {self._sql_literal(application_unique_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
            fund_sql = (
                "SELECT fund_application_id "
                "FROM dpu_seller_center.dpu_lender_shop_data_transmission "
                f"WHERE application_unique_id = {self._sql_literal(application_unique_id)} "
                "AND fund_application_id IS NOT NULL AND fund_application_id <> '' "
                "ORDER BY id DESC LIMIT 1"
            )
            try:
                app_row = self.db_executor.execute_query(app_sql)
            except Exception as exc:
                history.append({"attempt": attempts, "error": f"dpu_application 查询失败: {exc}"})
            try:
                fund_row = self.db_executor.execute_query(fund_sql)
            except Exception as exc:
                history.append({"attempt": attempts, "error": f"dpu_lender_shop_data_transmission 查询失败: {exc}"})

            app_status = (app_row or {}).get("application_status")
            sanction_status = (app_row or {}).get("sanction_status")
            fund_application_id = (fund_row or {}).get("fund_application_id")

            history.append({
                "attempt": attempts,
                "application_unique_id": application_unique_id,
                "use_latest_submitted_application": use_latest_submitted_application,
                "application_status": app_status,
                "sanction_status": sanction_status,
                "fund_application_id": fund_application_id,
            })

            ok = (
                str(app_status or "").upper() == "SUBMITTED"
                and str(sanction_status or "").upper() == "NOT_HIT"
                and bool(fund_application_id)
            )
            if ok:
                steps.append({
                    "step": "dmf.poll-application-ready",
                    "endpoint": "db: dpu_application + dpu_lender_shop_data_transmission",
                    "payload": {"application_unique_id": application_unique_id},
                    "result": {
                        "success": True,
                        "attempts": attempts,
                        "application_status": app_status,
                        "sanction_status": sanction_status,
                        "fund_application_id": fund_application_id,
                        "submitted_application_query_sql": submitted_application_sql,
                        "history_tail": history[-3:],
                    },
                })
                return {
                    "success": True,
                    "application_unique_id": application_unique_id,
                    "selected_new_application_unique_id": application_unique_id if use_latest_submitted_application else None,
                    "application_status": app_status,
                    "sanction_status": sanction_status,
                    "fund_application_id": fund_application_id,
                    "submitted_application_query_sql": submitted_application_sql,
                    "attempts": attempts,
                    "steps": steps,
                }

            if time.time() >= deadline:
                steps.append({
                    "step": "dmf.poll-application-ready",
                    "endpoint": "db: dpu_application + dpu_lender_shop_data_transmission",
                    "payload": {"application_unique_id": application_unique_id},
                    "result": {
                        "success": False,
                        "attempts": attempts,
                        "application_status": app_status,
                        "sanction_status": sanction_status,
                        "fund_application_id": fund_application_id,
                        "submitted_application_query_sql": submitted_application_sql,
                        "history_tail": history[-5:],
                    },
                })
                missing: list = []
                if str(app_status or "").upper() != "SUBMITTED":
                    missing.append(f"application_status={app_status!r} 未到 SUBMITTED")
                if str(sanction_status or "").upper() != "NOT_HIT":
                    missing.append(f"sanction_status={sanction_status!r} 未到 NOT_HIT")
                if not fund_application_id:
                    missing.append("fund_application_id 仍为空")
                return {
                    "success": False,
                    "error": "轮询超时：" + "；".join(missing or ["未知原因"]),
                    "retryable": True,
                    "retry_after": 20,
                    "application_unique_id": application_unique_id,
                    "selected_new_application_unique_id": application_unique_id if use_latest_submitted_application else None,
                    "application_status": app_status,
                    "sanction_status": sanction_status,
                    "fund_application_id": fund_application_id,
                    "submitted_application_query_sql": submitted_application_sql,
                    "attempts": attempts,
                    "steps": steps,
                }

            time.sleep(max(int(interval_seconds), 1))

    def refresh_and_esign_status_web(
        self,
        signed_amount: int = None,
        status: str = None,
    ) -> dict:
        """800K 场景 esign：先按 merchant_id 从 dpu_credit_offer 查最新的
        lender_approved_offer_id，再发送 esign webhook。

        为什么单独一个方法：`self.credit_offer_lender_approved_offer_id` 是
        property，走 `self.db_executor` 长连接，MySQL REPEATABLE READ 快照下
        看不到 re-approved-offer 后落库的新 dpu_credit_offer 记录，会一直把
        esign 挂到老 offer_id 上。这里显式开一个新短连接来绕过快照。
        """
        if signed_amount is None or status is None:
            return {"success": False, "error": "signed_amount / status 不能为空"}
        merchant_id = self.merchant_id
        if not merchant_id:
            return {"success": False, "error": "当前 session 没有 merchant_id"}

        env = self.db_executor.env
        fresh_offer_id: Optional[str] = None
        fresh_application_unique_id: Optional[str] = None
        try:
            with DatabaseExecutor(env=env) as db:
                row = db.execute_query(
                    "SELECT lender_approved_offer_id, application_unique_id "
                    "FROM dpu_seller_center.dpu_credit_offer "
                    f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
                    "AND lender_approved_offer_id IS NOT NULL "
                    "AND lender_approved_offer_id <> '' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
        except Exception as exc:  # noqa: BLE001 - report cleanly
            return {"success": False, "error": f"查询最新 dpu_credit_offer 失败: {exc}"}
        if row:
            fresh_offer_id = row.get("lender_approved_offer_id")
            fresh_application_unique_id = row.get("application_unique_id")
        if not fresh_offer_id:
            return {
                "success": False,
                "error": (
                    "未从 dpu_credit_offer 查询到最新 lender_approved_offer_id，"
                    "请确认 re-approved-offer 是否已落库"
                ),
                "merchant_id": merchant_id,
            }
        if fresh_application_unique_id:
            self.select_application(fresh_application_unique_id)

        data = self._build_common_webhook_data(
            "esign.completed",
            status,
            {
                "lenderApprovedOfferId": fresh_offer_id,
                "result": status,
                "signedLimit": {
                    "amount": round(float(signed_amount), 2),
                    "currency": self.preferred_currency,
                },
            },
        )
        result = self._do_post_webhook(data, "电子签状态")
        if isinstance(result, dict):
            result.update({
                "signed_amount": signed_amount,
                "status": status,
                "lender_approved_offer_id": fresh_offer_id,
                "application_unique_id": fresh_application_unique_id or self.application_unique_id,
                "refreshed_from_db": True,
            })
        return result

    def increase_esign_status_web(
        self,
        signed_amount: int = None,
        status: str = None,
    ) -> dict:
        """提额 esign：轮询最新 dpu_credit_offer，并确认旧 offer 已签约成功。"""
        if signed_amount is None or status is None:
            return {"success": False, "error": "signed_amount / status 不能为空"}
        merchant_id = self.merchant_id
        if not merchant_id:
            return {"success": False, "error": "当前 session 没有 merchant_id"}

        sql = (
            "SELECT * FROM dpu_seller_center.dpu_credit_offer "
            f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
            "ORDER BY created_at DESC"
        )
        timeout_seconds = 600
        interval_seconds = 3
        deadline = time.time() + timeout_seconds
        attempt = 0
        rows = []
        new_offer = {}
        old_offer = {}
        fresh_offer_id = ""
        fresh_application_unique_id = ""
        new_esign_status = ""
        old_esign_status = ""
        last_reason = ""
        poll_history = []

        while time.time() < deadline:
            attempt += 1
            try:
                with DatabaseExecutor(env=self.db_executor.env) as db:
                    rows = db.execute_query_all(sql)
            except Exception as exc:  # noqa: BLE001 - return clean operation failure
                return {
                    "success": False,
                    "error": f"查询 dpu_credit_offer 失败: {exc}",
                    "merchant_id": merchant_id,
                    "sql": sql,
                    "poll_attempts": attempt,
                }
            if isinstance(rows, dict):
                rows = [rows]
            rows = rows or []
            new_offer = rows[0] if len(rows) >= 1 else {}
            old_offer = rows[1] if len(rows) >= 2 else {}
            new_esign_status = str(new_offer.get("e_sign_status") or "").upper()
            old_esign_status = str(old_offer.get("e_sign_status") or "").upper()
            fresh_offer_id = str(new_offer.get("lender_approved_offer_id") or "").strip()
            fresh_application_unique_id = str(new_offer.get("application_unique_id") or "").strip()

            if len(rows) < 2:
                last_reason = f"dpu_credit_offer 记录不足 2 条，无法判断新旧提额 offer | count={len(rows)}"
            elif old_esign_status != "SUCCESS":
                last_reason = f"旧 credit offer e_sign_status 不是 SUCCESS | old_e_sign_status={old_esign_status or '-'}"
            elif new_esign_status == "SUCCESS":
                return {
                    "success": False,
                    "error": "最新提额 credit offer 的 e_sign_status 已经是 SUCCESS，说明该 offer 已签过，禁止重复发送 esign",
                    "merchant_id": merchant_id,
                    "sql": sql,
                    "poll_attempts": attempt,
                    "poll_history": poll_history[-10:],
                    "new_credit_offer": new_offer,
                    "old_credit_offer": old_offer,
                    "credit_offer_rows": rows[:5],
                }
            elif not fresh_offer_id:
                last_reason = "最新 dpu_credit_offer 缺少 lender_approved_offer_id"
            else:
                break

            poll_history.append({
                "attempt": attempt,
                "count": len(rows),
                "new_lender_approved_offer_id": new_offer.get("lender_approved_offer_id"),
                "new_application_unique_id": new_offer.get("application_unique_id"),
                "new_e_sign_status": new_offer.get("e_sign_status"),
                "old_lender_approved_offer_id": old_offer.get("lender_approved_offer_id"),
                "old_e_sign_status": old_offer.get("e_sign_status"),
                "reason": last_reason,
            })
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(interval_seconds, remaining))

        if not fresh_offer_id or len(rows) < 2 or old_esign_status != "SUCCESS":
            return {
                "success": False,
                "retryable": True,
                "error": f"等待提额 dpu_credit_offer 落库超时: {last_reason or '未满足继续条件'}",
                "merchant_id": merchant_id,
                "sql": sql,
                "timeout_seconds": timeout_seconds,
                "poll_attempts": attempt,
                "poll_history": poll_history[-10:],
                "new_credit_offer": new_offer,
                "old_credit_offer": old_offer,
                "credit_offer_rows": rows[:5],
            }
        if fresh_application_unique_id:
            self.select_application(fresh_application_unique_id)

        data = self._build_common_webhook_data(
            "esign.completed",
            status,
            {
                "lenderApprovedOfferId": fresh_offer_id,
                "result": status,
                "signedLimit": {
                    "amount": round(float(signed_amount), 2),
                    "currency": self.preferred_currency,
                },
            },
        )
        result = self._do_post_webhook(data, "提额电子签状态")
        if isinstance(result, dict):
            result.update({
                "increase_flow": True,
                "signed_amount": signed_amount,
                "status": status,
                "lender_approved_offer_id": fresh_offer_id,
                "application_unique_id": fresh_application_unique_id or self.application_unique_id,
                "old_lender_approved_offer_id": old_offer.get("lender_approved_offer_id"),
                "new_e_sign_status": new_offer.get("e_sign_status"),
                "old_e_sign_status": old_offer.get("e_sign_status"),
                "credit_offer_count": len(rows),
                "credit_offer_query_sql": sql,
                "poll_attempts": attempt,
                "poll_history": poll_history[-10:],
                "credit_offer_rows": rows[:5],
            })
        return result

    def activate_new_offer_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """800K 场景：re-approved-offer 之后，POST /credit-offer/activate-offer 激活新的 offer。"""
        steps: list = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/activate-offer"
        payload: dict = {}
        result = self._do_post_custom(
            url,
            "激活新的 offer",
            json_data=payload,
            headers=common_headers,
        )
        steps.append({
            "step": "credit-offer.activate-offer",
            "endpoint": url,
            "payload": payload,
            "result": result,
        })
        if not result.get("success"):
            return {"success": False, "error": "activate-offer 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def refresh_and_approved_offer_status_web(
        self,
        amount: int = None,
        status: str = None,
        failure_reason_index: int = None,
        rejection_reason: str = None,
    ) -> dict:
        """800K 场景：activate-additional-limit 之后会新落一条 dpu_application，
        这一步先强制从 DB 拉 SUBMITTED 的 application_unique_id，再走一次 approved-offer。

        MySQL 的 REPEATABLE READ 隔离级别下，session 里长连接会保留早前事务的快照，
        直接用 self.db_executor 查会一直读到旧的申请单号。这里显式开一个新的
        DatabaseExecutor 短连接跑
            SELECT application_unique_id FROM dpu_application
            WHERE merchant_id = %s AND application_status = 'SUBMITTED'
            ORDER BY created_at DESC LIMIT 1
        绕开会话快照，保证拿到 activate-additional-limit 新落的那条记录。
        """
        merchant_id = self.merchant_id
        if not merchant_id:
            return {
                "success": False,
                "error": "当前 session 没有 merchant_id，无法查询最新 application_unique_id",
            }
        env = self.db_executor.env
        fresh_id = None
        timeout_seconds = 600
        interval_seconds = 3
        deadline = time.time() + timeout_seconds
        attempt = 0
        last_row = None
        poll_history = []
        submitted_sql = (
            "SELECT * FROM dpu_seller_center.dpu_application "
            f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
            "AND application_status = 'SUBMITTED' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        while time.time() < deadline:
            attempt += 1
            try:
                with DatabaseExecutor(env=env) as db:
                    last_row = db.execute_query(submitted_sql)
            except Exception as exc:  # noqa: BLE001 - fall through to error path below
                return {
                    "success": False,
                    "error": f"查询 SUBMITTED application_unique_id 失败: {exc}",
                    "submitted_sql": submitted_sql,
                    "poll_attempts": attempt,
                }
            fresh_id = str((last_row or {}).get("application_unique_id") or "").strip()
            if fresh_id:
                break
            poll_history.append({
                "attempt": attempt,
                "submitted_found": False,
                "reason": "未查询到 application_status=SUBMITTED 的 re-approved 新申请单",
            })
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(interval_seconds, remaining))
        if not fresh_id:
            return {
                "success": False,
                "retryable": True,
                "error": (
                    "未从 dpu_application 中查询到 SUBMITTED application_unique_id，"
                    "请确认 activate-additional-limit 是否已落库"
                ),
                "merchant_id": merchant_id,
                "submitted_sql": submitted_sql,
                "timeout_seconds": timeout_seconds,
                "poll_attempts": attempt,
                "poll_history": poll_history[-10:],
                "last_row": last_row,
            }
        # Rebind the service so downstream mock_approved_offer_status uses fresh id.
        self.select_application(fresh_id)
        result = self.mock_approved_offer_status(
            amount=amount,
            status=status,
            failure_reason_index=failure_reason_index,
            rejection_reason=rejection_reason,
        )
        if isinstance(result, dict):
            result.setdefault("application_unique_id", fresh_id)
            result.setdefault("refreshed_from_db", True)
            result.setdefault("submitted_application_query_sql", submitted_sql)
            result.setdefault("poll_attempts", attempt)
            result.setdefault("poll_history", poll_history[-10:])
        return result

    def increase_approved_offer_status_web(
        self,
        amount: int = None,
        status: str = None,
        failure_reason_index: int = None,
        rejection_reason: str = None,
    ) -> dict:
        """提额 approved-offer：轮询同一 merchant_id 下 SUBMITTED 的提额新申请单。

        校验规则：
        1. SELECT * FROM dpu_application WHERE merchant_id = ? AND application_status = 'SUBMITTED'
        2. 这条 SUBMITTED 申请单作为提额新 application_unique_id
        3. 同一 merchant 下至少存在一条旧 APPROVED 申请单作为提额前置状态
        4. 绑定新 application_unique_id 后复用 mock_approved_offer_status 发送 approved-offer
        """
        merchant_id = self.merchant_id
        if not merchant_id:
            return {"success": False, "error": "当前 session 没有 merchant_id，无法查询 dpu_application"}

        submitted_sql = (
            "SELECT * FROM dpu_seller_center.dpu_application "
            f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
            "AND application_status = 'SUBMITTED' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        approved_sql = (
            "SELECT * FROM dpu_seller_center.dpu_application "
            f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
            "AND application_status = 'APPROVED' "
            "ORDER BY created_at DESC LIMIT 5"
        )
        timeout_seconds = 600
        interval_seconds = 3
        deadline = time.time() + timeout_seconds
        attempt = 0
        rows = []
        new_application = {}
        old_application = {}
        old_status = ""
        new_application_unique_id = ""
        last_reason = ""
        poll_history = []

        while time.time() < deadline:
            attempt += 1
            try:
                with DatabaseExecutor(env=self.db_executor.env) as db:
                    new_application = db.execute_query(submitted_sql) or {}
                    approved_rows = db.execute_query_all(approved_sql)
            except Exception as exc:  # noqa: BLE001 - return a structured operation failure
                return {
                    "success": False,
                    "error": f"查询 dpu_application 失败: {exc}",
                    "merchant_id": merchant_id,
                    "submitted_sql": submitted_sql,
                    "approved_sql": approved_sql,
                    "poll_attempts": attempt,
                }
            if isinstance(approved_rows, dict):
                approved_rows = [approved_rows]
            approved_rows = approved_rows or []
            old_application = approved_rows[0] if approved_rows else {}
            old_status = str(old_application.get("application_status") or "").upper()
            new_application_unique_id = str(new_application.get("application_unique_id") or "").strip()
            rows = ([new_application] if new_application else []) + approved_rows

            if not new_application_unique_id:
                last_reason = "未查询到 application_status=SUBMITTED 的提额新申请单"
            elif not approved_rows:
                last_reason = "未查询到旧 APPROVED 申请单，无法确认提额前置状态"
            elif old_status != "APPROVED":
                last_reason = f"旧申请单状态不是 APPROVED | old_status={old_status or '-'}"
            else:
                break

            poll_history.append({
                "attempt": attempt,
                "count": len(rows),
                "submitted_found": bool(new_application_unique_id),
                "new_application_unique_id": new_application.get("application_unique_id"),
                "new_application_status": new_application.get("application_status"),
                "old_application_unique_id": old_application.get("application_unique_id"),
                "old_application_status": old_application.get("application_status"),
                "reason": last_reason,
            })
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(interval_seconds, remaining))

        if not new_application_unique_id or not old_application or old_status != "APPROVED":
            return {
                "success": False,
                "retryable": True,
                "error": f"等待提额 dpu_application 落库超时: {last_reason or '未满足继续条件'}",
                "merchant_id": merchant_id,
                "submitted_sql": submitted_sql,
                "approved_sql": approved_sql,
                "timeout_seconds": timeout_seconds,
                "poll_attempts": attempt,
                "poll_history": poll_history[-10:],
                "new_application": new_application,
                "old_application": old_application,
                "application_rows": rows[:5],
            }

        self.select_application(new_application_unique_id)
        result = None
        webhook_attempt = 0
        webhook_history = []
        while True:
            webhook_attempt += 1
            result = self.mock_approved_offer_status(
                amount=amount,
                status=status,
                failure_reason_index=failure_reason_index,
                rejection_reason=rejection_reason,
            )
            response_json = result.get("response_json") if isinstance(result, dict) else None
            response_info_json = (result.get("response_info") or {}).get("json") if isinstance(result, dict) else None
            response_payload = response_json or response_info_json or {}
            status_code = result.get("status_code") or (result.get("response_info") or {}).get("status_code")
            retryable_invalid_input = (
                status_code == 400
                and isinstance(response_payload, dict)
                and response_payload.get("detail") == "Invalid input parameters"
                and response_payload.get("title") == "/webhook/handleApprovedOffer"
            )
            webhook_history.append({
                "attempt": webhook_attempt,
                "success": bool(result.get("success")) if isinstance(result, dict) else False,
                "status_code": status_code,
                "detail": response_payload.get("detail") if isinstance(response_payload, dict) else None,
                "title": response_payload.get("title") if isinstance(response_payload, dict) else None,
                "traceId": response_payload.get("traceId") if isinstance(response_payload, dict) else None,
            })
            if not retryable_invalid_input or result.get("success"):
                break
            remaining = deadline - time.time()
            if remaining <= 0:
                result.update({
                    "success": False,
                    "retryable": True,
                    "error": "等待提额 approved-offer 上游状态同步超时: handleApprovedOffer 仍返回 Invalid input parameters",
                    "timeout_seconds": timeout_seconds,
                    "webhook_attempts": webhook_attempt,
                    "webhook_history": webhook_history[-10:],
                })
                break
            time.sleep(min(interval_seconds, remaining))
        if isinstance(result, dict):
            result.update({
                "increase_flow": True,
                "application_count": len(rows),
                "selected_new_application_unique_id": new_application_unique_id,
                "old_application_unique_id": old_application.get("application_unique_id"),
                "old_application_status": old_application.get("application_status"),
                "submitted_application_query_sql": submitted_sql,
                "approved_application_query_sql": approved_sql,
                "poll_attempts": attempt,
                "poll_history": poll_history[-10:],
                "webhook_attempts": webhook_attempt,
                "webhook_history": webhook_history[-10:],
                "application_rows": rows[:5],
            })
        return result

    def submit_additional_director_info_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """800K 场景：先上传一张 1×1 PNG 到 /dpu-file/files/upload/addFile，
        然后 POST /fundpark-application/additional-director-shareholder 提交额外董事信息。

        实际后端只根据 objectKey 定位 S3 里的文件，所以第二个调用里 objectKey
        沿用 curl 示例即可；上传只是为了让整个链路和线上真实浏览器流量对齐。
        """
        import base64

        steps: list = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error

        # 1) POST /dpu-file/files/upload/addFile — multipart PNG upload
        upload_url = f"{self.api_config.base_url}/dpu-file/files/upload/addFile"
        # A minimal 1×1 transparent PNG so multipart is well-formed. Server-side
        # response is not consumed here (we hardcode objectKey below to keep
        # the flow stable), we only care that this HTTP call is exercised.
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        upload_headers = {k: v for k, v in (common_headers or {}).items() if k.lower() != "content-type"}
        upload_request_info = {
            "method": "POST",
            "url": upload_url,
            "headers": upload_headers,
            "body": "<multipart form-data: files=download.png (1×1 png, {} bytes)>".format(len(png_bytes)),
        }
        try:
            upload_resp = http_requests.post(
                upload_url,
                headers=upload_headers,
                files={"files": ("download.png", png_bytes, "image/png")},
                timeout=30,
            )
            upload_body_preview = (upload_resp.text or "")[:500]
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"upload/addFile 失败: {exc}",
                "steps": steps,
                "request_info": upload_request_info,
            }
        steps.append({
            "step": "dpu-file.upload.addFile",
            "endpoint": upload_url,
            "request_info": upload_request_info,
            "result": {
                "status_code": upload_resp.status_code,
                "response_body": upload_body_preview,
                "success": upload_resp.ok,
                "request_info": upload_request_info,
            },
        })

        # 2) POST /fundpark-application/additional-director-shareholder
        director_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/additional-director-shareholder"
        director_payload = {
            "step": "ADD_DIRECTOR_INFO_DRAFT",
            "isDraft": False,
            "data": {
                "persons": [
                    {
                        "id": str(uuid.uuid4()),
                        "spouseId": "",
                        "equityRatio": 100,
                        "perCreditReport": [
                            {
                                "name": "download.png",
                                "url": (
                                    "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/uploads/default/default/default/"
                                    "file_20260701163415_af5bd0dfa471.png?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                                    "&X-Amz-Date=20260701T083415Z&X-Amz-SignedHeaders=host&X-Amz-Expires=1800"
                                    "&X-Amz-Credential=AKIAVYYKAJWB2OBVR4OJ%2F20260701%2Fap-east-1%2Fs3%2Faws4_request"
                                    "&X-Amz-Signature=50bb83e6d234ce7fb618db2c86808832dd652215be93d73060373d1647bbeb1d"
                                ),
                                "objectKey": "uploads/default/default/default/file_20260701163415_af5bd0dfa471.png",
                                "thumbnailObjectKey": "uploads/default/default/default/file_20260701163415_af5bd0dfa471.png",
                                "docType": "",
                                "fileType": "PNG",
                            }
                        ],
                        "isMarried": False,
                        "position": "DIRECTOR_SHAREHOLDER_UBO",
                        "nameCn": "    ",
                        "nameEn": "LAUTSZ LAN",
                        "frontDocName": "",
                        "backDocName": "",
                        "idDocumentType": "PRC_RESIDENT_ID_CARD",
                        "idDocumentFrontUrl": "",
                        "idDocumentBackUrl": "",
                        "dateOfBirth": "",
                        "nationality": "China",
                        "ownershipProof": [],
                        "mobileNumber": {"countryCode": "+86", "number": ""},
                        "emailAddress": "",
                        "spouseEmailAddress": "",
                        "countryAndRegion": "",
                        "adressLine": "",
                        "secAdressLine": "",
                        "city": "",
                        "postalCode": "",
                        "spouseCreditReport": [],
                        "idFrontFlag": True,
                        "idBackFlag": True,
                    }
                ]
            },
        }
        director_result = self._do_post_custom(
            director_url,
            "提交额外董事信息",
            json_data=director_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.additional-director-shareholder",
            "endpoint": director_url,
            "payload": director_payload,
            "result": director_result,
        })
        if not director_result.get("success"):
            return {"success": False, "error": "additional-director-shareholder 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_additional_business_info_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """800K 场景：POST /fundpark-application/additionalBusinessInfo 提交额外公司信息。

        payload 里的 doc.url / objectKey 是从示例 curl 拷贝的 S3 预签名
        地址；DPU 后端只校验 objectKey，签名过期不影响本地 mock 使用。
        """
        steps: list = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/additionalBusinessInfo"
        payload: dict = {
            "step": "ADD_BUSINESS_INFO_DRAFT",
            "isDraft": False,
            "data": {
                "addDoc": [
                    {
                        "name": "download.png",
                        "url": (
                            "https://s3-dpu-sit.s3.ap-east-1.amazonaws.com/uploads/default/default/default/"
                            "file_20260701162315_88603539ee5f.png?X-Amz-Algorithm=AWS4-HMAC-SHA256"
                            "&X-Amz-Date=20260701T082315Z&X-Amz-SignedHeaders=host&X-Amz-Expires=1799"
                            "&X-Amz-Credential=AKIAVYYKAJWB2OBVR4OJ%2F20260701%2Fap-east-1%2Fs3%2Faws4_request"
                            "&X-Amz-Signature=21830c577eac87980b1066acc7f5fbea831385cb5caa5deb3a7f5bdf7bd92357"
                        ),
                        "objectKey": "uploads/default/default/default/file_20260701162315_88603539ee5f.png",
                        "thumbnailObjectKey": "uploads/default/default/default/file_20260701162315_88603539ee5f.png",
                        "docType": "",
                        "fileType": "PNG",
                        "uid": 1782894195473,
                        "status": "success",
                    },
                ],
                "optionalDoc": [],
                "additionalDocType": "UPLOAD_500K",
            },
        }
        result = self._do_post_custom(
            url,
            "提交额外公司信息",
            json_data=payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.additionalBusinessInfo",
            "endpoint": url,
            "payload": payload,
            "result": result,
        })
        if not result.get("success"):
            return {"success": False, "error": "additionalBusinessInfo 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_additional_documents_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """800K 场景第 18 步：POST /fundpark-application/submit-additional-documents 提交额外文档资料。"""
        steps: list = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/submit-additional-documents"
        payload: dict = {}
        result = self._do_post_custom(
            url,
            "提交额外文档资料",
            json_data=payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.submit-additional-documents",
            "endpoint": url,
            "payload": payload,
            "result": result,
        })
        if not result.get("success"):
            return {"success": False, "error": "submit-additional-documents 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def activate_additional_limit_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """800K 场景第 17 步：POST /credit-offer/activate-additional-limit 激活额外的额度。"""
        steps: list = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/activate-additional-limit"
        payload: dict = {}
        result = self._do_post_custom(
            url,
            "激活额外的额度",
            json_data=payload,
            headers=common_headers,
        )
        steps.append({
            "step": "credit-offer.activate-additional-limit",
            "endpoint": url,
            "payload": payload,
            "result": result,
        })
        if not result.get("success"):
            return {"success": False, "error": "activate-additional-limit 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_fp_add_contact_information_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        name_cn: Optional[str] = None,
        contact_template: Optional[dict] = None,
    ) -> dict:
        """DMF (HSBC USD) 第 13 步：提交联系人信息。

        naturePersonId 沿用 director-info 第一个董事的 id（持股 60% 的那位）。
        没有缓存的董事（例如用户先跳过了第 12 步）就现场生成一个 UUID。
        """
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error

        if (currency or self.preferred_currency or "").upper() == "CNY" and (funder_resource or "").upper() == "DOWSURE":
            url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/contact-person"
            template = contact_template if isinstance(contact_template, dict) else {}
            # 联系人姓名/手机号沿用 director-info 缓存的法人信息：备用公司→测近智/19443548216，
            # 默认公司→奉晓慧/18374816332。缓存缺失（例如跳过了 director-info）时，
            # 按 business-info 选择的公司回落到对应固定手机号，两套都不使用注册手机号。
            selected_company = getattr(self, "_dowsure_selected_company_cn_name", "") or ""
            is_backup_company = selected_company.strip() == self._DOWSURE_BACKUP_COMPANY_CN_NAME
            contact_mobile = (
                str(template.get("mobileNumber") or "").strip()
                or
                getattr(self, "_dowsure_contact_mobile", "")
                or ("19443548216" if is_backup_company else "18374816332")
            )
            contact_name = (
                name_cn
                or str(template.get("fullChineseName") or "").strip()
                or getattr(self, "_dowsure_contact_name", "")
            )
            payload = {
                "isDraft": bool(template.get("isDraft", False)),
                "isExistingPerson": bool(template.get("isExistingPerson", False)),
                "selectedPersonId": str(template.get("selectedPersonId") or ""),
                "fullChineseName": contact_name,
                "email": str(template.get("email") or "").strip() or f"{contact_mobile}@qq.com",
                "mobileNumber": contact_mobile,
                "phoneCountryCode": str(template.get("phoneCountryCode") or "+86"),
            }
            result = self._do_post_custom(
                url,
                "提交 contact-person",
                json_data=payload,
                headers=common_headers,
            )
            steps.append({
                "step": "fundpark-application.contact-person",
                "endpoint": url,
                "payload": payload,
                "result": result,
            })
            if not result.get("success"):
                return {"success": False, "error": "contact-person 失败", "steps": steps}
            return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

        persons = getattr(self, "_dmf_director_persons", None) or []
        nature_person_id = (persons[0]["id"] if persons else str(uuid.uuid4()))

        url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/add-contactInformation"
        payload = {
            "naturePersonId": nature_person_id,
            "addNewConformationRequest": {
                "title": "",
                "firstChiName": "",
                "firstEngName": "",
                "lastChiName": "",
                "lastEngName": "",
                "birthday": "",
                "idNumber": "",
                "country": "China",
                "countryCode": "CN",
                "area": "",
                "areaCode": "",
                "idNumberLength": "",
                "addressDetail": "",
                "email": "",
                "phoneNumber": "",
                "phoneCountryCode": "+86",
                "frontDocName": "",
                "naturePersonId": nature_person_id,
                "conformationType": "NATURE_PERSON",
                "backDocName": "",
                "idType": "PRC_RESIDENT_ID_CARD",
                "idDocumentFrontUrl": "",
                "idDocumentBackUrl": "",
                "idDocumentFrontFile": None,
                "idDocumentBackFile": None,
                "engName": None,
            },
            "isDraft": False,
        }
        result = self._do_post_custom(
            url,
            "提交 add-contactInformation",
            json_data=payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.add-contactInformation",
            "endpoint": url,
            "payload": payload,
            "result": result,
        })
        if not result.get("success"):
            return {"success": False, "error": "add-contactInformation 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_fp_bank_info_web(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        bank_info_url = f"{self.api_config.base_url}/dpu-merchant/bank-info"
        bank_account_number = f"128{int(time.time() * 1000) % 10000000000:010d}"
        bank_info_payload = {
            "step": "3",
            "isDraft": False,
            "bankCode": "128",
            "bankName": "128    (  )    FUBON BANK (HONG KONG) LIMITED",
            "bankAccountNumber": bank_account_number,
            "bankAccountName": "SUNRISE TECHNOLOGIES LIMITED",
            "swiftCode": "IBALHKHH",
            "bankAddress": "DES VOEUX ROAD, 38 HUTCHISON HOUSE FLOOR 5, CENTRAL",
        }
        bank_info_result = self._do_post_custom(
            bank_info_url,
            "提交 bank-info",
            json_data=bank_info_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "merchant.bank-info",
            "endpoint": bank_info_url,
            "payload": bank_info_payload,
            "result": bank_info_result,
        })
        if not bank_info_result.get("success"):
            return {"success": False, "error": "bank-info 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def start_fp_reassessment_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error

        reassessment_url = f"{self.api_config.base_url}/dpu-merchant/reassessment/start-reassessment"
        reassessment_payload = {}
        reassessment_result = self._do_post_custom(
            reassessment_url,
            "开始信用评估",
            json_data=reassessment_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "reassessment.start-reassessment",
            "endpoint": reassessment_url,
            "payload": reassessment_payload,
            "result": reassessment_result,
        })
        if not reassessment_result.get("success"):
            return {"success": False, "error": "start-reassessment 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def select_fp_offer_limit_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps)
        if error:
            return error
        limit_selection = self._resolve_limit_selection_amount(journey)
        cache_limit_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/cache-higher-limit"
        cache_limit_payload = {"limitSelection": limit_selection}
        cache_limit_result = self._do_post_custom(
            cache_limit_url,
            "缓存高额度选择",
            json_data=cache_limit_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.cache-higher-limit",
            "endpoint": cache_limit_url,
            "payload": cache_limit_payload,
            "result": cache_limit_result,
        })
        if not cache_limit_result.get("success"):
            return {"success": False, "error": "cache-higher-limit 失败", "steps": steps}

        # Note: /credit-offer/final-offer-select 曾经在这里被顺手调过，但线上
        # 实际流量里那一次 GET 不是"选择 offer 额度"步骤自己需要的（会由
        # 后续步骤自动触发或由用户手动进入 offer 页面时发出）。为了让这一
        # 步只反映 UI 上"选额度并缓存"这一个动作，去掉多余的 GET 调用。

        return {"success": True, "application_unique_id": self.application_unique_id, "limit_selection": limit_selection, "steps": steps}

    def activate_fp_offer_quote_web(self, journey: Optional[str] = None) -> dict:
        # 这个方法过去连续调 activate-offer + credit-offer/create 两个上游接口。
        # 现在这一步在前端被拆成了「创建 offer 额度报价」(仅 credit-offer/create)
        # 和「激活 offer 额度报价」(单独 /api/mock/fp-activate-offer → activate-offer)
        # 两步，所以这里只保留 credit-offer/create，避免旧路径重复调用。
        steps = []
        common_headers, error = self._application_headers_or_error(steps)
        if error:
            return error

        credit_offer_url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/create"
        credit_offer_result = self._do_post_custom(
            credit_offer_url,
            "创建 credit offer",
            headers=common_headers,
        )
        steps.append({
            "step": "credit-offer.create",
            "endpoint": credit_offer_url,
            "payload": None,
            "result": credit_offer_result,
        })
        if not credit_offer_result.get("success"):
            return {"success": False, "error": "credit-offer/create 失败", "steps": steps}
        return {
            "success": True,
            "application_unique_id": self.application_unique_id,
            "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id,
            "steps": steps,
        }

    def link_fp_sp_3pl_shops_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        link_url = f"{self.api_config.base_url}/dpu-merchant/mock/link-sp-3pl-shops"
        link_result = self._do_post_custom(
            link_url,
            "关联 SP/3PL 店铺",
            params={"phone": self.phone_number},
        )
        steps.append({
            "step": "link-sp-3pl-shops",
            "endpoint": link_url,
            "payload": {"phone": self.phone_number},
            "result": link_result,
        })
        if not link_result.get("success"):
            return {"success": False, "error": "link-sp-3pl-shops 失败", "steps": steps}
        return {"success": True, "phone_number": self.phone_number, "steps": steps}

    def run_fp_scheduled_tasks_and_poll_submitted_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps)
        if error:
            return error
        application_unique_id = self.application_unique_id
        sanction_url = f"{self.api_config.base_url}/dpu-merchant/test/scheduled-tasks/hsbcSanctionTask"
        sanction_result = self._do_post_custom(
            sanction_url,
            "触发 sanction 任务",
            headers=common_headers,
        )
        steps.append({
            "step": "scheduled-tasks.hsbcSanctionTask",
            "endpoint": sanction_url,
            "payload": None,
            "result": sanction_result,
        })
        if not sanction_result.get("success"):
            return {"success": False, "error": "hsbcSanctionTask 失败", "steps": steps}

        first_credit_model_url = f"{self.api_config.base_url}/dpu-merchant/test/scheduled-tasks/first-credit-model"
        first_credit_model_result = self._do_post_custom(
            first_credit_model_url,
            "触发 first-credit-model",
            headers=common_headers,
        )
        steps.append({
            "step": "scheduled-tasks.first-credit-model",
            "endpoint": first_credit_model_url,
            "payload": None,
            "result": first_credit_model_result,
        })
        if not first_credit_model_result.get("success"):
            return {"success": False, "error": "first-credit-model 失败", "steps": steps}

        scheduled_url = f"{self.api_config.base_url}/dpu-merchant/test/scheduled-tasks/first-application-start"
        scheduled_result = self._do_post_custom(
            scheduled_url,
            "触发 first-application-start",
            headers=common_headers,
        )
        steps.append({
            "step": "scheduled-tasks.first-application-start",
            "endpoint": scheduled_url,
            "payload": None,
            "result": scheduled_result,
        })
        if not scheduled_result.get("success"):
            return {"success": False, "error": "first-application-start 失败", "steps": steps}

        application_status_result = self._wait_for_application_status_submitted(
            common_headers,
            timeout_seconds=600,
        )
        steps.append({
            "step": "hsbc.application-status",
            "endpoint": f"{self.api_config.base_url}/dpu-merchant/hsbc/application-status",
            "payload": None,
            "result": application_status_result,
        })

        app_status_payload = application_status_result.get("response_json") or {}
        app_status_data = app_status_payload.get("data") if isinstance(app_status_payload, dict) else {}
        app_status_value = (app_status_data or {}).get("status") or ""
        application_unique_id = (
            (app_status_data or {}).get("applicationUniqueId")
            or self.application_unique_id
        )
        app_submitted = application_status_result.get("success") and str(app_status_value).upper() == "SUBMITTED"

        if app_submitted:
            limit_application_unique_id = self._wait_for_limit_application_unique_id(timeout_seconds=600)
            if limit_application_unique_id:
                return {
                    "success": True,
                    "application_unique_id": application_unique_id,
                    "limit_application_unique_id": limit_application_unique_id,
                    "application_status": app_status_value,
                    "steps": steps,
                }

            return {
                "success": False,
                "error": "application-status 已到 SUBMITTED，但等待窗口内未拿到 limit_application_unique_id，后续流程无法继续",
                "retryable": True,
                "retry_after": 20,
                "application_unique_id": application_unique_id,
                "limit_application_unique_id": None,
                "application_status": app_status_value,
                "steps": steps,
            }

        return {
            "success": False,
            "error": "等待窗口内未拿到 hsbc/application-status=SUBMITTED，后续流程无法继续",
            "retryable": True,
            "retry_after": 20,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": self.dpu_limit_application_id,
            "application_status": app_status_value or None,
            "steps": steps,
        }

    def _wait_for_application_unique_id(self, timeout_seconds: int = 120, interval_seconds: int = 2) -> Optional[str]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            application_unique_id = self.application_unique_id
            if application_unique_id:
                return application_unique_id
            time.sleep(interval_seconds)
        return None

    def _wait_for_limit_application_unique_id(self, timeout_seconds: int = 120, interval_seconds: int = 2) -> Optional[str]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            limit_application_unique_id = self.dpu_limit_application_id
            if limit_application_unique_id:
                return limit_application_unique_id
            time.sleep(interval_seconds)
        return None

    def _wait_for_application_status_submitted(
        self,
        headers: dict,
        timeout_seconds: int = 180,
        interval_seconds: int = 3,
    ) -> dict:
        url = f"{self.api_config.base_url}/dpu-merchant/hsbc/application-status"
        deadline = time.time() + timeout_seconds
        attempt = 0
        last_result = None
        poll_history = []
        while time.time() < deadline:
            attempt += 1
            result = self._do_get_custom(url, f"轮询 application-status 第{attempt}次", headers=headers)
            last_result = result
            payload = result.get("response_json") or {}
            data = payload.get("data") if isinstance(payload, dict) else {}
            status = (data or {}).get("status") or ""
            application_unique_id = (data or {}).get("applicationUniqueId") or self.application_unique_id
            poll_history.append({
                "attempt": attempt,
                "success": bool(result.get("success")),
                "status": status or None,
                "application_unique_id": application_unique_id,
                "status_code": result.get("status_code"),
                "error": result.get("error") or result.get("error_message"),
            })
            if result.get("success") and str(status).upper() == "SUBMITTED":
                result["status"] = status
                result["application_unique_id"] = application_unique_id
                result["poll_attempts"] = attempt
                result["poll_history"] = poll_history[-10:]
                return result
            time.sleep(interval_seconds)

        error = "hsbc/application-status 未在限定时间内到达 SUBMITTED"
        if isinstance(last_result, dict):
            last_result["success"] = False
            last_result["error"] = error
            last_result["poll_attempts"] = attempt
            last_result["poll_history"] = poll_history[-10:]
            return last_result
        return {"success": False, "error": error, "poll_attempts": attempt, "poll_history": poll_history[-10:]}

    @staticmethod
    def _resolve_limit_selection_amount(journey: Optional[str]) -> int:
        if journey == "200K":
            return 2000
        if journey == "2000K":
            return 2000000
        return 500000

    def _wait_for_credit_offer_submitted(self, auth_token: str, timeout_seconds: int = 180, interval_seconds: int = 3) -> dict:
        url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/status"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": "FUNDPARK",
            "product-currency": self.preferred_currency or "USD",
            "referer": f"{self._build_portal_base_url(self.db_executor.env)}/",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        }
        deadline = time.time() + timeout_seconds
        attempt = 0
        last_result = None
        poll_history = []
        while time.time() < deadline:
            attempt += 1
            result = self._do_get_custom(url, f"轮询 credit-offer/status 第{attempt}次", headers=headers)
            last_result = result
            payload = result.get("response_json") or {}
            status = ((payload.get("data") or {}).get("status") if isinstance(payload, dict) else None) or ""
            poll_history.append({
                "attempt": attempt,
                "success": bool(result.get("success")),
                "status": status or None,
                "status_code": result.get("status_code"),
                "error": result.get("error") or result.get("error_message"),
            })
            if result.get("success") and str(status).upper() == "SUBMITTED":
                result["status"] = status
                result["poll_attempts"] = attempt
                result["poll_history"] = poll_history[-10:]
                return result
            time.sleep(interval_seconds)

        error = "credit-offer/status 未在限定时间内到达 SUBMITTED"
        if isinstance(last_result, dict):
            last_result["success"] = False
            last_result["error"] = error
            last_result["poll_attempts"] = attempt
            last_result["poll_history"] = poll_history[-10:]
            return last_result
        return {"success": False, "error": error, "poll_attempts": attempt, "poll_history": poll_history[-10:]}

    # 常用大陆行政区划前缀（市级 6 位），用来给随机身份证号挑一个合法的开头。
    _PRC_ID_AREA_CODES = (
        "110101", "110105", "110108",  # 北京
        "120102", "120103",            # 天津
        "310101", "310104", "310115",  # 上海
        "440103", "440104", "440106", "440113",  # 广州/广东
        "440304", "440305", "440307",  # 深圳
        "330102", "330106", "330110",  # 杭州
        "510104", "510107", "510108",  # 成都
        "320104", "320105", "320106",  # 南京
        "420102", "420103", "420106",  # 武汉
    )

    @classmethod
    def _generate_prc_id_number(cls) -> str:
        """Generate a syntactically valid 18-digit PRC ID number (GB 11643).

        Area code / birth date / sequence are all randomised so successive calls
        produce different numbers. The 18th digit is the standard ISO 7064 mod
        11-2 check digit, so the number passes typical format validators.
        """
        weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        check_codes = "10X98765432"
        area_code = random.choice(cls._PRC_ID_AREA_CODES)
        # 出生日期在 1970-01-01 ~ 2002-12-31 之间随机，保证至少 22 岁。
        year = random.randint(1970, 2002)
        month = random.randint(1, 12)
        day = random.randint(1, 28)  # 28 以内保证每月都合法
        birth_date = f"{year:04d}{month:02d}{day:02d}"
        sequence = f"{random.randint(1, 999):03d}"
        body = f"{area_code}{birth_date}{sequence}"
        checksum = sum(int(value) * weight for value, weight in zip(body, weights)) % 11
        return f"{body}{check_codes[checksum]}"

    @classmethod
    def _generate_unique_prc_id_numbers(cls, count: int) -> list[str]:
        """Generate ``count`` distinct PRC ID numbers. Retries if rare collisions occur."""
        result: list[str] = []
        seen: set[str] = set()
        attempts = 0
        while len(result) < count and attempts < count * 20:
            attempts += 1
            candidate = cls._generate_prc_id_number()
            if candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
        # Fallback: pad with unique-looking strings if the random space somehow
        # collapsed (shouldn't happen in practice with 27 area codes * 32 years).
        while len(result) < count:
            result.append(cls._generate_prc_id_number())
        return result

    def _build_director_info_payload(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        name_cn: Optional[str] = None,
        address_detail: Optional[str] = None,
        common_headers: Optional[dict] = None,
        director_template: Optional[dict] = None,
        director_id_front_image_id: Optional[str] = None,
        director_id_back_image_id: Optional[str] = None,
    ) -> dict:
        if (currency or self.preferred_currency or "").upper() == "USD" and (funder_resource or "").upper() == "HSBC":
            # DMF (HSBC + USD) 提交两名董事/股东（60% / 40%）。手机号与邮箱
            # 每次随机生成且互不相同，避免后端按手机号或邮箱判重。
            def _new_mobile() -> str:
                # 11 位中国手机号：1 + [3-9] + 9 位随机数字
                return f"1{random.randint(3, 8)}{random.randint(10**8, 10**9 - 1):09d}"

            mobile_p1 = _new_mobile()
            mobile_p2 = _new_mobile()
            while mobile_p2 == mobile_p1:
                mobile_p2 = _new_mobile()

            email_p1 = f"{mobile_p1}@qq.com"
            email_p2 = f"{mobile_p2}@qq.com"

            business_key_p1 = str(uuid.uuid4())
            business_key_p2 = str(uuid.uuid4())

            def _build_person(*, equity, name_en, dob, front_obj, back_obj,
                              id_number, mobile, email, business_key):
                return {
                    "id": str(uuid.uuid4()),
                    "businessKey": business_key,
                    "equityRatio": equity,
                    "position": "DIRECTOR_SHAREHOLDER_UBO",
                    "roles": ["DIRECTOR", "SHAREHOLDER", "UBO"],
                    "nameCn": "    ",
                    "nameEn": name_en,
                    "firstChiName": None,
                    "lastChiName": None,
                    "frontDocName": "PRC ID-Front@3x-2Sh4SffG.png",
                    "backDocName": "PRC ID-Back@3x-DPHeKKi2.png",
                    "idDocumentType": "PRC_RESIDENT_ID_CARD",
                    "idDocumentFrontUrl": front_obj,
                    "idDocumentBackUrl": back_obj,
                    "idDocumentFrontFile": None,
                    "idDocumentBackFile": None,
                    "dateOfBirth": dob,
                    "nationality": "China",
                    "mobileNumber": {"countryCode": "+86", "number": mobile},
                    "emailAddress": email,
                    "countryAndRegion": "",
                    "adressLine": "",
                    "secAdressLine": "",
                    "city": "",
                    "postalCode": "",
                    "percentageOfShares": equity,
                    "idFrontFlag": True,
                    "idBackFlag": True,
                    "addStatus": "API",
                    "hsbcPersonInfoExtend": {
                        "title": "Mr",
                        "country": "China",
                        "countryCode": "CN",
                        "area": "",
                        "areaCode": "",
                        "addressDetail": address_detail or "Harbour Town 16F",
                        "idNumber": id_number,
                        "idNumberLength": "",
                    },
                    "dowsurePersonInfoExtend": None,
                    "guarantorList": None,
                    "mobileNumber.number": mobile,
                }

            # 两个董事的身份证号每次都随机生成（合法 18 位带校验码），互不重复。
            id_p1, id_p2 = self._generate_unique_prc_id_numbers(2)

            person1 = _build_person(
                equity=60,
                name_en="LAUTSZ LAN",
                dob="02/06/2026",
                front_obj="uploads/default/default/default/file_20260630101313_14686a653353.png",
                back_obj="uploads/default/default/default/file_20260630101314_9132b32551ab.png",
                id_number=id_p1,
                mobile=mobile_p1,
                email=email_p1,
                business_key=business_key_p1,
            )
            person2 = _build_person(
                equity=40,
                name_en="LYU WU HUANG",
                dob="17/06/2026",
                front_obj="uploads/default/default/default/file_20260630101402_59e3ea36b790.png",
                back_obj="uploads/default/default/default/file_20260630101403_f4ba7b0db584.png",
                id_number=id_p2,
                mobile=mobile_p2,
                email=email_p2,
                business_key=business_key_p2,
            )

            # Remember the director persons so later steps (e.g. add-contactInformation)
            # can reference the same naturePersonId / businessKey without the user
            # having to copy them around manually.
            self._dmf_director_persons = [person1, person2]

            return {
                "step": "2",
                "isDraft": False,
                "data": {
                    "persons": [person1, person2],
                    "guarantorList": [
                        {
                            "businessKey": business_key_p1,
                            "nameCn": "    ",
                            "nameEn": "LAUTSZ LAN",
                            "checked": True,
                        },
                        {
                            "businessKey": business_key_p2,
                            "nameCn": "    ",
                            "nameEn": "LYU WU HUANG",
                            "checked": False,
                        },
                    ],
                },
            }

        if (currency or self.preferred_currency or "").upper() == "CNY" and (funder_resource or "").upper() == "DOWSURE":
            template = director_template if isinstance(director_template, dict) else {}
            template_extend = (
                template.get("dowsurePersonInfoExtend")
                if isinstance(template.get("dowsurePersonInfoExtend"), dict)
                else {}
            )
            # director-info 自动跟随 business-info 选择的公司：选了备用公司
            # 「测广州市昆袄祝山脸从股份有限公司」就套用法人「测近智」这套档案。
            selected_company = getattr(self, "_dowsure_selected_company_cn_name", "") or ""
            is_backup_company = selected_company.strip() == self._DOWSURE_BACKUP_COMPANY_CN_NAME

            if is_backup_company:
                # 备用法人「测近智」档案（身份证图信息：出生1971.8.5、有效期2025.8.10-长期）。
                default_name_cn = "测近智"
                default_id_number = "620100197108054266"
                default_date_of_birth = "05/08/1971"
                default_id_card_start_date = "10/08/2025"
                default_address_detail = "甘肃省兰州市盘快饺题路247号301"
            else:
                default_name_cn = "奉晓慧"
                default_id_number = "431121199611248750"
                default_date_of_birth = "03/06/2026"
                default_id_card_start_date = "02/06/2026"
                default_address_detail = "广州市天河区测试路1号"

            resolved_name_cn = name_cn or str(template.get("nameCn") or "").strip() or default_name_cn
            id_number = str(template_extend.get("idNumber") or "").strip() or default_id_number
            date_of_birth = str(template.get("dateOfBirth") or "").strip() or default_date_of_birth
            id_card_start_date = (
                str(template_extend.get("idCardStartDate") or "").strip()
                or default_id_card_start_date
            )
            resolved_address_detail = (
                address_detail
                or str(template_extend.get("addressDetail") or "").strip()
                or default_address_detail
            )
            default_director_mobile = "19443548216" if is_backup_company else "18374816332"
            template_mobile = template.get("mobileNumber") if isinstance(template.get("mobileNumber"), dict) else {}
            director_mobile = str(template_mobile.get("number") or "").strip() or default_director_mobile

            # 运行时把仓库内身份证正反图上传到当前环境换 objectKey（全环境自适应）；
            # 备用与默认公司共用同一套「测近智」证件图。上传失败回落到 .env 固定 key。
            front_file_key = ""
            back_file_key = ""
            front_doc_name = ""
            back_doc_name = ""
            try:
                front_uploaded = self._upload_dowsure_asset(
                    "director_id_front",
                    common_headers,
                    director_id_front_image_id,
                )
                back_uploaded = self._upload_dowsure_asset(
                    "director_id_back",
                    common_headers,
                    director_id_back_image_id,
                )
                front_file_key = front_uploaded.get("file_key", "")
                back_file_key = back_uploaded.get("file_key", "")
                front_doc_name = str(front_uploaded.get("filename") or "").strip()
                back_doc_name = str(back_uploaded.get("filename") or "").strip()
            except Exception as exc:
                selected_custom_image = any(
                    image_id and not str(image_id).startswith("builtin:")
                    for image_id in (director_id_front_image_id, director_id_back_image_id)
                )
                if selected_custom_image:
                    raise
                log.warning("director 身份证运行时上传失败，回落到 .env key: %s", exc)
            if not front_file_key:
                front_file_key = (
                    os.getenv("DOWSURE_CNY_BACKUP_DIRECTOR_ID_FRONT_FILE_KEY", "").strip()
                    or os.getenv("DOWSURE_CNY_DIRECTOR_ID_FRONT_FILE_KEY", "").strip()
                )
            if not back_file_key:
                back_file_key = (
                    os.getenv("DOWSURE_CNY_BACKUP_DIRECTOR_ID_BACK_FILE_KEY", "").strip()
                    or os.getenv("DOWSURE_CNY_DIRECTOR_ID_BACK_FILE_KEY", "").strip()
                )

            if not front_file_key or not back_file_key:
                raise RuntimeError(
                    "身份证图上传失败且未配置 DOWSURE_CNY_DIRECTOR_ID_FRONT_FILE_KEY 或 "
                    "DOWSURE_CNY_DIRECTOR_ID_BACK_FILE_KEY"
                )
            self._dowsure_contact_name = resolved_name_cn
            # 缓存法人手机号，供后续 contact-person 步骤复用（与 director-info 一致）。
            self._dowsure_contact_mobile = director_mobile
            return {
                "step": "2",
                "isDraft": False,
                "data": {
                    "persons": [
                        {
                            "position": str(template.get("position") or "DIRECTOR_AND_LEGAL_REPRESENTATIVE"),
                            "nameCn": resolved_name_cn,
                            "nameEn": str(template.get("nameEn") or ""),
                            "mobileNumber": {
                                "countryCode": str(template_mobile.get("countryCode") or "+86"),
                                "number": director_mobile,
                            },
                            "dowsurePersonInfoExtend": {
                                "idNumber": id_number,
                                "idCardStartDate": id_card_start_date,
                                "idCardEndDate": str(template_extend.get("idCardEndDate") or ""),
                                "longTermFlag": str(template_extend.get("longTermFlag") or "true"),
                                "addressDetail": resolved_address_detail,
                            },
                            "dateOfBirth": date_of_birth,
                            "frontDocName": (
                                front_doc_name
                                or str(template.get("frontDocName") or "身份证正面.png")
                            ),
                            "backDocName": (
                                back_doc_name
                                or str(template.get("backDocName") or "身份证反面.png")
                            ),
                            "idDocumentFrontUrl": front_file_key,
                            "idDocumentBackUrl": back_file_key,
                            "emailAddress": str(template.get("emailAddress") or "").strip() or f"{director_mobile}@qq.com",
                            "idDocumentType": str(template.get("idDocumentType") or "PRC_RESIDENT_ID_CARD"),
                            "id": str(uuid.uuid4()),
                        }
                    ],
                    "guarantorList": [],
                },
            }

        return {
            "step": "2",
            "isDraft": False,
            "data": {
                "persons": [
                    {
                        "id": str(uuid.uuid4()),
                        "businessKey": None,
                        "equityRatio": 100,
                        "position": "DIRECTOR_SHAREHOLDER_UBO",
                        "roles": ["DIRECTOR", "SHAREHOLDER", "UBO"],
                        "nameCn": "    ",
                        "nameEn": "LAUTSZ LAN",
                        "firstChiName": None,
                        "lastChiName": None,
                        "frontDocName": "PRC ID-Front@3x-2Sh4SffG.png",
                        "backDocName": "PRC ID-Back@3x-DPHeKKi2.png",
                        "idDocumentType": "PRC_RESIDENT_ID_CARD",
                        "idDocumentFrontUrl": "uploads/default/default/default/file_20260608101214_084c1c663cdb.png",
                        "idDocumentBackUrl": "uploads/default/default/default/file_20260608101217_b73417787427.png",
                        "idDocumentFrontFile": None,
                        "idDocumentBackFile": None,
                        "dateOfBirth": "01/06/2026",
                        "nationality": "China",
                        "mobileNumber": {"countryCode": "+86", "number": "15533906473"},
                        "emailAddress": "15533906473@qq.com",
                        "countryAndRegion": "",
                        "adressLine": "",
                        "secAdressLine": "",
                        "city": "",
                        "postalCode": "",
                        "percentageOfShares": 100,
                        "idFrontFlag": True,
                        "idBackFlag": True,
                        "addStatus": "API",
                        "hsbcPersonInfoExtend": None,
                        "dowsurePersonInfoExtend": None,
                        "guarantorList": None,
                        "mobileNumber.number": "15533906473",
                    }
                ]
            },
        }

    def _ensure_sp_auth_active_from_manual_offer(self, seller_id: Optional[str] = None) -> dict:
        """Normalize SP auth rows so each seller ends with one canonical ACTIVE token."""
        resolved_seller_id = self._resolve_platform_seller_id(seller_id)
        manual_offer = self._wait_for_manual_offer(
            selling_partner_id=resolved_seller_id,
            merchant_id=self.merchant_id,
            timeout_seconds=1,
            interval_seconds=1,
        )
        if not manual_offer:
            return {
                "success": False,
                "error": "No ready dpu_manual_offer found for SP auth fallback",
                "seller_id": resolved_seller_id,
                "merchant_id": self.merchant_id,
            }

        seller_id = manual_offer.get("platform_seller_id") or resolved_seller_id
        merchant_account_id = manual_offer.get("merchant_account_id")
        if not seller_id or not merchant_account_id:
            return {
                "success": False,
                "error": "manual offer missing platform_seller_id or merchant_account_id",
                "manual_offer": manual_offer,
            }

        token_rows = self.db_executor.execute_query_all(
            "SELECT id, merchant_account_id, authorization_id, status, state, reason, "
            "scene_code, processing_stage, auth_start_time, auth_complete_time, created_at, updated_at "
            "FROM dpu_seller_center.dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            f"AND (authorization_id = {self._sql_literal(seller_id)} "
            "OR authorization_id IS NULL OR authorization_id = '') "
            "ORDER BY created_at DESC, id DESC"
        )
        if not token_rows:
            return {
                "success": False,
                "error": "No SP token rows found for normalization",
                "seller_id": seller_id,
                "merchant_account_id": merchant_account_id,
            }

        def _token_rank(row: dict) -> tuple:
            return (
                1 if row.get("authorization_id") == seller_id and row.get("status") == "ACTIVE" else 0,
                1 if row.get("scene_code") else 0,
                1 if row.get("auth_complete_time") else 0,
                1 if row.get("auth_start_time") else 0,
                row.get("updated_at") or row.get("created_at"),
                row.get("id"),
            )

        canonical_token = max(token_rows, key=_token_rank)
        canonical_id = canonical_token["id"]

        normalize_canonical_sql = (
            "UPDATE dpu_seller_center.dpu_auth_token "
            f"SET merchant_account_id = {self._sql_literal(merchant_account_id)}, "
            f"authorization_id = {self._sql_literal(seller_id)}, "
            "status = 'ACTIVE', "
            "reason = NULL, "
            "auth_complete_time = COALESCE(auth_complete_time, NOW()), "
            "updated_at = NOW() "
            f"WHERE id = {self._sql_literal(canonical_id)}"
        )
        self.db_executor.execute_sql(normalize_canonical_sql)

        suppress_duplicate_sql = (
            "UPDATE dpu_seller_center.dpu_auth_token "
            "SET status = 'REVOKED', "
            "reason = 'mockapi normalized duplicate SP token', "
            "updated_at = NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            f"AND id <> {self._sql_literal(canonical_id)} "
            f"AND (authorization_id = {self._sql_literal(seller_id)} "
            "OR authorization_id IS NULL OR authorization_id = '') "
            "AND status IN ('NEW', 'FAIL', 'PENDING', 'ACTIVE')"
        )
        self.db_executor.execute_sql(suppress_duplicate_sql)

        active_token = self.db_executor.execute_query(
            "SELECT id, state, status, authorization_id, merchant_account_id "
            "FROM dpu_seller_center.dpu_auth_token "
            f"WHERE id = {self._sql_literal(canonical_id)} "
            "LIMIT 1"
        )
        if not active_token:
            return {
                "success": False,
                "error": "SP token was not ACTIVE after fallback update",
                "seller_id": seller_id,
                "merchant_account_id": merchant_account_id,
            }

        inserted_shops = []
        for country_code in ("US", "CA"):
            exists_sql = (
                "SELECT id FROM dpu_seller_center.dpu_shops "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                "AND emarketplace = 'AMAZON' "
                "AND emarketplace_data_type = 'SP' "
                f"AND shop_reference_id = {self._sql_literal(seller_id)} "
                f"AND country_code = {self._sql_literal(country_code)} "
                "AND is_deleted = 0 "
                "LIMIT 1"
            )
            if self.db_executor.execute_sql(exists_sql):
                continue
            insert_shop_sql = (
                "INSERT INTO dpu_seller_center.dpu_shops ("
                "id, merchant_id, emarketplace, emarketplace_data_type, auth_id, "
                "shop_reference_id, merchant_account_id, shop_status, country_code, "
                "created_at, updated_at, create_by, update_by, is_deleted"
                ") VALUES ("
                "REPLACE(UUID(), '-', ''), "
                f"{self._sql_literal(self.merchant_id)}, "
                "'AMAZON', 'SP', "
                f"{self._sql_literal(canonical_id)}, "
                f"{self._sql_literal(seller_id)}, "
                f"{self._sql_literal(merchant_account_id)}, "
                "'ACTIVE', "
                f"{self._sql_literal(country_code)}, "
                "NOW(), NOW(), 'mockapi', 'mockapi', 0)"
            )
            self.db_executor.execute_sql(insert_shop_sql)
            inserted_shops.append(country_code)

        repoint_shop_sql = (
            "UPDATE dpu_seller_center.dpu_shops "
            f"SET auth_id = {self._sql_literal(canonical_id)}, "
            f"merchant_account_id = {self._sql_literal(merchant_account_id)}, "
            "updated_at = NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND emarketplace = 'AMAZON' "
            "AND emarketplace_data_type = 'SP' "
            f"AND shop_reference_id = {self._sql_literal(seller_id)} "
            "AND is_deleted = 0"
        )
        self.db_executor.execute_sql(repoint_shop_sql)

        latest_token = self.db_executor.execute_query(
            "SELECT id, state, status, authorization_id, merchant_account_id, reason, created_at, updated_at "
            "FROM dpu_seller_center.dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        shop_rows = self.db_executor.execute_query_all(
            "SELECT id, auth_id, shop_reference_id, merchant_account_id, shop_status, country_code "
            "FROM dpu_seller_center.dpu_shops "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND emarketplace = 'AMAZON' "
            "AND emarketplace_data_type = 'SP' "
            f"AND shop_reference_id = {self._sql_literal(seller_id)} "
            "AND is_deleted = 0 "
            "ORDER BY country_code"
        )
        return {
            "success": bool(active_token and active_token.get("status") == "ACTIVE"),
            "seller_id": seller_id,
            "merchant_account_id": merchant_account_id,
            "manual_offer": manual_offer,
            "canonical_token_id": canonical_id,
            "active_token": active_token,
            "latest_sp_token": latest_token,
            "inserted_shops": inserted_shops,
            "shops": shop_rows,
        }

    @staticmethod
    def _build_api_config(env: str) -> ApiConfig:
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "reg": "https://dpu-gateway-reg.dowsure.com",
            "local": "http://192.168.11.3:8080",
        }
        base_url = base_url_dict[env]
        redirect_url_base = (
            f"{base_url}/dpu-merchant/amazon/redirect"
            if env in ("uat", "preprod")
            else f"https://dpu-gateway-{env}.dowsure.com/dpu-merchant/amazon/redirect"
        )
        return ApiConfig(
            base_url=base_url,
            create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            redirect_url=redirect_url_base,
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=f"{base_url}/dpu-merchant/amz/sp/shop/auth",
            multi_shop_sp_auth_url=f"{base_url}/dpu-auth/amazon-sp/auth",
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            update_offer_url=f"{base_url}/dpu-auth/amazon-sp/updateOffer",
            txt_path=str(SCRIPT_DIR / f"register_{env}.txt"),
        )

    @staticmethod
    def _build_portal_base_url(env: str) -> str:
        portal_base_url_dict = {
            "sit": "https://expressfinance-dpu-sit.dowsure.com",
            "dev": "https://expressfinance-dpu-dev.dowsure.com",
            "uat": "https://expressfinance-uat.business.hsbc.com",
            "preprod": "https://expressfinance-preprod.business.hsbc.com",
            "reg": "https://expressfinance-dpu-reg.dowsure.com",
            "local": "http://localhost:5173",
        }
        return portal_base_url_dict[env]

    @staticmethod
    def _format_http_body_for_log(text: str, max_chars: int = 4000) -> str:
        """Pretty-print JSON response bodies and keep long payloads bounded for the UI log."""
        if text is None:
            return ""
        body = str(text)
        try:
            body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
        except (TypeError, json.JSONDecodeError):
            pass
        if len(body) > max_chars:
            return f"{body[:max_chars]}\n...<truncated {len(body) - max_chars} chars>"
        return body

    @staticmethod
    def _format_http_headers_for_log(headers: dict, max_chars: int = 2000) -> str:
        header_text = json.dumps(dict(headers or {}), indent=2, ensure_ascii=False)
        if len(header_text) > max_chars:
            return f"{header_text[:max_chars]}\n...<truncated {len(header_text) - max_chars} chars>"
        return header_text

    @staticmethod
    def _format_redirect_body_for_log(text: str, max_chars: int = 500) -> str:
        """Do not flood operation results with redirected HTML pages."""
        if text is None:
            return ""
        body = str(text)
        stripped = body.lstrip().lower()
        if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
            return f"<HTML response omitted; {len(body)} chars>"
        if len(body) > max_chars:
            return f"{body[:max_chars]}\n...<truncated {len(body) - max_chars} chars>"
        return body

    @staticmethod
    def _interpret_api_success(response: http_requests.Response) -> tuple[bool, Optional[dict], Optional[str]]:
        """Treat business-level error payloads as failures even when HTTP status is 200."""
        http_success = 200 <= response.status_code < 300
        try:
            payload = response.json()
        except ValueError:
            return http_success, None, None

        if not isinstance(payload, dict):
            return http_success, payload, None

        # Some auth bootstrap APIs return authStatus=UNAUTHORIZED together with an authorization URL.
        # That means the request succeeded and produced the next-step consent entrypoint.
        if (
            str(payload.get("code")) == "200"
            and isinstance(payload.get("data"), dict)
            and payload["data"].get("authorizationUrl")
        ):
            return http_success, payload, None

        business_success = True
        if "isSuccess" in payload:
            business_success = bool(payload.get("isSuccess"))
        elif "success" in payload:
            business_success = bool(payload.get("success"))
        elif "code" in payload:
            business_success = str(payload.get("code")) == "200"

        error_message = None
        if not business_success:
            error_message = str(
                payload.get("message")
                or payload.get("detail")
                or payload.get("title")
                or "Business response indicated failure"
            )
        return http_success and business_success, payload, error_message

    @staticmethod
    def _summarize_webhook_request(data: dict) -> str:
        details = (data or {}).get("data", {}).get("details", {})
        summary = {
            "eventType": (data or {}).get("data", {}).get("eventType"),
            "merchantId": details.get("merchantId"),
            "status": details.get("status") or details.get("result") or details.get("drawdownStatus"),
            "dpuLimitApplicationId": details.get("dpuLimitApplicationId"),
            "dpuApplicationId": details.get("dpuApplicationId"),
            "dpuMerchantAccountId": details.get("dpuMerchantAccountId"),
            "creditLimit": details.get("credit", {}).get("creditLimit") if isinstance(details.get("credit"), dict) else None,
        }
        return json.dumps({k: v for k, v in summary.items() if v is not None}, indent=2, ensure_ascii=False)

    def _do_post_webhook(self, data: dict, label: str, headers: Optional[dict] = None) -> dict:
        """统一的 webhook POST 发送 + 日志 + 结果封装"""
        request_headers = headers or {"Content-Type": "application/json"}
        request_info = {
            "method": "POST",
            "url": self.api_config.webhook_url,
            "headers": request_headers,
            "body": data,
        }
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: POST")
        log.info(f"请求URL: {self.api_config.webhook_url}")
        log.info("请求Headers:")
        log.info(json.dumps(request_info["headers"], indent=2, ensure_ascii=False))
        log.info("请求Body（JSON）:")
        log.info(json.dumps(data, indent=2, ensure_ascii=False))
        log.info("=" * 60)

        try:
            response = http_requests.post(self.api_config.webhook_url, json=data, headers=request_headers, timeout=30)
            log.info(f"\n【{label}】完整响应信息")
            log.info("=" * 60)
            log.info(f"响应状态码: {response.status_code}")
            log.info("响应Headers:")
            log.info(self._format_http_headers_for_log(response.headers))
            log.info(f"响应Body: {response.text}")
            log.info("=" * 60)

            success = response.status_code == 200
            response_body = self._format_http_body_for_log(response.text)
            response_json = None
            try:
                response_json = response.json()
            except ValueError:
                response_json = None
            if success:
                log.info(f"{label}成功")
            else:
                headers_for_log = self._format_http_headers_for_log(response.headers)
                request_summary = self._summarize_webhook_request(data)
                log.error(
                    f"{label}失败 | 状态码={response.status_code}\n"
                    f"请求URL: {self.api_config.webhook_url}\n"
                    f"请求摘要:\n{request_summary}\n"
                    f"响应Headers:\n{headers_for_log}\n"
                    f"响应Body:\n{response_body}"
                )
            return {
                "success": success,
                "status_code": response.status_code,
                "response": response.text,
                "response_body": response_body,
                "response_headers": dict(response.headers),
                "response_json": response_json,
                "request_info": request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": response_json,
                },
            }
        except http_requests.exceptions.RequestException as e:
            detail = [f"【{label}】请求异常: {type(e).__name__}: {e}", f"请求URL: {self.api_config.webhook_url}"]
            response_info = None
            if getattr(e, "response", None) is not None:
                response_body = self._format_http_body_for_log(e.response.text)
                response_json = None
                try:
                    response_json = e.response.json()
                except ValueError:
                    response_json = None
                response_info = {
                    "status_code": e.response.status_code,
                    "headers": dict(e.response.headers),
                    "body": response_body,
                    "json": response_json,
                }
                detail.extend([
                    f"响应状态码: {e.response.status_code}",
                    f"响应Headers:\n{self._format_http_headers_for_log(e.response.headers)}",
                    f"响应Body:\n{response_body}",
                ])
            log.error("\n".join(detail))
            return {
                "success": False,
                "error": str(e),
                "error_message": str(e),
                "request_info": request_info,
                "response_info": response_info,
            }

    def _do_post_custom(self, url: str, label: str, json_data: dict = None,
                        params: dict = None, headers: dict = None) -> dict:
        """统一的自定义 URL POST 发送"""
        request_info = {
            "method": "POST",
            "url": url,
            "headers": headers or {},
            "params": params,
            "body": json_data,
        }
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: POST")
        log.info(f"请求URL: {url}")
        if json_data is not None:
            log.info(f"请求Body（JSON）: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
        if params:
            log.info(f"请求Params: {params}")
        if headers:
            log.info(f"请求Headers: {json.dumps(headers, ensure_ascii=False)}")
        log.info("=" * 60)

        try:
            kwargs = {"timeout": 30}
            if json_data is not None:
                kwargs["json"] = json_data
            if params:
                kwargs["params"] = params
            if headers:
                kwargs["headers"] = headers
            response = http_requests.post(url, **kwargs)
            success, response_payload, business_error = self._interpret_api_success(response)
            response_body = self._format_http_body_for_log(response.text)
            log.info(f"【{label}】响应状态码: {response.status_code}")
            log.info(f"【{label}】响应Body: {response_body}")
            if not success:
                error_suffix = f"\n业务错误: {business_error}" if business_error else ""
                log.error(
                    f"{label}失败 | 状态码={response.status_code}\n"
                    f"请求URL: {url}\n"
                    f"响应Payload:\n{json.dumps(response_payload, indent=2, ensure_ascii=False) if isinstance(response_payload, dict) else response_body}\n"
                    f"响应Headers:\n{self._format_http_headers_for_log(response.headers)}\n"
                    f"响应Body:\n{response_body}"
                    f"{error_suffix}"
                )
            return {
                "success": success,
                "status_code": response.status_code,
                "response": response.text,
                "response_body": response_body,
                "response_headers": dict(response.headers),
                "response_json": response_payload if isinstance(response_payload, dict) else None,
                "error_message": business_error,
                "request_info": request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": response_payload if isinstance(response_payload, dict) else None,
                },
            }
        except http_requests.exceptions.RequestException as e:
            detail = [f"【{label}】请求异常: {type(e).__name__}: {e}", f"请求URL: {url}"]
            response_info = None
            if getattr(e, "response", None) is not None:
                response_body = self._format_http_body_for_log(e.response.text)
                response_json = None
                try:
                    response_json = e.response.json()
                except ValueError:
                    response_json = None
                response_info = {
                    "status_code": e.response.status_code,
                    "headers": dict(e.response.headers),
                    "body": response_body,
                    "json": response_json,
                }
                detail.extend([
                    f"响应状态码: {e.response.status_code}",
                    f"响应Headers:\n{self._format_http_headers_for_log(e.response.headers)}",
                    f"响应Body:\n{response_body}",
                ])
            log.error("\n".join(detail))
            return {
                "success": False,
                "error": str(e),
                "error_message": str(e),
                "request_info": request_info,
                "response_info": response_info,
            }

    def _do_post_custom_with_retry(
        self,
        url: str,
        label: str,
        json_data: dict = None,
        params: dict = None,
        headers: dict = None,
        attempts: int = 2,
        interval_seconds: int = 2,
        require_json_data: bool = False,
    ) -> dict:
        """POST helper with a small retry for transient REG gateway timeouts."""
        last_result = None
        for attempt in range(1, max(1, attempts) + 1):
            retry_label = label if attempt == 1 else f"{label} retry {attempt}"
            result = self._do_post_custom(
                url,
                retry_label,
                json_data=json_data,
                params=params,
                headers=headers,
            )
            result["attempt"] = attempt
            last_result = result
            retryable_empty_data = False
            if result.get("success") and require_json_data:
                response_payload = result.get("response_json") or {}
                response_data = response_payload.get("data") if isinstance(response_payload, dict) else None
                if response_data in (None, "", [], {}):
                    result["success"] = False
                    result["error"] = f"{label} response data is empty"
                    result["error_message"] = result["error"]
                    retryable_empty_data = True
            if result.get("success"):
                return result
            error_text = str(result.get("error") or result.get("error_message") or "")
            if (
                not retryable_empty_data
                and "timed out" not in error_text.lower()
                and "timeout" not in error_text.lower()
            ):
                return result
            if attempt < attempts:
                time.sleep(interval_seconds)
        return last_result or {"success": False, "error": f"{label} failed without result"}

    def _do_get_custom(self, url: str, label: str, params: dict = None, headers: dict = None) -> dict:
        """统一的自定义 URL GET 发送"""
        request_info = {
            "method": "GET",
            "url": url,
            "headers": headers or {},
            "params": params,
            "body": None,
        }
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: GET")
        log.info(f"请求URL: {url}")
        if params:
            log.info(f"请求Params: {params}")
        if headers:
            log.info(f"请求Headers: {json.dumps(headers, ensure_ascii=False)}")
        log.info("=" * 60)

        try:
            kwargs = {"timeout": 30}
            if params:
                kwargs["params"] = params
            if headers:
                kwargs["headers"] = headers
            response = http_requests.get(url, **kwargs)
            success, response_payload, business_error = self._interpret_api_success(response)
            response_body = self._format_http_body_for_log(response.text)
            log.info(f"【{label}】响应状态码: {response.status_code}")
            log.info(f"【{label}】响应Body: {response_body}")
            if not success:
                error_suffix = f"\n业务错误: {business_error}" if business_error else ""
                log.error(
                    f"{label}失败 | 状态码={response.status_code}\n"
                    f"请求URL: {url}\n"
                    f"响应Payload:\n{json.dumps(response_payload, indent=2, ensure_ascii=False) if isinstance(response_payload, dict) else response_body}\n"
                    f"响应Headers:\n{self._format_http_headers_for_log(response.headers)}\n"
                    f"响应Body:\n{response_body}"
                    f"{error_suffix}"
                )
            return {
                "success": success,
                "status_code": response.status_code,
                "response": response.text,
                "response_body": response_body,
                "response_headers": dict(response.headers),
                "response_json": response_payload if isinstance(response_payload, dict) else None,
                "error_message": business_error,
                "request_info": request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": response_payload if isinstance(response_payload, dict) else None,
                },
            }
        except http_requests.exceptions.RequestException as e:
            response_info = None
            if getattr(e, "response", None) is not None:
                response_body = self._format_http_body_for_log(e.response.text)
                response_json = None
                try:
                    response_json = e.response.json()
                except ValueError:
                    response_json = None
                response_info = {
                    "status_code": e.response.status_code,
                    "headers": dict(e.response.headers),
                    "body": response_body,
                    "json": response_json,
                }
            log.error(f"{label}请求异常: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_message": str(e),
                "request_info": request_info,
                "response_info": response_info,
            }

    def _do_get_custom_with_retry(
        self,
        url: str,
        label: str,
        params: dict = None,
        headers: dict = None,
        attempts: int = 2,
        interval_seconds: int = 2,
    ) -> dict:
        """GET helper with a small retry for transient REG gateway timeouts."""
        last_result = None
        for attempt in range(1, max(1, attempts) + 1):
            retry_label = label if attempt == 1 else f"{label} retry {attempt}"
            result = self._do_get_custom(
                url,
                retry_label,
                params=params,
                headers=headers,
            )
            result["attempt"] = attempt
            last_result = result
            if result.get("success"):
                return result
            error_text = str(result.get("error") or result.get("error_message") or "")
            if "timed out" not in error_text.lower() and "timeout" not in error_text.lower():
                return result
            if attempt < attempts:
                time.sleep(interval_seconds)
        return last_result or {"success": False, "error": f"{label} failed without result"}

    # ======================== 1. SP-3PL 关联 ========================

    def mock_link_sp_3pl_shop(self) -> dict:
        """模拟关联 SP 和 3PL 店铺（无需用户输入）"""
        log.info("开始关联SP和3PL店铺...")
        result = self._do_post_custom(
            self.api_config.link_sap_3pl_url,
            "SP-3PL关联",
            params={"phone": self.phone_number}
        )
        if result.get("success"):
            try:
                resp_json = json.loads(result.get("response", "{}"))
                if resp_json.get("code") == 200:
                    log.info("SP-3PL关联成功")
                else:
                    log.error(f"SP-3PL关联失败: {resp_json}")
                    result["success"] = False
            except json.JSONDecodeError:
                pass
        return result

    # ======================== 2. 核保 ========================

    def get_dowsure_merchant_accounts(self) -> dict:
        """Return DOWSURE offer rows used by creditResultList."""
        if not self.merchant_id:
            return {"success": False, "error": "当前 session 没有 merchant_id，无法反查 DOWSURE 店铺 sellerId"}

        tpl_token_sql = (
            "SELECT authorization_id AS dpu_offer_id, merchant_account_id "
            "FROM dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party IN ('3PL', 'DPU_3PL') "
            "AND authorization_id IS NOT NULL "
            "AND authorization_id <> '' "
            "AND merchant_account_id IS NOT NULL "
            "AND merchant_account_id <> '' "
            "ORDER BY created_at DESC"
        )
        tpl_rows = self.db_executor.execute_query_all(tpl_token_sql) or []
        if isinstance(tpl_rows, dict):
            tpl_rows = [tpl_rows]

        dpu_offer_id_by_account = {}
        merchant_account_ids = []
        for row in tpl_rows:
            merchant_account_id = str(row.get("merchant_account_id") or "").strip()
            dpu_offer_id = str(row.get("dpu_offer_id") or "").strip()
            if merchant_account_id and dpu_offer_id and merchant_account_id not in dpu_offer_id_by_account:
                dpu_offer_id_by_account[merchant_account_id] = dpu_offer_id
                merchant_account_ids.append(merchant_account_id)

        if not merchant_account_ids:
            return {
                "success": True,
                "merchant_id": self.merchant_id,
                "source_sql": tpl_token_sql,
                "accounts": [],
                "count": 0,
                "warning": "当前 merchant_id 未查询到 3PL/DPU_3PL dpu_auth_token，无法通过 DPU offerId 反查 merchant_account_id",
            }

        sp_token_sql = (
            "SELECT merchant_account_id, authorization_id AS seller_id, status "
            "FROM dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND merchant_account_id IN ("
            + ", ".join(self._sql_literal(account_id) for account_id in merchant_account_ids)
            + ") "
            "AND authorization_party = 'SP' "
            "AND authorization_id IS NOT NULL "
            "AND authorization_id <> '' "
            "ORDER BY merchant_account_id, (status = 'ACTIVE') DESC, updated_at DESC, created_at DESC"
        )
        sp_rows = self.db_executor.execute_query_all(sp_token_sql) or []
        if isinstance(sp_rows, dict):
            sp_rows = [sp_rows]

        seller_id_by_account = {}
        account_id_by_seller = {}
        for row in sp_rows:
            merchant_account_id = str(row.get("merchant_account_id") or "").strip()
            seller_id = str(row.get("seller_id") or "").strip()
            if merchant_account_id and seller_id and merchant_account_id not in seller_id_by_account:
                seller_id_by_account[merchant_account_id] = seller_id
                account_id_by_seller.setdefault(seller_id, merchant_account_id)

        if not account_id_by_seller:
            return {
                "success": True,
                "merchant_id": self.merchant_id,
                "source_sql": {"dpu_3pl_token_sql": tpl_token_sql, "sp_token_sql": sp_token_sql},
                "accounts": [],
                "count": 0,
                "warning": "已通过 DPU offerId 查询到 merchant_account_id，但未查询到对应 SP sellerId",
            }

        seller_ids = list(account_id_by_seller.keys())
        dowsure_offer_sql = (
            "SELECT offer_id, seller_id "
            "FROM dsb_seller_center.t_offer "
            "WHERE offer_source = 'DPU_3PL' "
            "AND seller_id IN ("
            + ", ".join(self._sql_literal(seller_id) for seller_id in seller_ids)
            + ") "
            "ORDER BY create_time DESC LIMIT 50"
        )
        dowsure_offer_rows = self._query_dowsure_seller_center(dowsure_offer_sql)

        seen_offer_ids = set()
        accounts = []
        for row in dowsure_offer_rows or []:
            offer_id = str(row.get("offer_id") or "").strip()
            seller_id = str(row.get("seller_id") or "").strip()
            merchant_account_id = account_id_by_seller.get(seller_id, "")
            if not offer_id or not seller_id or offer_id in seen_offer_ids:
                continue
            seen_offer_ids.add(offer_id)
            accounts.append({
                "offerId": offer_id,
                "sellerId": seller_id,
                "amount": 100000,
                "merchantAccountId": merchant_account_id,
                "dpuOfferId": dpu_offer_id_by_account.get(merchant_account_id, ""),
            })

        return {
            "success": True,
            "merchant_id": self.merchant_id,
            "source_sql": {
                "dpu_3pl_token_sql": tpl_token_sql,
                "dowsure_offer_sql": dowsure_offer_sql,
                "sp_token_sql": sp_token_sql,
            },
            "accounts": accounts,
            "count": len(accounts),
        }

    def mock_underwritten_status(
        self,
        amount: int = None,
        status: str = None,
        limit_application_unique_id: Optional[str] = None,
        use_latest_submitted_limit_application: bool = False,
    ) -> dict:
        """模拟核保状态更新"""
        if amount is None or status is None:
            # 兼容 CLI 模式，但 Web 模式下不会走到这里
            return super().mock_underwritten_status()

        underwritten_status = status
        submitted_limit_application_row = None
        submitted_limit_application_query_sql = None
        if use_latest_submitted_limit_application and not str(limit_application_unique_id or "").strip():
            submitted_limit_application_query_sql = (
                "SELECT * FROM dpu_limit_application "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                "AND status = 'SUBMITTED' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            submitted_limit_application_row = self.db_executor.execute_query(submitted_limit_application_query_sql)
            limit_application_unique_id = (
                (submitted_limit_application_row or {}).get("limit_application_unique_id")
                or (submitted_limit_application_row or {}).get("dpu_limit_application_id")
            )
            if not limit_application_unique_id:
                return {
                    "success": False,
                    "error": "未查询到最新 SUBMITTED dpu_limit_application，无法发送提额 underwritten",
                    "merchant_id": self.merchant_id,
                    "submitted_limit_application_query_sql": submitted_limit_application_query_sql,
                    "submitted_limit_application_row": submitted_limit_application_row,
                }
        selected_limit_application_unique_id = (
            str(limit_application_unique_id or "").strip()
            or self.dpu_limit_application_id
            or "DEFAULT_LIMIT_APP_ID"
        )
        data = self._build_common_webhook_data(
            "underwrittenLimit.completed",
            underwritten_status,
            {
                "dpuMerchantAccountId": [
                    {"MerchantAccountId": self.dpu_auth_token_seller_id}
                ] if self.dpu_auth_token_seller_id else [],
                "dpuApplicationId": self.application_unique_id,
                "dpuLimitApplicationId": selected_limit_application_unique_id,
                "originalRequestId": "req_EFAL17621784619057169",
                "status": underwritten_status,
                "credit": {
                    "marginRate": "2.5",
                    "chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "creditLimit": {
                        "currency": self.preferred_currency,
                        "underwrittenAmount": {"currency": self.preferred_currency, "amount": amount},
                        "availableLimit": {"currency": self.preferred_currency, "amount": 0.00},
                        "signedLimit": {"currency": self.preferred_currency, "amount": 0.00},
                        "watermark": {"currency": self.preferred_currency, "amount": 0.00},
                    }
                }
            }
        )
        result = self._do_post_webhook(data, "核保状态")
        result.update({
            "amount": amount,
            "status": underwritten_status,
            "limit_application_unique_id": selected_limit_application_unique_id,
            "use_latest_submitted_limit_application": use_latest_submitted_limit_application,
            "submitted_limit_application_query_sql": submitted_limit_application_query_sql,
            "submitted_limit_application_row": submitted_limit_application_row,
        })
        return result

    # ======================== 3. 审批 ========================

    def mock_underwritten_status_dowsure(
        self,
        status: str = None,
        merchant_accounts: Optional[list[dict]] = None,
    ) -> dict:
        """Send the DOWSURE underwritten webhook without interactive input."""
        if status is None:
            return super().mock_underwritten_status_dowsure()

        if status not in {"APPROVED", "REJECTED"}:
            return {"success": False, "error": f"Unsupported DOWSURE underwritten status: {status}"}

        if not merchant_accounts:
            dowsure_accounts = self.get_dowsure_merchant_accounts()
            merchant_accounts = [
                {
                    "merchantAccountId": item["merchantAccountId"],
                    "merchantAccountLimit": item.get("merchantAccountLimit"),
                }
                for item in dowsure_accounts.get("accounts", [])
            ]

        clean_accounts = []
        for item in merchant_accounts:
            merchant_account_id = str(item.get("merchantAccountId") or "").strip()
            if not merchant_account_id:
                continue
            merchant_account_limit = item.get("merchantAccountLimit")
            clean_accounts.append({
                "merchantAccountId": merchant_account_id,
                "merchantAccountLimit": None if merchant_account_limit is None else float(merchant_account_limit),
            })

        if not clean_accounts:
            return {"success": False, "error": "No SP merchant accounts found for DOWSURE underwritten webhook"}

        total_underwritten_amount = sum(
            item["merchantAccountLimit"]
            for item in clean_accounts
            if item["merchantAccountLimit"] is not None
        )
        underwritten_amount = total_underwritten_amount
        underwritten_status = status
        data = self._build_common_webhook_data(
            "underwrittenLimit.completed",
            underwritten_status,
            {
                "dpuMerchantAccountId": clean_accounts,
                "dpuLimitApplicationId": self.dpu_limit_application_id,
                "originalRequestId": "req_50111101",
                "status": underwritten_status,
                "failureReason": None,
                "lenderLoanId": "lloan_6001",
                "lenderRepaymentScheduled": "lrs_7001",
                "lenderCreditId": "lcredit_8001",
                "lenderRepaymentId": "lrepay_9001",
                "credit": {
                    "marginRate": "2.5",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "eSign": "PENDING",
                    "creditLimit": {
                        "currency": self.preferred_currency,
                        "underwrittenAmount": {
                            "currency": self.preferred_currency,
                            "amount": f"{underwritten_amount:.2f}",
                        },
                        "availableLimit": {"currency": self.preferred_currency, "amount": "0.00"},
                        "signedLimit": {"currency": self.preferred_currency, "amount": "0.00"},
                        "watermark": {"currency": self.preferred_currency, "amount": "0.00"},
                    },
                },
            },
        )
        result = self._do_post_webhook(
            data,
            "DOWSURE核保状态",
            headers={
                "Authorization": "",
                "Content-Type": "application/json",
                "Cookie": "Cookie_1=value",
            },
        )
        result.update({
            "amount": underwritten_amount,
            "total_merchant_account_limit": total_underwritten_amount,
            "status": underwritten_status,
            "merchant_accounts": clean_accounts,
        })
        return result

    # ======================== 18-20. DOWSURE test callbacks ========================

    @staticmethod
    def _dowsure_headers() -> dict:
        return {
            "clientid": "f4527684987a4d48aaf191a03d8a3176",
            "Content-Type": "application/json",
        }

    def send_dowsure_credit_result_web(
        self,
        application_code: str,
        credit_status: str = "APPROVE",
        start_time: str = "2026-05-26 00:00:00",
        end_time: str = "2027-05-26 00:00:00",
        term: int = 12,
        term_unit: str = "MONTH",
        apr: float = 5.4,
        credit_code: str = "CREDIT_HSEF_TEST_001",
        credit_contract_no: str = "CONTRACT_HSEF_001",
        amount: float = 0.0,
        currency: str = "CNY",
        processing_fee: float = 0.0,
        reason: str = "",
        is_lock: str = "YES",
        credit_result_list: Optional[list] = None,
    ) -> dict:
        """Send DOWSURE credit-result callback without interactive input."""
        application_code = str(application_code or "").strip()
        if not application_code:
            return {"success": False, "error": "applicationCode is required"}

        amount = float(amount)
        credit_status = str(credit_status or "APPROVE").strip().upper()
        if credit_status not in {"APPROVE", "REJECT"}:
            return {"success": False, "error": "creditStatus must be APPROVE or REJECT"}
        reason = str(reason or ("FAIL" if credit_status == "REJECT" else ""))
        term = int(term)
        apr = float(apr)
        term_unit = str(term_unit or "MONTH")
        credit_code = str(credit_code or f"CREDIT_HSEF_TEST_{application_code}")
        credit_contract_no = str(credit_contract_no or "")
        currency = str(currency or "CNY")
        processing_fee = float(processing_fee)
        is_lock = str(is_lock or "YES")
        credit_result_list = credit_result_list or []
        payload = {
            "applicationCode": application_code,
            "creditStatus": credit_status,
            "startTime": str(start_time or "2026-05-26 00:00:00"),
            "endTime": str(end_time or "2027-05-26 00:00:00"),
            "term": term,
            "termUnit": term_unit,
            "apr": apr,
            "creditCode": credit_code,
            "creditContractNo": credit_contract_no,
            "amount": amount,
            "currency": currency,
            "processingFee": processing_fee,
            "reason": reason,
            "isLock": is_lock,
            "creditResultList": [
                {
                    "offerId": str(item.get("offerId") or "").strip(),
                    "sellerId": str(item.get("sellerId") or "").strip(),
                    "creditStatus": credit_status,
                    "term": term,
                    "termUnit": term_unit,
                    "apr": apr,
                    "creditCode": credit_code,
                    "creditContractNo": credit_contract_no,
                    "amount": float(item.get("amount") or 0),
                    "currency": currency,
                    "processingFee": processing_fee,
                    "isLock": is_lock,
                }
                for item in credit_result_list
                if str(item.get("offerId") or "").strip() and str(item.get("sellerId") or "").strip()
            ],
        }

        result = self._do_post_custom(
            "https://sandbox-api.dowsure.com/saasapi/v1/test/credit-result",
            "DOWSURE授信结果",
            json_data=payload,
            headers=self._dowsure_headers(),
        )
        if result.get("success"):
            self.dowsure_application_code = application_code
            self.dowsure_credit_contract_no = payload["creditContractNo"]
        result.update({
            "applicationCode": application_code,
            "creditContractNo": payload["creditContractNo"],
            "amount": amount,
            "currency": payload["currency"],
            "creditStatus": credit_status,
            "reason": reason,
            "payload": payload,
        })
        return result

    def _query_dowsure_seller_center(self, sql: str) -> list:
        """Run a read-only SELECT against the DOWSURE dsb_seller_center DB.

        店铺数据在 Dowsure 库（dsb_seller_center），不在 session 的 DPU 库，
        因此走 .env 里的 DOWSURE_SQL_* 凭据单独连一条只读连接。
        """
        from web.services.ai_service import load_external_sql_data_sources

        sources = load_external_sql_data_sources()
        source = sources.get("dowsure")
        if source is None:
            raise RuntimeError(
                "未配置 DOWSURE_SQL_* 数据源（检查 mockapi/.env 的 DOWSURE_SQL_HOST/USER/PASSWORD）"
            )

        import pymysql

        connection = pymysql.connect(
            host=source.host,
            port=source.port,
            user=source.user,
            password=source.password,
            database=source.database or None,
            charset=source.charset,
            connect_timeout=15,
            read_timeout=30,
            cursorclass=pymysql.cursors.Cursor,
            autocommit=True,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns = [desc[0] for desc in (cursor.description or [])]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows] if columns else []
        finally:
            connection.close()

    def get_webank_seller_offers(self) -> dict:
        """Return the seller offers for the current merchant from the DOWSURE DB.

        merchant_id 即 dsb_seller_center.t_external_user.ext_user_id；
        先查 user_id，再查该 user 名下所有 t_offer 记录，
        前端展示 offer_id / seller_id / marketplace_country。
        """
        merchant_id = str(self.merchant_id or "").strip()
        if not merchant_id:
            return {"success": False, "error": "当前会话缺少 merchant_id，无法查询店铺"}

        try:
            user_rows = self._query_dowsure_seller_center(
                "SELECT user_id FROM t_external_user "
                f"WHERE ext_user_id = {self._sql_literal(merchant_id)} "
                "ORDER BY user_id DESC LIMIT 1"
            )
        except Exception as exc:  # noqa: BLE001 - 网络/凭据类异常回传前端
            return {"success": False, "error": f"查询 t_external_user 失败: {exc}"}

        if not user_rows:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "error": f"未在 dsb_seller_center.t_external_user 查到 ext_user_id={merchant_id} 的记录",
            }

        user_id = user_rows[0].get("user_id")
        if user_id is None:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "error": "t_external_user.user_id 为空",
            }

        try:
            offer_rows = self._query_dowsure_seller_center(
                "SELECT offer_id, seller_id, marketplace_country FROM t_offer "
                f"WHERE user_id = {self._sql_literal(str(user_id))} "
                "ORDER BY offer_id DESC"
            )
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"查询 t_offer 失败: {exc}"}

        offers = []
        for row in offer_rows or []:
            seller_id = row.get("seller_id")
            if not seller_id:
                continue
            offers.append({
                "offer_id": row.get("offer_id"),
                "seller_id": seller_id,
                "marketplace_country": row.get("marketplace_country") or "",
            })

        # application_code 也从 dowsure 库带出（取该 user 最新一条），前端无需手填
        application_code = ""
        try:
            app_rows = self._query_dowsure_seller_center(
                "SELECT application_code FROM t_application_serial "
                f"WHERE user_id = {self._sql_literal(str(user_id))} "
                "ORDER BY id DESC LIMIT 1"
            )
            if app_rows:
                application_code = str(app_rows[0].get("application_code") or "")
        except Exception as exc:  # noqa: BLE001 - application_code 查不到不阻断店铺展示
            log.warning(f"查询 t_application_serial.application_code(ORDER BY id) 失败，回退无排序查询: {exc}")
            try:
                app_rows = self._query_dowsure_seller_center(
                    "SELECT application_code FROM t_application_serial "
                    f"WHERE user_id = {self._sql_literal(str(user_id))} "
                    "LIMIT 1"
                )
                if app_rows:
                    application_code = str(app_rows[0].get("application_code") or "")
            except Exception as exc2:  # noqa: BLE001
                log.warning(f"查询 t_application_serial.application_code 失败: {exc2}")

        return {
            "success": True,
            "merchant_id": merchant_id,
            "user_id": user_id,
            "application_code": application_code,
            "offers": offers,
            "count": len(offers),
        }

    def get_webank_application_code(self) -> dict:
        """Return the latest applicationCode for the current merchant from the DOWSURE DB.

        merchant_id 即 dsb_seller_center.t_external_user.ext_user_id；
        先查 user_id，再取该 user 名下 t_application_serial 最新一条 application_code。
        """
        merchant_id = str(self.merchant_id or "").strip()
        if not merchant_id:
            return {"success": False, "error": "当前会话缺少 merchant_id，无法查询 applicationCode"}

        try:
            user_rows = self._query_dowsure_seller_center(
                "SELECT user_id FROM t_external_user "
                f"WHERE ext_user_id = {self._sql_literal(merchant_id)} "
                "ORDER BY user_id DESC LIMIT 1"
            )
        except Exception as exc:  # noqa: BLE001 - 网络/凭据类异常回传前端
            return {"success": False, "error": f"查询 t_external_user 失败: {exc}"}

        if not user_rows:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "error": f"未在 dsb_seller_center.t_external_user 查到 ext_user_id={merchant_id} 的记录",
            }

        user_id = user_rows[0].get("user_id")
        if user_id is None:
            return {"success": False, "merchant_id": merchant_id, "error": "t_external_user.user_id 为空"}

        try:
            app_rows = self._query_dowsure_seller_center(
                "SELECT application_code FROM t_application_serial "
                f"WHERE user_id = {self._sql_literal(str(user_id))} "
                "ORDER BY id DESC LIMIT 1"
            )
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"查询 t_application_serial 失败: {exc}"}

        if not app_rows:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "user_id": user_id,
                "error": f"未在 dsb_seller_center.t_application_serial 查到 user_id={user_id} 的记录",
            }

        application_code = str(app_rows[0].get("application_code") or "")
        return {
            "success": True,
            "merchant_id": merchant_id,
            "user_id": user_id,
            "application_code": application_code,
        }

    def send_webank_credit_result_web(
        self,
        application_code: str,
        business_sum: Optional[float] = None,
        seller_offers: Optional[list] = None,
    ) -> dict:
        """Send WEBANK credit-result callback (reuses DOWSURE credit-result endpoint).

        每家准入店铺一行 applySeller；标记为不准入的店铺不写入 applySellerList；
        applySellerBusinessSum 与顶层 businessSum 由用户在前端输入；
        businessSum 未传时兼容旧逻辑，自动回退为各准入店铺之和。
        applicationCode 未传时从 DOWSURE 库按当前 merchant 自动带出，前端无需填写。
        """
        application_code = str(application_code or "").strip()
        if not application_code:
            lookup = self.get_webank_application_code()
            if not lookup.get("success"):
                return {"success": False, "error": lookup.get("error", "无法获取 applicationCode")}
            application_code = str(lookup.get("application_code") or "").strip()
        if not application_code:
            return {"success": False, "error": "applicationCode is required"}

        seller_offers = seller_offers or []
        apply_seller_list = []
        total = 0.0
        for offer in seller_offers:
            if str(offer.get("admissionStatus") or "ADMITTED").upper() == "NOT_ADMITTED":
                continue
            seller_id = str(offer.get("applySellerId") or "").strip()
            if not seller_id:
                continue
            seller_business_sum = float(offer.get("applySellerBusinessSum") or 0)
            total += seller_business_sum
            country = str(offer.get("sellerSiteCountryName") or "").strip()
            apply_seller_list.append({
                "applySellerId": seller_id,
                "applySellerBusinessSum": self._webank_amount_str(seller_business_sum),
                "applySellerSiteList": [{"sellerSiteCountryName": country}],
            })

        if not apply_seller_list:
            return {"success": False, "error": "至少需要一家准入店铺"}

        credit_business_sum = float(business_sum) if business_sum is not None else total
        total_str = self._webank_amount_str(credit_business_sum)
        payload = {
            "applicationCode": application_code,
            "creditData": {
                "repayAcctNo": "6225881415569016",
                "repayAcctName": "fengshen测试微众还款账户",
                "repayAcctBankName": "微众银行",
                "repayAcctBankNo": "WEBANK",
                "productList": [
                    {
                        "frontProductId": "501026D",
                        "projectId": "MOCK001",
                        "businessSum": total_str,
                        "availableSum": total_str,
                        "creditStatus": "4",
                        "applyDate": "2026/07/29",
                        "effectDate": "2026/07/29",
                        "deadlineDate": "2027/07/29",
                        "currency": "01",
                        "nextUpdateDate": "2026/08/29",
                        "creditSerialNo": f"WB_MOCK_CREDIT_{application_code}",
                        "refuseReson": "",
                        "applyPlatformList": [
                            {
                                "applyPlatformId": "amazon",
                                "applyPlatformBusinessSum": total_str,
                                "applyPlatformAvailableSum": total_str,
                                "applySellerList": apply_seller_list,
                            }
                        ],
                    }
                ],
            },
        }

        result = self._do_post_custom(
            "https://lendingapi-sit.dowsure.com/dowsure-merchant/v1/test/webank/credit-result",
            "WEBANK授信结果",
            json_data=payload,
            headers={"Content-Type": "application/json"},
        )
        if result.get("success"):
            self.dowsure_application_code = application_code
            self.dowsure_credit_contract_no = ""
        result.update({
            "applicationCode": application_code,
            "creditContractNo": "",
            "amount": credit_business_sum,
            "currency": "CNY",
            "payload": payload,
        })
        return result

    def get_application_code_options(self) -> dict:
        """List selectable applicationCode values for the current phone, newest first.

        三个 credit-result（CCB / WEBANK / CGB）共用这一份下拉数据，
        列表按 t_application.id 倒序，前端默认选中第一条（最新一条）。
        """
        phone_number = str(self.phone_number or "").strip()
        if not phone_number:
            return {"success": False, "error": "当前 Session 缺少手机号，无法查询 applicationCode"}

        application_sql = (
            "SELECT application_code "
            "FROM dsb_seller_center.t_application "
            "WHERE user_id IN ("
            "SELECT id FROM dsb_seller_center.t_user "
            f"WHERE tel = {self._sql_literal(phone_number)}"
            ") ORDER BY id DESC"
        )
        try:
            application_rows = self._query_dowsure_seller_center(application_sql)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": f"查询 applicationCode 失败: {exc}",
                "sql": application_sql,
                "application_codes": [],
            }

        application_codes: list[str] = []
        for row in application_rows or []:
            code = str(row.get("application_code") or "").strip()
            if code and code not in application_codes:
                application_codes.append(code)
        if not application_codes:
            return {
                "success": False,
                "error": f"手机号 {phone_number} 未查询到 applicationCode",
                "sql": application_sql,
                "application_codes": [],
            }
        return {
            "success": True,
            "phone_number": phone_number,
            "application_codes": application_codes,
            "application_code": application_codes[0],
            "count": len(application_codes),
            "sql": application_sql,
        }

    def get_cgb_application_code(self, application_code: Optional[str] = None) -> dict:
        """Resolve the CGB applicationCode, preferring the value chosen in the UI."""
        override = str(application_code or "").strip()
        if override:
            return {
                "success": True,
                "phone_number": str(self.phone_number or ""),
                "application_code": override,
                "sql": "",
            }

        lookup = self.get_application_code_options()
        if not lookup.get("success"):
            return lookup
        return {
            "success": True,
            "phone_number": lookup.get("phone_number"),
            "application_code": lookup.get("application_code"),
            "sql": lookup.get("sql"),
        }

    @staticmethod
    def _cgb_amount_number(value: float) -> int | float:
        numeric_value = float(value)
        return int(numeric_value) if numeric_value.is_integer() else numeric_value

    def send_cgb_credit_result_web(
        self,
        amount: float,
        processing_fee: float,
        credit_status: str = "APPROVE",
        application_code: Optional[str] = None,
    ) -> dict:
        """Query applicationCode by the current phone and submit a CGB credit result."""
        lookup = self.get_cgb_application_code(application_code)
        if not lookup.get("success"):
            return lookup
        phone_number = str(lookup.get("phone_number") or "")
        application_code = str(lookup.get("application_code") or "")
        application_sql = str(lookup.get("sql") or "")
        amount_value = float(amount)
        processing_fee_value = float(processing_fee)
        credit_status_value = str(credit_status or "APPROVE").strip().upper()
        if credit_status_value not in {"APPROVE", "REJECT"}:
            return {"success": False, "error": "creditStatus must be APPROVE or REJECT"}
        amount_number = self._cgb_amount_number(amount_value)
        processing_fee_number = self._cgb_amount_number(processing_fee_value)
        credit_code = f"CGB-CREDIT-{application_code}"
        credit_contract_no = f"CGB-CONTRACT-{application_code}"
        payload = {
            "applicationCode": application_code,
            "creditStatus": credit_status_value,
            "startTime": "2026-08-20 20:10:00",
            "endTime": "2027-08-20 20:10:00",
            "term": 12,
            "termUnit": "MONTH",
            "apr": 0.12,
            "creditCode": credit_code,
            "creditContractNo": credit_contract_no,
            "amount": amount_number,
            "currency": "CNY",
            "processingFee": processing_fee_number,
            "creditStatus": credit_status_value,
            "isLock": "YES",
        }
        result = self._do_post_custom(
            "https://lendingapi-sit.dowsure.com/dowsure-lending-common/v1/credit/result?lenderId=23",
            "CGB授信结果",
            json_data=payload,
            headers={"Content-Type": "application/json"},
        )
        result.update({
            "phone_number": phone_number,
            "applicationCode": application_code,
            "creditCode": credit_code,
            "creditContractNo": credit_contract_no,
            "amount": amount_number,
            "processingFee": processing_fee_number,
            "application_code_sql": application_sql,
            "payload": payload,
        })
        return result

    def send_cgb_loan_result_web(
        self,
        amount: float,
        processing_fee: float,
        application_code: Optional[str] = None,
    ) -> dict:
        """Query applicationCode and submit a CGB loan result."""
        lookup = self.get_cgb_application_code(application_code)
        if not lookup.get("success"):
            return lookup
        phone_number = str(lookup.get("phone_number") or "")
        application_code = str(lookup.get("application_code") or "")
        application_sql = str(lookup.get("sql") or "")
        amount_number = self._cgb_amount_number(amount)
        processing_fee_number = self._cgb_amount_number(processing_fee)
        credit_code = f"CGB-CREDIT-{application_code}"
        credit_contract_no = f"CGB-CONTRACT-{application_code}"
        loan_code = f"CGB-LOAN-{application_code}"
        loan_contract_no = f"CGB-LOAN-CONTRACT-{application_code}"
        start_at = datetime.now()
        try:
            end_at = start_at.replace(year=start_at.year + 1)
        except ValueError:
            end_at = start_at.replace(year=start_at.year + 1, day=28)
        payload = {
            "applicationCode": application_code,
            "creditCode": credit_code,
            "creditContractNo": credit_contract_no,
            "loanCode": loan_code,
            "loanContractNo": loan_contract_no,
            "amount": amount_number,
            "startTime": start_at.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_at.strftime("%Y-%m-%d %H:%M:%S"),
            "term": 12,
            "termUnit": "MONTH",
            "apr": 0.12,
            "currency": "CNY",
            "processingFee": processing_fee_number,
        }
        result = self._do_post_custom(
            "https://lendingapi-sit.dowsure.com/dowsure-lending-common/v1/credit/loan?lenderId=23",
            "CGB支用回传",
            json_data=payload,
            headers={"Content-Type": "application/json"},
        )
        result.update({
            "phone_number": phone_number,
            "applicationCode": application_code,
            "creditCode": credit_code,
            "creditContractNo": credit_contract_no,
            "loanCode": loan_code,
            "loanContractNo": loan_contract_no,
            "amount": amount_number,
            "processingFee": processing_fee_number,
            "application_code_sql": application_sql,
            "payload": payload,
        })
        return result

    def _get_cgb_loan_repayment_context(self, loan_code: Optional[str] = None) -> dict:
        """Resolve the DPU drawdown and DOWSURE loan fields needed by CGB repayment."""
        drawdown_info = self._get_drawdown_info_for_repayment(loan_code)
        if not drawdown_info:
            return {
                "success": False,
                "error": f"未查询到 dpu_drawdown 放款记录，loanCode={loan_code or ''}",
            }

        lender_loan_id = str(drawdown_info.get("lender_loan_id") or "").strip()
        lender_drawdown_id = str(drawdown_info.get("lender_drawdown_id") or "").strip()
        dpu_loan_id = str(drawdown_info.get("loan_id") or "").strip()
        if not lender_drawdown_id:
            return {"success": False, "error": "dpu_drawdown.lender_drawdown_id 为空，无法回传 CGB 还款"}
        if not dpu_loan_id:
            return {"success": False, "error": f"loanCode={lender_drawdown_id} 未找到对应 dpu_loan_id"}

        repayment_count_sql = (
            "SELECT COUNT(*) AS repayment_count "
            "FROM dpu_repayment "
            f"WHERE dpu_loan_id = {self._sql_literal(dpu_loan_id)}"
        )
        try:
            repayment_count_row = self.db_executor.execute_query(repayment_count_sql) or {}
            repayment_count = int(repayment_count_row.get("repayment_count") or 0)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": f"查询 dpu_repayment 记录数失败: {exc}",
                "sql": repayment_count_sql,
            }
        current_term = repayment_count or 1

        if not lender_loan_id:
            return {"success": False, "error": "dpu_drawdown.lender_loan_id 为空，无法回传 CGB 还款"}
        loan_sql = (
            "SELECT partner_loan_code, contract_number "
            "FROM t_loan "
            f"WHERE partner_loan_code = {self._sql_literal(lender_loan_id)} "
            "LIMIT 1"
        )
        try:
            loan_rows = self._query_dowsure_seller_center(loan_sql)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": f"查询 DOWSURE t_loan 失败: {exc}",
                "sql": loan_sql,
            }
        if not loan_rows:
            return {
                "success": False,
                "error": f"DOWSURE t_loan 未找到 partner_loan_code={lender_loan_id}",
                "sql": loan_sql,
            }

        loan_row = loan_rows[0]
        partner_loan_code = str(loan_row.get("partner_loan_code") or "").strip()
        if not partner_loan_code:
            return {
                "success": False,
                "error": f"DOWSURE t_loan.partner_loan_code 为空，lender_loan_id={lender_loan_id}",
                "sql": loan_sql,
            }
        loan_contract_no = str(loan_row.get("contract_number") or "").strip()
        if not loan_contract_no:
            return {
                "success": False,
                "error": f"DOWSURE t_loan.contract_number 为空，partner_loan_code={partner_loan_code}",
                "sql": loan_sql,
            }
        outstanding_amount = drawdown_info.get("outstanding_amount")
        if outstanding_amount is None:
            return {
                "success": False,
                "error": f"dpu_drawdown.outstanding_amount 为空，loanCode={lender_drawdown_id}",
            }
        return {
            "success": True,
            "drawdown_info": drawdown_info,
            "loan_code": partner_loan_code,
            "source_lender_loan_id": lender_loan_id,
            "lender_drawdown_id": lender_drawdown_id,
            "partner_loan_code": partner_loan_code,
            "dpu_loan_id": dpu_loan_id,
            "loan_contract_no": loan_contract_no,
            "outstanding_amount": float(outstanding_amount),
            "repayment_count": repayment_count,
            "current_term": current_term,
            "repayment_count_sql": repayment_count_sql,
            "loan_sql": loan_sql,
        }

    def send_cgb_repayment_result_web(
        self,
        payment_principal: float,
        payment_interest: float,
        payment_overdue_interest: float,
        application_code: Optional[str] = None,
        loan_code: Optional[str] = None,
    ) -> dict:
        """Submit the CGB repayment callback using the selected DPU drawdown loan."""
        application_lookup = self.get_cgb_application_code(application_code)
        if not application_lookup.get("success"):
            return application_lookup
        application_code = str(application_lookup.get("application_code") or "").strip()
        if not application_code:
            return {"success": False, "error": "未查询到 CGB applicationCode"}

        loan_context = self._get_cgb_loan_repayment_context(loan_code)
        if not loan_context.get("success"):
            return {
                **loan_context,
                "applicationCode": application_code,
                "application_code_sql": application_lookup.get("sql"),
            }

        principal = float(payment_principal)
        interest = float(payment_interest)
        overdue_interest = float(payment_overdue_interest)
        deal_amount = round(principal + interest + overdue_interest, 2)
        surplus_principal = max(
            round(float(loan_context["outstanding_amount"]) - principal, 2),
            0.0,
        )
        principal_number = self._cgb_amount_number(principal)
        interest_number = self._cgb_amount_number(interest)
        overdue_number = self._cgb_amount_number(overdue_interest)
        deal_amount_number = self._cgb_amount_number(deal_amount)
        surplus_principal_number = self._cgb_amount_number(surplus_principal)
        current_timestamp = get_current_time("%Y-%m-%d %H:%M:%S")
        resolved_loan_code = loan_context["loan_code"]
        payload = {
            "applicationCode": application_code,
            "currentTerm": loan_context["current_term"],
            "loanCode": resolved_loan_code,
            "loanContractNo": loan_context["loan_contract_no"],
            "serialNo": resolved_loan_code,
            "paymentPrincipal": principal_number,
            "realPaymentPrincipal": principal_number,
            "paymentInterest": interest_number,
            "realPaymentInterest": interest_number,
            "paymentOverdueInterest": overdue_number,
            "realPaymentOverdueInterest": overdue_number,
            "dealAmount": deal_amount_number,
            "surplusPrincipal": surplus_principal_number,
            "dealDate": current_timestamp,
            "realDate": current_timestamp,
        }
        result = self._do_post_custom(
            "https://lendingapi-sit.dowsure.com/dowsure-lending-common/v1/loan/repayment?lenderId=23",
            "CGB还款结果",
            json_data=payload,
            headers={"Content-Type": "application/json"},
        )
        result.update({
            "applicationCode": application_code,
            "loanCode": resolved_loan_code,
            "sourceLenderLoanId": loan_context["source_lender_loan_id"],
            "lenderDrawdownId": loan_context["lender_drawdown_id"],
            "loanContractNo": loan_context["loan_contract_no"],
            "currentTerm": loan_context["current_term"],
            "dealAmount": deal_amount_number,
            "surplusPrincipal": surplus_principal_number,
            "application_code_sql": application_lookup.get("sql"),
            "repayment_count_sql": loan_context["repayment_count_sql"],
            "loan_sql": loan_context["loan_sql"],
            "drawdown_info": loan_context["drawdown_info"],
            "payload": payload,
        })
        return result

    @staticmethod
    def _webank_amount_str(amount: float) -> str:
        """Render an amount as an integer-like string when possible (matches sample)."""
        amount = float(amount)
        return str(int(amount)) if amount == int(amount) else str(amount)

    def get_webank_loan_code(self) -> dict:
        """Return the latest loan_code for the current merchant from the DOWSURE DB.

        merchant_id 即 dsb_seller_center.t_external_user.ext_user_id；
        先查 user_id，再取该 user 名下 t_loan 最新一条 loan_code。
        """
        merchant_id = str(self.merchant_id or "").strip()
        if not merchant_id:
            return {"success": False, "error": "当前会话缺少 merchant_id，无法查询 loan_code"}

        try:
            user_rows = self._query_dowsure_seller_center(
                "SELECT user_id FROM t_external_user "
                f"WHERE ext_user_id = {self._sql_literal(merchant_id)} "
                "ORDER BY user_id DESC LIMIT 1"
            )
        except Exception as exc:  # noqa: BLE001 - 网络/凭据类异常回传前端
            return {"success": False, "error": f"查询 t_external_user 失败: {exc}"}

        if not user_rows:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "error": f"未在 dsb_seller_center.t_external_user 查到 ext_user_id={merchant_id} 的记录",
            }

        user_id = user_rows[0].get("user_id")
        if user_id is None:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "error": "t_external_user.user_id 为空",
            }

        try:
            loan_rows = self._query_dowsure_seller_center(
                "SELECT loan_code FROM t_loan "
                f"WHERE user_id = {self._sql_literal(str(user_id))} "
                "ORDER BY create_time DESC LIMIT 1"
            )
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"查询 t_loan 失败: {exc}"}

        if not loan_rows:
            return {
                "success": False,
                "merchant_id": merchant_id,
                "user_id": user_id,
                "error": f"未在 dsb_seller_center.t_loan 查到 user_id={user_id} 的放款记录",
            }

        loan_code = str(loan_rows[0].get("loan_code") or "")
        return {
            "success": True,
            "merchant_id": merchant_id,
            "user_id": user_id,
            "loan_code": loan_code,
        }

    def send_webank_drawdown_result_web(
        self,
        loan_amount: float,
        service_fee_amount: float,
    ) -> dict:
        """Send WEBANK loan-result (支用结果) callback.

        用户只需输入 loanAmount 与 serviceFee.amount，businessSum/balance 自动同步为 loanAmount；
        loanCode 始终从 DOWSURE t_loan 取当前 merchant 最新一条；
        loanAcctNo 固定为 WB_LOAN_{loanCode}。
        """
        lookup = self.get_webank_loan_code()
        if not lookup.get("success"):
            return {"success": False, "error": lookup.get("error", "无法获取 loanCode")}
        loan_code = str(lookup.get("loan_code") or "").strip()
        if not loan_code:
            return {"success": False, "error": "loanCode is required"}

        loan_amount = float(loan_amount)
        service_fee_amount = float(service_fee_amount)
        amount_num = int(loan_amount) if loan_amount == int(loan_amount) else loan_amount
        service_fee_num = (
            int(service_fee_amount)
            if service_fee_amount == int(service_fee_amount)
            else service_fee_amount
        )
        loan_acct_no = f"WB_LOAN_{loan_code}"
        payload = {
            "loanCode": loan_code,
            "orderStatus": {
                "transStatus": "SUCCESS",
                "putOutDate": "2026/07/29",
                "loanAmount": amount_num,
                "loanAcctNo": loan_acct_no,
            },
            "loanDetail": {
                "loanAcctNo": loan_acct_no,
                "putOutDate": "2026/07/29",
                "corpusPayMethod": "RPT-02",
                "businessSum": amount_num,
                "businessRate": 5.9,
                "periods": "9",
                "dueStatus": "0",
                "maturityDate": "2027/04/29",
                "balance": amount_num,
                "interestBalance1": 0,
            },
            "serviceFee": {
                "amount": service_fee_num,
                "currency": "CNY",
            },
        }

        result = self._do_post_custom(
            "https://lendingapi-sit.dowsure.com/dowsure-merchant/v1/test/webank/loan-result",
            "WEBANK支用结果",
            json_data=payload,
            headers={"Content-Type": "application/json"},
        )
        if result.get("success"):
            self.dowsure_loan_code = loan_code
        result.update({
            "loanCode": loan_code,
            "loanAcctNo": loan_acct_no,
            "loanAmount": amount_num,
            "serviceFeeAmount": service_fee_num,
            "payload": payload,
        })
        return result

    def send_webank_repayment_result_web(
        self,
        payment_principal: float,
        payment_interest: float,
        payment_penalty_interest: float,
        loan_code: Optional[str] = None,
    ) -> dict:
        """Send WEBANK repayment-result callback using the current merchant's latest loan."""
        selected_loan_code = str(loan_code or "").strip()
        lookup = {}
        if not selected_loan_code:
            lookup = self.get_webank_loan_code()
            if not lookup.get("success"):
                return {"success": False, "error": lookup.get("error", "无法获取 loanCode")}
            selected_loan_code = str(lookup.get("loan_code") or "").strip()
        if not selected_loan_code:
            return {"success": False, "error": "loanCode is required"}

        principal = float(payment_principal)
        interest = float(payment_interest)
        penalty_interest = float(payment_penalty_interest)
        drawdown_info = self._get_drawdown_info_for_repayment(selected_loan_code)
        if not drawdown_info:
            return {
                "success": False,
                "error": f"未查询到还款单 dpu_drawdown，无法计算 remainPrincipalAmount | loanCode={selected_loan_code}",
                "loanCode": selected_loan_code,
                "loan_lookup": lookup,
            }
        outstanding_amount = float(drawdown_info.get("outstanding_amount") or 0)
        remain_principal = max(round(outstanding_amount - principal, 2), 0.0)
        request_loan_code = str(drawdown_info.get("lender_drawdown_id") or "").strip()
        if not request_loan_code:
            return {
                "success": False,
                "error": (
                    "dpu_drawdown.lender_drawdown_id 为空，无法组装 WEBANK repayment-result loanCode"
                    f" | selectedLoanCode={selected_loan_code}"
                ),
                "loanCode": selected_loan_code,
                "drawdown_info": drawdown_info,
                "loan_lookup": lookup,
            }

        payload = {
            "loanCode": request_loan_code,
            "serialNo": f"WB_REPAY_{request_loan_code}",
            "dealDate": "2026/07/29",
            "paymentPrincipal": int(principal) if principal == int(principal) else principal,
            "paymentInterest": int(interest) if interest == int(interest) else interest,
            "paymentPenaltyInterest": (
                int(penalty_interest)
                if penalty_interest == int(penalty_interest)
                else penalty_interest
            ),
            "remainPrincipalAmount": (
                int(remain_principal)
                if remain_principal == int(remain_principal)
                else remain_principal
            ),
        }
        result = self._do_post_custom(
            "https://lendingapi-sit.dowsure.com/dowsure-merchant/v1/test/webank/repayment-result",
            "WEBANK还款结果",
            json_data=payload,
            headers={"Content-Type": "application/json"},
        )
        if result.get("success"):
            self.dowsure_loan_code = request_loan_code
        result.update({
            "loanCode": request_loan_code,
            "selectedLoanCode": selected_loan_code,
            "serialNo": payload["serialNo"],
            "outstandingAmount": outstanding_amount,
            "remainPrincipalAmount": remain_principal,
            "drawdown_info": drawdown_info,
            "payload": payload,
        })
        return result

    def send_dowsure_esign_drawdown_result_web(
        self,
        amount: float,
        processing_fee: float,
        application_code: Optional[str] = None,
        credit_contract_no: Optional[str] = None,
    ) -> dict:
        """Send DOWSURE eSign and drawdown callback without interactive input."""
        application_code = str(application_code or self.dowsure_application_code or "").strip()
        credit_contract_no = str(credit_contract_no if credit_contract_no is not None else self.dowsure_credit_contract_no or "")
        if not application_code:
            return {
                "success": False,
                "error": "applicationCode is required. Please run DOWSURE credit result first or input it manually.",
            }

        amount = float(amount)
        processing_fee = float(processing_fee)
        loan_code = f"LOAN_{random.randint(10000, 99999)}"
        payload = {
            "applicationCode": application_code,
            "creditContractNo": credit_contract_no,
            "loanCode": loan_code,
            "loanContractNo": "",
            "amount": amount,
            "startTime": "2026-05-27 12:00:00",
            "endTime": "2027-05-27 12:00:00",
            "term": 12,
            "termUnit": "MONTH",
            "apr": 5.4,
            "currency": "CNY",
            "processingFee": processing_fee,
            "loanStatus": "REPAYMENT",
        }

        result = self._do_post_custom(
            "https://sandbox-api.dowsure.com/saasapi/v1/test/loan",
            "DOWSURE eSign&drawdown结果",
            json_data=payload,
            headers=self._dowsure_headers(),
        )
        if result.get("success"):
            self.dowsure_application_code = application_code
            self.dowsure_credit_contract_no = credit_contract_no
            self.dowsure_loan_code = loan_code
            self.dowsure_loan_contract_no = ""
        result.update({
            "applicationCode": application_code,
            "creditContractNo": credit_contract_no,
            "loanCode": loan_code,
            "loanContractNo": "",
            "amount": amount,
            "processingFee": processing_fee,
            "currency": "CNY",
            "payload": payload,
        })
        return result

    def send_dowsure_repayment_result_web(
        self,
        payment_principal: float,
        payment_overdue_interest: float,
        payment_interest: Optional[float] = None,
        deal_amount: Optional[float] = None,
        surplus_principal: Optional[float] = None,
        application_code: Optional[str] = None,
        loan_code: Optional[str] = None,
    ) -> dict:
        """Send DOWSURE repayment callback without interactive input."""
        application_code = str(application_code or self.dowsure_application_code or "").strip()
        if not application_code:
            return {
                "success": False,
                "error": "applicationCode is required. Please run DOWSURE credit result first or input it manually.",
            }

        drawdown_info = self.db_executor.execute_query(f"""
            SELECT lender_loan_id, outstanding_amount, total_interest_rate
            FROM dpu_drawdown
            WHERE merchant_id = {self._sql_literal(self.merchant_id)}
            AND lender_loan_id IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        """)
        loan_code = str(loan_code or (drawdown_info or {}).get("lender_loan_id") or self.dowsure_loan_code or "").strip()
        if not loan_code:
            return {"success": False, "error": f"未从dpu_drawdown查询到lender_loan_id，merchant_id={self.merchant_id}"}

        payment_principal = float(payment_principal)
        payment_overdue_interest = float(payment_overdue_interest)
        try:
            calculated_interest, _, calculated_surplus, calculation = self._calculate_repayment_amounts(
                drawdown_info or {},
                payment_principal,
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        payment_interest = float(payment_interest) if payment_interest is not None else calculated_interest
        surplus_principal = float(surplus_principal) if surplus_principal is not None else calculated_surplus
        deal_amount = (
            float(deal_amount)
            if deal_amount is not None
            else round(payment_principal + payment_interest + payment_overdue_interest, 2)
        )
        payload = {
            "applicationCode": application_code,
            "currentTerm": 1,
            "loanCode": loan_code,
            "loanContractNo": "",
            "serialNo": f"RPM_{random.randint(10000, 99999)}",
            "paymentPrincipal": payment_principal,
            "realPaymentPrincipal": payment_principal,
            "paymentInterest": payment_interest,
            "realPaymentInterest": payment_interest,
            "paymentOverdueInterest": payment_overdue_interest,
            "realPaymentOverdueInterest": payment_overdue_interest,
            "dealAmount": deal_amount,
            "surplusPrincipal": surplus_principal,
            "dealDate": "2026-05-27 00:00:00",
            "realDate": "2026-05-27 00:00:00",
        }

        result = self._do_post_custom(
            "https://sandbox-api.dowsure.com/saasapi/v1/test/repayment",
            "DOWSURE还款结果",
            json_data=payload,
            headers=self._dowsure_headers(),
        )
        result.update({
            "applicationCode": application_code,
            "loanCode": loan_code,
            "loanContractNo": "",
            "paymentPrincipal": payment_principal,
            "paymentInterest": payment_interest,
            "paymentOverdueInterest": payment_overdue_interest,
            "dealAmount": deal_amount,
            "surplusPrincipal": surplus_principal,
            "calculation": calculation,
            "payload": payload,
        })
        return result

    def retry_dowsure_callback_web(self) -> dict:
        """Retry DOWSURE callback delivery without interactive input."""
        url = "https://sandbox-api.dowsure.com/saasapi/partner/hsef/internal/result/callback/retry?limit=100"
        headers = {
            "clientid": "f4527684987a4d48aaf191a03d8a3176",
        }

        result = self._do_post_custom(
            url,
            "DOWSURE重试请求",
            headers=headers,
        )
        result.update({
            "request_method": "POST",
            "request_url": url,
            "request_headers": headers,
        })
        return result

    def mock_approved_offer_status(self, amount: int = None, status: str = None,
                                   failure_reason_index: int = None,
                                   rejection_reason: str = None) -> dict:
        """模拟审批状态更新"""
        if amount is None or status is None:
            return super().mock_approved_offer_status()

        approved_amount = round(float(amount), 2)
        approved_status = status
        sofr_sql = (
            "SELECT sofr_value "
            "FROM dpu_seller_center.dpu_sofr_data AS dsd "
            "ORDER BY record_date DESC LIMIT 1"
        )
        try:
            raw_sofr_value = self.db_executor.execute_sql(sofr_sql)
            if raw_sofr_value is None:
                raise ValueError("未查询到 SOFR 数据")
            base_rate_decimal = Decimal(str(raw_sofr_value)) / Decimal("100")
        except (InvalidOperation, TypeError, ValueError) as exc:
            msg = f"查询或转换最新 SOFR 失败: {exc}"
            log.error(msg)
            return {"success": False, "error": msg, "sofr_sql": sofr_sql}

        margin_rate_decimal = Decimal("0.02")
        fixed_rate_decimal = base_rate_decimal + margin_rate_decimal

        def _rate_text(value: Decimal) -> str:
            return format(value.normalize(), "f")

        base_rate = _rate_text(base_rate_decimal)
        margin_rate = _rate_text(margin_rate_decimal)
        fixed_rate = _rate_text(fixed_rate_decimal)
        lender_approved_offer_id = self._ensure_credit_offer_lender_approved_offer_id(
            self.application_unique_id,
            approved_amount,
        )
        if not lender_approved_offer_id:
            msg = (
                "未查询到dpu_credit_offer.lender_approved_offer_id，"
                f"无法发起approved-offer | merchant_id={self.merchant_id} | "
                f"application_unique_id={self.application_unique_id}"
            )
            log.error(msg)
            return {"success": False, "error": msg}

        # Keep Web API behavior aligned with the current mock_sit approval flow.
        failure_reason = None
        if approved_status == "RETURNED" and failure_reason_index is not None:
            reasons = list(ReturnedFailureReason)
            if 1 <= failure_reason_index <= len(reasons):
                failure_reason = reasons[failure_reason_index - 1].value
        elif approved_status == "REJECTED":
            failure_reason = rejection_reason if rejection_reason in {"fraud", "others"} else "others"

        request_body = {
            "data": {
                "eventType": "approvedoffer.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "Application approval process completed successfully",
                "enquiryUrl": "https://api.lender.com/enquiry/12345",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "dpuApplicationId": self.application_unique_id,
                    "originalRequestId": "req_1111113579",
                    "status": approved_status,
                    "failureReason": failure_reason,
                    "lenderApprovedOfferId": lender_approved_offer_id,
                    "offer": {
                        "rate": {
                            "chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float",
                            "baseRateType": "SOFR",
                            "baseRate": base_rate,
                            "marginRate": margin_rate,
                            "fixedRate": fixed_rate,
                        },
                        "term": 120,
                        "termUnit": "Days",
                        "mintenor": 3,
                        "maxtenor": 24,
                        "offerEndDate": calculate_future_date(90),
                        "offerStartDate": get_current_time("%Y-%m-%d"),
                        "approvedLimit": {"currency": self.preferred_currency, "amount": approved_amount},
                        "warterMark": {"currency": self.preferred_currency, "amount": 0.00},
                        "signedLimit": {"currency": self.preferred_currency, "amount": 0.00},
                        "feeOrCharge": {
                            "type": "PROCESSING_FEE",
                            "feeOrChargeDate": "2023-10-16",
                            "netAmount": {"currency": self.preferred_currency, "amount": 0.00}
                        }
                    }
                }
            }
        }
        result = self._do_post_webhook(request_body, "审批状态")
        result.update({
            "amount": approved_amount,
            "status": approved_status,
            "failure_reason": failure_reason,
            "application_unique_id": self.application_unique_id,
            "lender_approved_offer_id": lender_approved_offer_id,
            "base_rate": base_rate,
            "margin_rate": margin_rate,
            "fixed_rate": fixed_rate,
        })
        return result

    # ======================== 4/5. PSP 开始/完成 ========================

    def _mock_psp_status(
        self,
        is_start: bool = True,
        psp_status: str = None,
        merchant_account_id: Optional[str] = None,
    ) -> dict:
        """模拟PSP状态更新（参数化版本）"""
        if psp_status is None:
            return super()._mock_psp_status(is_start)

        event_type = "psp.verification.started" if is_start else "psp.verification.completed"

        requested_account_id = str(merchant_account_id or "").strip()
        sp_auth_info = None
        if requested_account_id:
            limit_row = self.db_executor.execute_query(
                "SELECT psp_status FROM dpu_merchant_account_limit "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if str((limit_row or {}).get("psp_status") or "").upper() == "SUCCESS":
                return {
                    "success": False,
                    "error": f"PSP状态已为SUCCESS，不允许选择 | merchant_account_id={requested_account_id}",
                }
            sp_auth_info = self.db_executor.execute_query(
                "SELECT merchant_id, authorization_id, merchant_account_id, status FROM dpu_auth_token "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "AND authorization_party = 'SP' "
                "AND status = 'ACTIVE' "
                "AND authorization_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if not sp_auth_info:
                return {
                    "success": False,
                    "error": f"未查询到可用SP授权记录 | merchant_account_id={requested_account_id}",
                }
        else:
            if is_start:
                latest_sp_auth = self.db_executor.execute_query(
                    "SELECT merchant_id, authorization_id, merchant_account_id, status "
                    "FROM dpu_auth_token "
                    f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                    "AND authorization_party = 'SP' "
                    "AND status = 'ACTIVE' "
                    "AND authorization_id IS NOT NULL "
                    "AND authorization_id != '' "
                    "AND merchant_account_id IS NOT NULL "
                    "AND merchant_account_id != '' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                if latest_sp_auth:
                    latest_account_id = str(latest_sp_auth.get("merchant_account_id") or "").strip()
                    limit_row = self.db_executor.execute_query(
                        "SELECT psp_status FROM dpu_merchant_account_limit "
                        f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                        f"AND merchant_account_id = {self._sql_literal(latest_account_id)} "
                        "ORDER BY created_at DESC LIMIT 1"
                    )
                    if str((limit_row or {}).get("psp_status") or "").upper() == "SUCCESS":
                        return {
                            "success": False,
                            "error": f"最新ACTIVE SP店铺 PSP状态已为SUCCESS，不允许选择 | merchant_account_id={latest_account_id}",
                            "selected_merchant_account_id": latest_account_id,
                        }
                    sp_auth_info = self.db_executor.execute_query(
                        "SELECT merchant_id, authorization_id, merchant_account_id, status "
                        "FROM dpu_auth_token "
                        f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                        f"AND merchant_account_id = {self._sql_literal(latest_account_id)} "
                        "AND authorization_party = 'SP' "
                        "AND status = 'ACTIVE' "
                        "AND authorization_id IS NOT NULL "
                        "AND authorization_id != '' "
                        "ORDER BY created_at DESC LIMIT 1"
                    )
            else:
                sp_auth_info = self._select_hsbc_psp_auth_token_info(for_completed=True)
        if not sp_auth_info:
            return {"success": False, "error": "未查询到SP授权记录"}

        resolved_merchant_account_id = sp_auth_info.get("merchant_account_id")
        merchant_account_id = sp_auth_info["authorization_id"]
        credit_offer_id = self.credit_offer_lender_approved_offer_id
        if not credit_offer_id:
            msg = f"未查询到dpu_credit_offer.lender_approved_offer_id | merchant_id={self.merchant_id}"
            log.error(msg)
            return {"success": False, "error": msg}

        data = self._build_common_webhook_data(
            event_type, psp_status,
            {
                "applicationId": "EFA17590311621044381",
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": merchant_account_id,
                "lenderApprovedOfferId": credit_offer_id,
                "result": psp_status
            }
        )
        result = self._do_post_webhook(data, f"PSP{'开始' if is_start else '完成'}状态")

        if result.get("success"):
            if is_start:
                self.hsbc_psp_pending_account_id_by_merchant[self.merchant_id] = merchant_account_id
            else:
                self.hsbc_psp_completed_account_ids_in_session.add(merchant_account_id)
                self.hsbc_psp_pending_account_id_by_merchant.pop(self.merchant_id, None)

        result.update({
            "status": psp_status,
            "merchant_account_id": merchant_account_id,
            "resolved_merchant_account_id": resolved_merchant_account_id,
            "selected_merchant_account_id": requested_account_id or None,
        })
        return result

    def mock_psp_start_status(self, status: str = None, merchant_account_id: Optional[str] = None) -> dict:
        """模拟PSP开始状态"""
        return self._mock_psp_status(is_start=True, psp_status=status, merchant_account_id=merchant_account_id)

    def mock_psp_completed_status(self, status: str = None, merchant_account_id: Optional[str] = None) -> dict:
        """模拟PSP完成状态"""
        return self._mock_psp_status(is_start=False, psp_status=status, merchant_account_id=merchant_account_id)

    def start_reassessment_web(
        self,
        business_context: str = "REASSESSMENT",
        currency: str = "USD",
        funder_resource: str = "FUNDPARK",
    ) -> dict:
        """Start a merchant credit-limit reassessment from the portal API."""
        steps: list[dict] = []
        headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error

        url = f"{self.api_config.base_url}/dpu-merchant/reassessment/start-reassessment"
        payload = {"businessContext": business_context or "REASSESSMENT"}
        result = self._do_post_custom(
            url,
            "开始额度重新评估",
            json_data=payload,
            headers=headers,
        )
        result.update({
            "business_context": payload["businessContext"],
            "currency": currency,
            "funder_resource": funder_resource,
        })
        return result

    def get_psp_authorization_rows(self) -> dict:
        """Return SP/3PL/PSP status rows grouped by merchant_account_id."""
        if not self.merchant_id:
            return {"success": False, "error": "未获取到 merchant_id", "rows": []}

        auth_rows = self.db_executor.execute_query_all(
            "SELECT merchant_account_id, authorization_party, authorization_id, status, state, "
            "processing_stage, created_at, updated_at "
            "FROM dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND merchant_account_id IS NOT NULL "
            "AND merchant_account_id != '' "
            "AND authorization_party IN ('SP', '3PL') "
            "ORDER BY merchant_account_id, authorization_party, created_at DESC"
        )

        limit_rows = self.db_executor.execute_query_all(
            "SELECT merchant_account_id, psp_status, created_at, updated_at "
            "FROM dpu_merchant_account_limit "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND merchant_account_id IS NOT NULL "
            "AND merchant_account_id != '' "
            "ORDER BY merchant_account_id, created_at DESC"
        )

        grouped: dict[str, dict] = {}
        for row in auth_rows or []:
            merchant_account_id = row.get("merchant_account_id")
            if not merchant_account_id:
                continue
            item = grouped.setdefault(
                merchant_account_id,
                {
                    "merchant_account_id": merchant_account_id,
                    "sp_authorization_id": None,
                    "sp_status": None,
                    "three_pl_authorization_id": None,
                    "three_pl_status": None,
                    "psp_status": None,
                    "psp_updated_at": None,
                },
            )
            party = row.get("authorization_party")
            if party == "SP" and not item.get("sp_status"):
                item["sp_authorization_id"] = row.get("authorization_id")
                item["sp_status"] = row.get("status")
                item["sp_state"] = row.get("state")
                item["sp_processing_stage"] = row.get("processing_stage")
            elif party == "3PL" and not item.get("three_pl_status"):
                item["three_pl_authorization_id"] = row.get("authorization_id")
                item["three_pl_status"] = row.get("status")

        for row in limit_rows or []:
            merchant_account_id = row.get("merchant_account_id")
            if not merchant_account_id:
                continue
            item = grouped.setdefault(
                merchant_account_id,
                {
                    "merchant_account_id": merchant_account_id,
                    "sp_authorization_id": None,
                    "sp_status": None,
                    "three_pl_authorization_id": None,
                    "three_pl_status": None,
                    "psp_status": None,
                    "psp_updated_at": None,
                },
            )
            if item.get("psp_status") is None:
                item["psp_status"] = row.get("psp_status")
                item["psp_updated_at"] = row.get("updated_at") or row.get("created_at")

        rows = sorted(grouped.values(), key=lambda item: item.get("merchant_account_id") or "")
        default_selected_merchant_account_id = None
        default_sp_row = next(
            (
                row for row in auth_rows or []
                if row.get("authorization_party") == "SP"
                and row.get("status") == "ACTIVE"
                and row.get("authorization_id")
            ),
            None,
        )
        if default_sp_row:
            default_selected_merchant_account_id = default_sp_row.get("merchant_account_id")
        return {
            "success": True,
            "rows": rows,
            "default_selected_merchant_account_id": default_selected_merchant_account_id,
        }

    # ======================== 6. 电子签 ========================

    def mock_esign_status(self, signed_amount: int = None, status: str = None) -> dict:
        """模拟电子签状态更新"""
        if signed_amount is None or status is None:
            return super().mock_esign_status()

        esign_status = status
        credit_offer_id = self.credit_offer_lender_approved_offer_id
        if not credit_offer_id:
            msg = (f"未查询到dpu_credit_offer.lender_approved_offer_id | "
                   f"merchant_id={self.merchant_id} | application_unique_id={self.application_unique_id}")
            log.error(msg)
            return {"success": False, "error": msg}

        data = self._build_common_webhook_data(
            "esign.completed", esign_status,
            {
                "lenderApprovedOfferId": credit_offer_id,
                "result": esign_status,
                "signedLimit": {"amount": round(float(signed_amount), 2), "currency": self.preferred_currency}
            }
        )
        result = self._do_post_webhook(data, "电子签状态")
        result.update({"signed_amount": signed_amount, "status": esign_status})
        return result

    # ======================== 7. 放款 ========================

    def mock_drawdown_status(self, amount: float = None, status: str = None,
                              failure_reason_index: int = None) -> dict:
        """模拟放款状态更新"""
        if amount is None or status is None:
            return super().mock_drawdown_status()

        drawdown_status = status
        failure_reason = None
        if drawdown_status == "REJECTED" and failure_reason_index is not None:
            reasons = list(DrawdownFailureReason)
            if 1 <= failure_reason_index <= len(reasons):
                failure_reason = reasons[failure_reason_index - 1].value[0]

        credit_offer_id = self.credit_offer_lender_approved_offer_id
        if not credit_offer_id:
            msg = (f"未查询到dpu_credit_offer.lender_approved_offer_id | "
                   f"merchant_id={self.merchant_id} | application_unique_id={self.application_unique_id}")
            log.error(msg)
            return {"success": False, "error": msg}

        drawdown_ready = self._wait_for_drawdown_submitted(credit_offer_id)
        if not drawdown_ready.get("success"):
            return drawdown_ready
        drawdown_row = drawdown_ready.get("row") or {}
        dpu_loan_id = drawdown_row.get("loan_id") or self.dpu_loan_id
        lender_loan_id = drawdown_row.get("lender_loan_id") or self.lender_loan_id
        lender_drawdown_id = drawdown_row.get("lender_drawdown_id") or "DRA1"

        sofr_sql = (
            "SELECT * "
            "FROM dpu_seller_center.dpu_sofr_data AS dsd "
            "ORDER BY record_date DESC LIMIT 1"
        )
        try:
            sofr_row = self.db_executor.execute_query(sofr_sql)
            raw_sofr_value = (sofr_row or {}).get("sofr_value")
            if raw_sofr_value is None:
                raise ValueError("未查询到 SOFR 数据")
            base_rate = format((Decimal(str(raw_sofr_value)) / Decimal("100")).normalize(), "f")
        except (InvalidOperation, TypeError, ValueError) as exc:
            msg = f"查询或转换最新 SOFR 失败: {exc}"
            log.error(msg)
            return {"success": False, "error": msg, "sofr_sql": sofr_sql}

        current_date = get_current_time("%Y-%m-%d")
        request_body = {
            "data": {
                "eventType": "disbursement.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "Disbursement completed",
                "enquiryUrl": f"/loans?merchantId={self.merchant_id}&loanId=LEND1",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id or "de04dcca3dee4461a581e8ffed19612e",
                    "lenderApprovedOfferId": credit_offer_id,
                    "dpuLoanId": dpu_loan_id,
                    "lenderLoanId": lender_loan_id,
                    "originalRequestId": "e37b91d056114e48a466b433934e2068",
                    "lenderCreditId": "CR1",
                    "lenderCompanyId": "LEND1",
                    "lenderDrawdownId": lender_drawdown_id,
                    "drawdownStatus": drawdown_status,
                    "failureReason": failure_reason,
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system",
                    "disbursement": {
                        "loanAmount": {"currency": self.preferred_currency, "amount": f"{float(amount):.2f}"},
                        "rate": {"chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float", "baseRateType": "SOFR", "baseRate": base_rate,
                                 "marginRate": "2.5"},
                        "term": "90",
                        "termUnit": "Days",
                        "drawdownSuccessDate": current_date,
                        "actualDrawdownDate": current_date
                    },
                    "repayment": {
                        "expectedRepaymentDate": calculate_future_date(90),
                        "expectedRepaymentAmount": {"currency": self.preferred_currency, "amount": f"{float(amount):.2f}"},
                        "repaymentTerm": "90"
                    }
                }
            }
        }
        result = self._do_post_webhook(request_body, "放款状态")
        result.update({
            "amount": amount,
            "status": drawdown_status,
            "drawdown_ready": drawdown_ready,
            "dpu_loan_id": dpu_loan_id,
            "lender_loan_id": lender_loan_id,
            "lender_drawdown_id": lender_drawdown_id,
            "base_rate": base_rate,
            "margin_rate": "2.5",
        })
        return result

    # ======================== 8. 还款开始 ========================

    def mock_repayment_start_status(self, principal_amount: float = None,
                                     outstanding_amount: float = None,
                                     loan_code: Optional[str] = None) -> dict:
        """模拟还款开始状态通知"""
        if principal_amount is None:
            return super().mock_repayment_start_status()

        drawdown_info = self._get_drawdown_info_for_repayment(loan_code)
        if not drawdown_info:
            return {"success": False, "error": "无放款记录，还款操作终止"}

        repayment_status = RepaymentStatus.START.value
        try:
            interest_amount, total_amount, calculated_outstanding_amount, calculation = self._calculate_repayment_amounts(
                drawdown_info,
                float(principal_amount),
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        outstanding_amount = (
            float(outstanding_amount)
            if outstanding_amount is not None
            else calculated_outstanding_amount
        )
        lender_repayment_id = self._get_or_create_lender_repayment_id()

        data = self._build_common_webhook_data(
            "repayment.status", repayment_status,
            {
                "merchantId": drawdown_info["merchant_id"],
                "dpuLoanId": drawdown_info["loan_id"],
                "lenderLoanId": drawdown_info["lender_loan_id"],
                "lenderRepaymentId": lender_repayment_id,
                "repayment": {
                    "status": repayment_status,
                    "failureReason": None,
                    "fundSource": "BankTransfer",
                    "paidOn": get_current_time(),
                    "totalPaidAmount": {"currency": self.preferred_currency, "amount": total_amount},
                    "principalPaidAmount": {"currency": self.preferred_currency, "amount": principal_amount},
                    "interestPaidAmount": {"currency": self.preferred_currency, "amount": interest_amount},
                    "feePaidAmount": {"currency": self.preferred_currency, "amount": 0.00},
                    "outstandingAmount": {"currency": self.preferred_currency, "amount": outstanding_amount}
                }
            }
        )
        result = self._do_post_webhook(data, "还款开始")
        result.update({
            "repayment_id": lender_repayment_id,
            "principal_amount": float(principal_amount),
            "interest_amount": interest_amount,
            "outstanding_amount": outstanding_amount,
            "total_amount": total_amount,
            "calculation": calculation,
        })
        return result

    # ======================== 9. 还款 ========================

    def mock_repayment_status(self, principal_amount: float = None, outstanding_amount: float = None,
                               status: str = None, failure_reason_index: int = None,
                               loan_code: Optional[str] = None) -> dict:
        """模拟还款状态通知"""
        if principal_amount is None or status is None:
            return super().mock_repayment_status()

        drawdown_info = self._get_drawdown_info_for_repayment(loan_code)
        if not drawdown_info:
            return {"success": False, "error": "无放款记录，还款操作终止"}

        repayment_status = status
        failure_reason = None
        if repayment_status == "Failure" and failure_reason_index is not None:
            reason_map = {1: "ER001", 2: "ER002"}
            failure_reason = reason_map.get(failure_reason_index)

        try:
            interest_amount, total_amount, calculated_outstanding_amount, calculation = self._calculate_repayment_amounts(
                drawdown_info,
                float(principal_amount),
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        outstanding_amount = (
            float(outstanding_amount)
            if outstanding_amount is not None
            else calculated_outstanding_amount
        )
        lender_repayment_id = self._get_or_create_lender_repayment_id()

        data = self._build_common_webhook_data(
            "repayment.status", repayment_status,
            {
                "merchantId": drawdown_info["merchant_id"],
                "dpuLoanId": drawdown_info["loan_id"],
                "lenderLoanId": drawdown_info["lender_loan_id"],
                "lenderRepaymentId": lender_repayment_id,
                "repayment": {
                    "status": repayment_status,
                    "failureReason": failure_reason,
                    "fundSource": "BankTransfer",
                    "paidOn": get_current_time(),
                    "totalPaidAmount": {"currency": self.preferred_currency, "amount": total_amount},
                    "principalPaidAmount": {"currency": self.preferred_currency, "amount": principal_amount},
                    "interestPaidAmount": {"currency": self.preferred_currency, "amount": interest_amount},
                    "feePaidAmount": {"currency": self.preferred_currency, "amount": 0.00},
                    "outstandingAmount": {"currency": self.preferred_currency, "amount": outstanding_amount}
                }
            }
        )
        result = self._do_post_webhook(data, "还款")

        if result.get("success"):
            self.clear_lender_repayment_id()

        result.update({
            "repayment_id": lender_repayment_id,
            "status": repayment_status,
            "principal_amount": float(principal_amount),
            "interest_amount": interest_amount,
            "outstanding_amount": outstanding_amount,
            "total_amount": total_amount,
            "calculation": calculation,
        })
        return result

    # ======================== 10. 多店铺 SP 绑定 ========================

    def mock_multi_shop_binding(
        self,
        state: str = None,
        platform_seller_id: str = None,
    ) -> dict:
        """SP 店铺绑定（多店铺第一步）"""
        if state is None:
            return super().mock_multi_shop_binding()

        generated_selling_partner_id = (
            str(platform_seller_id).strip()
            if platform_seller_id and str(platform_seller_id).strip()
            else f"spshouquanfs{random.randint(10000, 99999)}"
        )
        auth_token = ""
        params = {
            "state": state,
            "selling_partner_id": generated_selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }
        full_auth_url = f"{self.api_config.multi_shop_sp_auth_url}?{urlencode(params)}"

        log.info("=" * 60)
        log.info("【多店铺-SP绑定】")
        log.info("=" * 60)

        try:
            response = http_requests.get(
                self.api_config.multi_shop_sp_auth_url,
                params=params,
                headers={
                    "Authorization": f"Bearer {(auth_token or '').strip()}",
                    "content-type": "application/json",
                    "finance-product": "LINE_OF_CREDIT",
                    "funder-resource": "FUNDPARK",
                    "product-currency": self.preferred_currency or "USD",
                },
                timeout=30,
            )
            response_body = self._format_redirect_body_for_log(response.text)
            log.info(f"请求URL: {full_auth_url}")
            log.info(f"响应状态码: {response.status_code}")
            log.info(f"响应Body: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            self.generated_selling_partner_id = None
            error_detail = f"SP绑定失败: {type(e).__name__}: {e}\n  - 请求URL: {full_auth_url}"
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                error_detail += f"\n  - 响应Body: {error_response_body}"
            log.error(error_detail)
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": None,
                "auth_url": full_auth_url,
                "auth_token_source": "dpu_users.token",
                "response_body": error_response_body,
                "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
            }

        self.generated_selling_partner_id = generated_selling_partner_id
        log.info(f"【多店铺】SP绑定成功 | SP绑定ID：{self.generated_selling_partner_id}")
        log.info(f"【多店铺】SP授权URL：{full_auth_url}")

        return {
            "success": True,
            "selling_partner_id": self.generated_selling_partner_id,
            "auth_url": full_auth_url,
            "auth_token_source": "dpu_users.token",
            "status_code": response.status_code,
            "response_body": response_body,
        }


    # ======================== 11. SP 状态更新 ========================

    @staticmethod
    def register_and_run_multishop_flow_web(
        env: str,
        journey: str = "500K",
        currency: str = "USD",
        offline: bool = False,
        funder_resource: str = "FUNDPARK",
        sp_status: str = "SUCCESS",
    ) -> dict:
        """Register a new account and run the multi-shop flow via amazon-sp/auth plus DB verification."""
        if not offline and funder_resource == "DOWSURE":
            return {
                "success": False,
                "stage": "unsupported_combo",
                "error": "DOWSURE 线上模式不支持注册并完成绑店，请切换到线下模式",
            }

        register_result = WebDPUMockService.register_new_account_web(
            env=env,
            journey=journey,
            currency=currency,
            offline=offline,
            funder_resource=funder_resource,
        )
        if not register_result.get("success"):
            return {
                "success": False,
                "stage": "register",
                "error": register_result.get("error", "Register failed"),
                "register_result": register_result,
            }

        session_ctx = None
        steps = []
        try:
            try:
                from web.services.session_manager import session_manager
            except ModuleNotFoundError:
                from mockapi.web.services.session_manager import session_manager

            session_ctx = session_manager.create_session(env, register_result["phone_number"])
            service = session_ctx.service

            if offline and funder_resource == "DOWSURE":
                offer_result = WebDPUMockService.step_create_offer_web(
                    env=env,
                    journey=journey,
                    currency="CNY",
                    yearly_repayment_amount=950000,
                )
                steps.append({
                    "step": "generate offerId",
                    "endpoint": "/api/register/create-offer",
                    "payload": {
                        "currency": "CNY",
                        "yearly_repayment_amount": 950000,
                    },
                    "result": offer_result,
                })
                if not offer_result.get("success"):
                    return {
                        "success": False,
                        "stage": "generate_cny_offer",
                        "error": offer_result.get("error", "generate-shop-performance failed"),
                        "register_result": register_result,
                        "session": {
                            "session_id": session_ctx.session_id,
                            "env": session_ctx.env,
                            "phone_number": session_ctx.phone_number,
                            "merchant_id": session_ctx.merchant_id,
                        },
                        "steps": steps,
                    }

                auth_token = str(register_result.get("token") or "").strip()
                if not auth_token:
                    auth_token = WebDPUMockService._lookup_user_token(
                        service.db_executor,
                        register_result["phone_number"],
                    )
                service.session_user_token = auth_token
                redirect_result = WebDPUMockService.step_amazon_redirect_web(
                    env=env,
                    offer_id=offer_result["offer_id"],
                    phone_number=register_result["phone_number"],
                    currency="CNY",
                    funder_resource="DOWSURE",
                    token=auth_token,
                )
                # The step-by-step scenario exposes TESTOFFER cleanup as its
                # own SQL step. Keep the legacy one-click flow equivalent by
                # running that cleanup here after the redirect succeeds.
                if redirect_result.get("success"):
                    cleanup_result = WebDPUMockService.remove_test_offer_suffix_web(
                        env=env,
                        phone_number=register_result["phone_number"],
                    )
                    if cleanup_result.get("success"):
                        redirect_result["offer_id_update"] = {
                            key: value
                            for key, value in cleanup_result.items()
                            if key != "success"
                        }
                    else:
                        redirect_result.update({
                            "success": False,
                            "stage": "remove_test_offer_suffix",
                            "error": cleanup_result.get(
                                "error", "移除 TESTOFFER 后缀失败"
                            ),
                        })
                steps.append({
                    "step": "GET redirect + POST redirect",
                    "endpoint": "/api/register/amazon-redirect",
                    "payload": {
                        "offer_id": offer_result["offer_id"],
                        "phone_number": register_result["phone_number"],
                        "currency": "CNY",
                        "funder_resource": "DOWSURE",
                    },
                    "result": redirect_result,
                })
                return {
                    "success": redirect_result.get("success", False),
                    "stage": "completed" if redirect_result.get("success") else "amazon_redirect",
                    "summary": "Registered, created session, then ran DS-CNY generate offerId and amazon redirect.",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "offer_id": offer_result["offer_id"],
                    "steps": steps,
                }

            state = service.db_executor.execute_sql("SELECT UUID() AS state")
            if not state:
                state = str(uuid.uuid4())

            auth_token = (register_result.get("token") or "").strip()
            auth_token_source = "signup_response.token"
            if not auth_token:
                auth_token = WebDPUMockService._lookup_user_token(
                    service.db_executor,
                    register_result.get("phone_number", ""),
                )
                auth_token_source = "dpu_users.token"
            if not auth_token:
                return {
                    "success": False,
                    "stage": "auth_token",
                    "error": "Signup did not return token and no token was found in dpu_users",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": "missing",
                    "steps": steps,
                }
            service.session_user_token = auth_token

            generated_selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"
            service.generated_selling_partner_id = generated_selling_partner_id

            sp_auth_url = f"{service.api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-auth-url"
            sp_auth_payload = {
                "state": state,
                "sceneCode": "SHOP_BIND" if offline else "SHOP_BIND_NO_OFFER",
                "sourceCode": funder_resource,
                "redirectUrl": f"{WebDPUMockService._build_portal_base_url(env)}/redirect-loading?state={state}",
            }
            sp_auth_headers = {
                "Authorization": f"Bearer {auth_token}",
                "content-type": "application/json",
                "finance-product": "LINE_OF_CREDIT",
                "funder-resource": funder_resource,
                "product-currency": currency,
                "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            }
            sp_auth_result = service._do_post_custom_with_retry(
                sp_auth_url,
                "SP auth-url",
                json_data=sp_auth_payload,
                headers=sp_auth_headers,
                attempts=3,
                require_json_data=True,
            )
            sp_auth_response_body = sp_auth_result.get("response_body") or ""
            sp_auth_payload_result = sp_auth_result.get("response_json")
            sp_auth_url_recorded = False
            if not sp_auth_result.get("success"):
                sp_auth_state_exists = service.db_executor.execute_sql(
                    "SELECT state FROM dpu_auth_token "
                    f"WHERE merchant_id = '{session_ctx.merchant_id}' "
                    "AND authorization_party = 'SP' "
                    f"AND state = '{state}' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                if sp_auth_state_exists:
                    sp_auth_result["warning"] = "sp-auth-url response data was empty, but dpu_auth_token.state exists; continue"
                    steps.append({
                        "step": "SP auth-url",
                        "endpoint": sp_auth_url,
                        "payload": sp_auth_payload,
                        "result": {**sp_auth_result, "selling_partner_id": generated_selling_partner_id, "auth_token_source": auth_token_source, "db_state": sp_auth_state_exists},
                    })
                    sp_auth_url_recorded = True
                else:
                    return {
                        "success": False,
                        "stage": "sp_auth_url",
                        "error": sp_auth_result.get("error") or sp_auth_result.get("error_message") or "sp-auth-url failed",
                        "register_result": register_result,
                        "session": {
                            "session_id": session_ctx.session_id,
                            "env": session_ctx.env,
                            "phone_number": session_ctx.phone_number,
                            "merchant_id": session_ctx.merchant_id,
                        },
                        "auth_token_source": auth_token_source,
                        "state": state,
                        "steps": steps + [{
                            "step": "SP auth-url",
                            "endpoint": sp_auth_url,
                            "payload": sp_auth_payload,
                            "result": {**sp_auth_result, "selling_partner_id": generated_selling_partner_id, "auth_token_source": auth_token_source},
                        }],
                    }

            if not sp_auth_url_recorded:
                steps.append({
                    "step": "SP auth-url",
                    "endpoint": sp_auth_url,
                    "payload": sp_auth_payload,
                    "result": {
                        "success": True,
                        "status_code": sp_auth_result.get("status_code"),
                        "response_body": sp_auth_response_body,
                        "response_json": sp_auth_payload_result if isinstance(sp_auth_payload_result, dict) else None,
                        "selling_partner_id": generated_selling_partner_id,
                        "auth_token_source": auth_token_source,
                    },
                })
            sp_auth_result_url = f"{service.api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-shop-auth-result?state={state}"
            sp_auth_result_headers = {
                "Authorization": f"Bearer {auth_token}",
                "finance-product": "LINE_OF_CREDIT",
                "product-currency": currency,
                "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            }
            sp_auth_result = service._do_get_custom_with_retry(
                sp_auth_result_url,
                "SP auth-result",
                headers=sp_auth_result_headers,
                attempts=2,
            )
            sp_auth_result_body = sp_auth_result.get("response_body") or ""
            sp_auth_result_payload = sp_auth_result.get("response_json")
            sp_auth_result_recorded = False
            if not sp_auth_result.get("success"):
                state_exists = service.db_executor.execute_sql(
                    "SELECT state FROM dpu_auth_token "
                    f"WHERE merchant_id = '{session_ctx.merchant_id}' "
                    "AND authorization_party = 'SP' "
                    f"AND state = '{state}' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                if state_exists:
                    sp_auth_result["warning"] = "sp-shop-auth-result timed out, but dpu_auth_token.state exists; continue with SP auth callback"
                    steps.append({
                        "step": "SP auth-result",
                        "endpoint": sp_auth_result_url,
                        "payload": {"state": state},
                        "result": {**sp_auth_result, "auth_token_source": auth_token_source, "db_state": state_exists},
                    })
                    sp_auth_result_recorded = True
                else:
                    return {
                        "success": False,
                        "stage": "sp_shop_auth_result",
                        "error": sp_auth_result.get("error") or sp_auth_result.get("error_message") or "sp-shop-auth-result failed",
                        "register_result": register_result,
                        "session": {
                            "session_id": session_ctx.session_id,
                            "env": session_ctx.env,
                            "phone_number": session_ctx.phone_number,
                            "merchant_id": session_ctx.merchant_id,
                        },
                        "auth_token_source": auth_token_source,
                        "state": state,
                        "steps": steps + [{
                            "step": "SP auth-result",
                            "endpoint": sp_auth_result_url,
                            "payload": {"state": state},
                            "result": {**sp_auth_result, "auth_token_source": auth_token_source},
                        }],
                    }

            if not sp_auth_result_recorded:
                steps.append({
                    "step": "SP auth-result",
                    "endpoint": sp_auth_result_url,
                    "payload": {"state": state},
                    "result": {
                        "success": True,
                        "status_code": sp_auth_result.get("status_code"),
                        "response_body": sp_auth_result_body,
                        "response_json": sp_auth_result_payload if isinstance(sp_auth_result_payload, dict) else None,
                        "auth_token_source": auth_token_source,
                    },
                })

            db_state_sql = (
                "SELECT state FROM dpu_auth_token "
                f"WHERE merchant_id = '{session_ctx.merchant_id}' "
                "AND authorization_party = 'SP' "
                f"AND state = '{state}' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            db_state = None
            for _ in range(15):
                db_state = service.db_executor.execute_sql(db_state_sql)
                if db_state:
                    break
                time.sleep(1)
            if not db_state:
                return {
                    "success": False,
                    "stage": "wait_sp_state",
                    "error": "Timeout waiting dpu_auth_token.state after sp-auth-url",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps,
                }

            auth_params = {
                "mws_auth_token": "1235",
                "selling_partner_id": generated_selling_partner_id,
                "spapi_oauth_code": "123123",
                "state": db_state,
            }
            auth_get_url = f"{service.api_config.multi_shop_sp_auth_url}?{urlencode(auth_params)}"
            try:
                auth_get_response = http_requests.get(
                    service.api_config.multi_shop_sp_auth_url,
                    params=auth_params,
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "content-type": "application/json",
                        "finance-product": "LINE_OF_CREDIT",
                        "funder-resource": funder_resource,
                        "product-currency": currency,
                    },
                    timeout=30,
                )
                auth_get_body = service._format_redirect_body_for_log(auth_get_response.text)
                auth_get_response.raise_for_status()
            except http_requests.exceptions.RequestException as exc:
                return {
                    "success": False,
                    "stage": "amazon_sp_auth",
                    "error": str(exc),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": db_state,
                    "steps": steps + [{
                        "step": "SP auth",
                        "endpoint": service.api_config.multi_shop_sp_auth_url,
                        "payload": auth_params,
                        "result": {
                            "success": False,
                            "status_code": exc.response.status_code if getattr(exc, "response", None) is not None else None,
                            "response_body": None if getattr(exc, "response", None) is None else service._format_redirect_body_for_log(exc.response.text),
                            "auth_url": auth_get_url,
                            "auth_token_source": auth_token_source,
                        },
                    }],
                }

            steps.append({
                "step": "SP auth",
                "endpoint": service.api_config.multi_shop_sp_auth_url,
                "payload": auth_params,
                "result": {
                    "success": True,
                    "status_code": auth_get_response.status_code,
                    "response_body": auth_get_body,
                    "selling_partner_id": generated_selling_partner_id,
                    "auth_url": auth_get_url,
                    "auth_token_source": auth_token_source,
                },
            })

            if not offline:
                return {
                    "success": True,
                    "stage": "completed",
                    "summary": "Registered, created session, generated state, and completed Amazon SP auth callback. Online registration already carries 3P, so the flow stops here.",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps,
                }

            manual_offer_row = service._wait_for_manual_offer(
                selling_partner_id=generated_selling_partner_id,
                merchant_id=session_ctx.merchant_id,
                timeout_seconds=120 if offline else 30,
            )
            if not manual_offer_row and not offline:
                link_result = service._do_post_custom(
                    service.api_config.link_sap_3pl_url,
                    "SP-3PL关联补偿",
                    params={"phone": session_ctx.phone_number},
                )
                steps.append({
                    "step": "SP-3PL fallback link",
                    "endpoint": service.api_config.link_sap_3pl_url,
                    "payload": {"phone": session_ctx.phone_number},
                    "result": link_result,
                })
                manual_offer_row = service._wait_for_manual_offer(
                    selling_partner_id=generated_selling_partner_id,
                    merchant_id=session_ctx.merchant_id,
                    timeout_seconds=20,
                )
            if not manual_offer_row:
                manual_offer_debug_rows = service._get_manual_offer_debug_rows(
                    selling_partner_id=generated_selling_partner_id,
                    merchant_id=session_ctx.merchant_id,
                )
                return {
                    "success": False,
                    "stage": "wait_manual_offer",
                    "error": (
                        "Timeout waiting ready dpu_manual_offer after amazon-sp/auth. "
                        "Expected the backend to auto-generate platform_offer_id."
                    ),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": db_state,
                    "manual_offer_debug_rows": manual_offer_debug_rows,
                    "steps": steps,
                }

            ready_selling_partner_id = manual_offer_row.get("platform_seller_id") or generated_selling_partner_id
            service.generated_selling_partner_id = ready_selling_partner_id
            steps.append({
                "step": "manual offer ready",
                "endpoint": "dpu_manual_offer",
                "payload": {
                    "selling_partner_id": generated_selling_partner_id,
                    "merchant_id": session_ctx.merchant_id,
                },
                "result": {
                    "success": True,
                    "requested_selling_partner_id": generated_selling_partner_id,
                    "selling_partner_id": ready_selling_partner_id,
                    "merchant_id": manual_offer_row.get("merchant_id"),
                    "platform_offer_id": manual_offer_row.get("platform_offer_id"),
                    "idempotency_key": manual_offer_row.get("idempotency_key"),
                    "auth_token_source": auth_token_source,
                },
            })

            sp_update_result = service.mock_sp_status_update(
                platform_seller_id=ready_selling_partner_id,
                status=sp_status,
            )
            steps.append({
                "step": "SP status update",
                "endpoint": "/api/mock/sp-status-update",
                "payload": {
                    "session_id": session_ctx.session_id,
                    "platform_seller_id": ready_selling_partner_id,
                    "status": sp_status,
                },
                "result": sp_update_result,
            })
            if not sp_update_result.get("success"):
                return {
                    "success": False,
                    "stage": "sp_status_update",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps,
                }

            redirect_result = service._run_multishop_3pl_redirect_with_post()
            steps.append({
                "step": "3PL redirect",
                "endpoint": "/api/register-and-run-multishop:3pl-redirect",
                "payload": {"session_id": session_ctx.session_id},
                "result": redirect_result,
            })

            return {
                "success": redirect_result.get("success", False),
                "stage": "completed" if redirect_result.get("success") else "multi_shop_3pl_redirect",
                "summary": "Registered, created session, generated state, ran SP auth, verified manual offer, updated SP status, and called 3PL redirect.",
                "register_result": register_result,
                "session": {
                    "session_id": session_ctx.session_id,
                    "env": session_ctx.env,
                    "phone_number": session_ctx.phone_number,
                    "merchant_id": session_ctx.merchant_id,
                },
                "auth_token_source": auth_token_source,
                "state": state,
                "steps": steps,
            }
        except Exception as exc:
            return {
                "success": False,
                "stage": "unexpected_exception",
                "error": str(exc),
                "register_result": register_result,
                "session": None if session_ctx is None else {
                    "session_id": session_ctx.session_id,
                    "env": session_ctx.env,
                    "phone_number": session_ctx.phone_number,
                    "merchant_id": session_ctx.merchant_id,
                },
                "auth_token_source": None if session_ctx is None else "signup_response.token",
                "steps": steps,
            }

    def mock_sp_status_update(self, platform_seller_id: str = None, status: str = None,
                               failure_reason_index: int = None) -> dict:
        """SP 状态更新"""
        if status is None:
            return super().mock_sp_status_update()

        # 优先使用传入值，其次使用 session 缓存，最后按 merchant_id 自动反查
        seller_id = self._resolve_platform_seller_id(platform_seller_id)
        if not seller_id:
            return {
                "success": False,
                "error": "未找到可用的 platform_seller_id。可手动输入，或先执行多店铺 SP 绑定。",
            }

        log.info(f"使用 platform_seller_id: {seller_id}")

        # 查询 idempotency_key 和 platform_offer_id
        idempotency_key = self.db_executor.execute_sql(
            f"SELECT idempotency_key FROM dpu_seller_center.dpu_manual_offer WHERE platform_seller_id = '{seller_id}'"
        )
        platform_offer_id = self.db_executor.execute_sql(
            f"SELECT platform_offer_id FROM dpu_seller_center.dpu_manual_offer "
            f"WHERE platform_seller_id = '{seller_id}' ORDER BY created_at DESC LIMIT 1"
        )

        if not idempotency_key:
            msg = f"未查询到 idempotency_key，platform_seller_id: {seller_id}"
            log.error(msg)
            return {"success": False, "error": msg}

        log.info(f"查询成功 | idempotency_key: {idempotency_key} | platform_offer_id: {platform_offer_id}")

        send_status = status
        failure_reason = ""
        if send_status == "FAIL" and failure_reason_index is not None:
            reason_map = {
                1: "The lender country doesn't match with the Seller reporting country",
                2: "Active credit approval exists",
                3: "An offer already exists for the seller for the same partner product combination",
                4: "others"
            }
            failure_reason = reason_map.get(failure_reason_index, "")

        if send_status == "SUCCESS" and not platform_offer_id:
            msg = f"SUCCESS 场景需要 platform_offer_id，platform_seller_id: {seller_id}"
            log.error(msg)
            return {"success": False, "error": msg}

        payload = {
            "idempotencyKey": idempotency_key,
            "sendStatus": send_status,
            "offerId": platform_offer_id if send_status == "SUCCESS" else "",
            "reason": failure_reason
        }

        result = self._do_post_custom(
            self.api_config.update_offer_url, "SP状态更新",
            json_data=payload, headers={"Content-Type": "application/json"}
        )
        result.update({"status": send_status, "platform_seller_id": seller_id})
        if result.get("success") and send_status == "SUCCESS":
            result["sp_auth_fallback"] = self._ensure_sp_auth_active_from_manual_offer(seller_id)
        return result

    # ======================== 12. 3PL 重定向 ========================

    def _run_multishop_3pl_redirect_with_post(self, platform_offer_id: Optional[str] = None) -> dict:
        """Run the register-and-bind 3PL redirect flow, including the required POST callback."""
        seller_id = None
        platform_offer_id = str(platform_offer_id or "").strip()
        if not platform_offer_id:
            seller_id = self._resolve_platform_seller_id()
            if not seller_id:
                return {"success": False, "error": "未找到可用的 SP 绑定ID，请先执行SP店铺绑定或确认商户已有记录"}

            platform_offer_id = self.get_platform_offer_id(seller_id)
            if not platform_offer_id:
                msg = f"seller_id: {seller_id} 无对应platform_offer_id"
                log.error(msg)
                return {"success": False, "error": msg}

        full_redirect_url = f"{self.api_config.redirect_url}?offerId={platform_offer_id}"
        get_request_info = {
            "method": "GET",
            "url": self.api_config.redirect_url,
            "headers": {},
            "params": {"offerId": platform_offer_id},
            "body": None,
        }

        log.info("=" * 60)
        log.info("【注册并完成绑店-3PL重定向】")
        log.info("=" * 60)

        try:
            response = http_requests.get(self.api_config.redirect_url, params={"offerId": platform_offer_id}, timeout=30)
            response_body = self._format_redirect_body_for_log(response.text)
            log.info(f"3PL GET URL: {self.api_config.redirect_url}")
            log.info(f"3PL GET Params: offerId={platform_offer_id}")
            log.info(f"3PL GET status: {response.status_code}")
            log.info(f"3PL GET response: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
            log.error(f"3PL GET failed: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": seller_id,
                "platform_offer_id": platform_offer_id,
                "redirect_url": full_redirect_url,
                "redirect_get": {
                    "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
                    "response_body": error_response_body,
                    "request_info": get_request_info,
                    "response_info": {
                        "status_code": e.response.status_code,
                        "headers": dict(e.response.headers),
                        "body": error_response_body,
                        "json": None,
                    } if getattr(e, "response", None) is not None else None,
                },
                "request_info": get_request_info,
            }

        post_payload = {
            "authToken": "mock",
            "expireOn": "null",
            "keyId": "null",
            "offerId": platform_offer_id,
            "relayPage": 1,
            "returnUrl": "null",
            "signature": "null",
        }
        post_headers = {"Content-Type": "application/json"}
        post_request_info = {
            "method": "POST",
            "url": self.api_config.redirect_url,
            "headers": post_headers,
            "params": None,
            "body": post_payload,
        }
        try:
            post_response = http_requests.post(
                self.api_config.redirect_url,
                json=post_payload,
                headers=post_headers,
                timeout=60,
            )
            post_response_body = self._format_redirect_body_for_log(post_response.text)
            log.info(f"3PL POST URL: {self.api_config.redirect_url}")
            log.info(f"3PL POST Body: {json.dumps(post_payload, ensure_ascii=False)}")
            log.info(f"3PL POST status: {post_response.status_code}")
            log.info(f"3PL POST response: {post_response_body}")
            post_response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
            log.error(f"3PL POST failed: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": seller_id,
                "platform_offer_id": platform_offer_id,
                "redirect_url": full_redirect_url,
                "redirect_get": {
                    "status_code": response.status_code,
                    "response_body": response_body,
                    "request_info": get_request_info,
                    "response_info": {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response_body,
                        "json": None,
                    },
                },
                "redirect_post": {
                    "payload": post_payload,
                    "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
                    "response_body": error_response_body,
                    "request_info": post_request_info,
                    "response_info": {
                        "status_code": e.response.status_code,
                        "headers": dict(e.response.headers),
                        "body": error_response_body,
                        "json": None,
                    } if getattr(e, "response", None) is not None else None,
                },
                "request_info": post_request_info,
            }

        return {
            "success": True,
            "selling_partner_id": seller_id,
            "platform_offer_id": platform_offer_id,
            "redirect_url": full_redirect_url,
            "status_code": response.status_code,
            "response_body": response_body,
            "redirect_get": {
                "status_code": response.status_code,
                "response_body": response_body,
                "request_info": get_request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": None,
                },
            },
            "redirect_post": {
                "payload": post_payload,
                "status_code": post_response.status_code,
                "response_body": post_response_body,
                "request_info": post_request_info,
                "response_info": {
                    "status_code": post_response.status_code,
                    "headers": dict(post_response.headers),
                    "body": post_response_body,
                    "json": None,
                },
            },
            "request_info": post_request_info,
            "response_info": {
                "status_code": post_response.status_code,
                "headers": dict(post_response.headers),
                "body": post_response_body,
                "json": None,
            },
        }

    def mock_multi_shop_3pl_redirect(self) -> dict:
        """3PL 重定向（多店铺第二步）"""
        seller_id = self._resolve_platform_seller_id()
        if not seller_id:
            return {"success": False, "error": "未找到可用的 SP 绑定ID，请先执行SP店铺绑定或确认商户已有记录"}

        platform_offer_id = self.get_platform_offer_id(seller_id)
        if not platform_offer_id:
            msg = f"seller_id: {seller_id} 无对应platform_offer_id"
            log.error(msg)
            return {"success": False, "error": msg}

        full_redirect_url = f"{self.api_config.redirect_url}?offerId={platform_offer_id}"

        log.info("=" * 60)
        log.info("【多店铺-3PL重定向】")
        log.info("=" * 60)

        try:
            response = http_requests.get(self.api_config.redirect_url, params={"offerId": platform_offer_id}, timeout=30)
            response_body = self._format_redirect_body_for_log(response.text)
            log.info(f"请求URL: {self.api_config.redirect_url}")
            log.info(f"请求Params: offerId={platform_offer_id}")
            log.info(f"响应状态码: {response.status_code}")
            log.info(f"响应Body: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_detail = f"【多店铺-3PL重定向】请求失败: {type(e).__name__}: {e}\n  - 请求URL: {full_redirect_url}"
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                error_detail += f"\n  - 响应Body: {error_response_body}"
            log.error(error_detail)
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": seller_id,
                "platform_offer_id": platform_offer_id,
                "redirect_url": full_redirect_url,
                "response_body": error_response_body,
                "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
            }

        log.info(f"【多店铺】SP绑定ID：{seller_id}")
        log.info(f"【多店铺】platform_offer_id：{platform_offer_id}")
        log.info(f"【多店铺】3PL重定向URL：{full_redirect_url}")

        return {
            "success": True,
            "selling_partner_id": seller_id,
            "platform_offer_id": platform_offer_id,
            "redirect_url": full_redirect_url,
            "status_code": response.status_code,
            "response_body": response_body,
        }

    # ======================== 13. 系统事件通知 ========================

    def mock_system_event_notification(self, event_type: str = None,
                                        application_unique_id: str = None,
                                        error_code: str = None) -> dict:
        """发送系统事件通知"""
        if event_type is None:
            return super().mock_system_event_notification()

        log.info(f"开始发送系统事件通知 | eventType={event_type}")

        # 获取 applicationUniqueId
        app_unique_id = application_unique_id or self.application_unique_id
        if not app_unique_id:
            return {"success": False, "error": "需要提供 application_unique_id"}

        # 查询 applicationId
        application_id = self.db_executor.execute_sql(
            f"SELECT fund_application_id FROM dpu_seller_center.dpu_lender_shop_data_transmission "
            f"WHERE application_unique_id = '{app_unique_id}' LIMIT 1"
        )
        if not application_id:
            log.warning("未找到 applicationId，使用默认值")
            application_id = "PLPUAT000000652489"

        # 查询 thirdPartyCustomerId
        third_party_customer_id = self.db_executor.execute_sql(
            f"SELECT merchant_id FROM dpu_seller_center.dpu_lender_shop_data_transmission "
            f"WHERE application_unique_id = '{app_unique_id}' LIMIT 1"
        )
        if not third_party_customer_id:
            log.warning("未找到 merchant_id，使用默认值")
            third_party_customer_id = "67379738b310487393c3947188e8a204"

        # 处理 errorCode
        actual_error_code = ""
        if event_type == "EXCEPTION-APPLICATION-CREATION":
            actual_error_code = error_code or "B-6003"

        payload = {
            "applicationUniqueId": app_unique_id,
            "eventType": event_type,
            "eventReceiver": "dpu",
            "eventData": {
                "thirdPartyCustomerId": third_party_customer_id,
                "applicationId": application_id,
                "eventTime": get_current_time(),
                "errorCode": actual_error_code,
                "errorMessage": ""
            }
        }

        headers = {
            "Authorization": "JWS eyJ2ZXIiOiIxLjAiLCJraWQiOiJCQzAwMDAxMTA2NyIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJCQzAwMDAxMTA2NyIsImF1ZCI6IkdCQS1FQ09NTSIsInBheWxvYWRfaGFzaF9hbGciOiJTSEEtMjU2IiwicGF5bG9hZF9oYXNoIjoiOWFkNjQyZmM4MGY1YmJkZTYwZDFhMmI1ZjJmMTJkNjY4OTJiZGQ4MGVlMzc4ODUzOTE4NTA2MmJkNjFjMzg5YyIsImlhdCI6MTc2OTA3NjQ4OCwianRpIjoiYjQ1OWJjMWYtZWNkZi00Mjc4LWIwMjMtNTQ2YzM4Y2ZmNWRhIn0.ULI-b7nl8E1n4JXjCR7jAOY1maoUlL5_kBex-FHITCfVa7VPRPPKRiU4RZhFlGVdRS1sJzGmlce4Gn0nidbWUISI7JzN-94N3GxMuMinVoLi6U_3SIH1a3Ykx4LdSACRL7DC2Jw1kcjKqgzaO-30TnR4iR1JtwcUPqcmSII8CxoYDFrrMh-Hqwq16fvj92VcgkMQB_TPu0ZezwBus01YLetiA4wCkCk-1Jq4K5E8EImHzDUISAiHyDovQo79t37bTX18ir0q1MvSqIgCDyMcb7-13REKXDjAE6AJKxprwE6RsrDULc0texMPra2j1PUdIfGGggsBjz0dlHDuaHXyCw",
            "X-HSBC-Request-Correlation-Id": "581772f3-8791-4466-98bf-bd5f13a6daff",
            "X-HSBC-E2E-Trust-Token": "5C2413B10CA3B23A",
            "X-HSBC-Request-Idempotency-Key": "8f5a23ce-a3d2-4b46-98f3-cac50b542abd",
            "X-HSBC-PROFILEID": "DPUSIT-B2B-P-2025-ACTIVE",
            "Accept": "*/*",
            "Funder-Resource": "HSBC",
            "Content-Type": "application/json"
        }

        url = f"{self.api_config.base_url}/dpu-openapi/notification/system-events"
        result = self._do_post_custom(url, "系统事件通知", json_data=payload, headers=headers)
        result.update({"event_type": event_type, "application_unique_id": app_unique_id})
        return result

    def handle_boss_application_status_web(
        self,
        approved_date: str = "2026-06-01",
        approved_limit: str = "10000.00",
        interest_type: str = "Float",
        rate: str = "3.0",
        tenor: int = 120,
        application_status: str = "APPROVED",
        update_by: str = "boss",
        psp_status: str = "Init",
        psp_aggregate_status: str = "NORMAL",
        currency: str = "USD",
        funder_resource: str = "HSBC",
        event_type: str = "NTB-customer",
        application_unique_id: Optional[str] = None,
    ) -> dict:
        """Call BOSS application status webhook with the latest application id."""
        steps: list[dict] = []
        merchant_id = self.merchant_id
        if not merchant_id:
            return {"success": False, "error": "当前 session 没有 merchant_id，无法查询最新申请单", "steps": steps}

        requested_application_unique_id = str(application_unique_id or "").strip()
        if requested_application_unique_id:
            latest_application_sql = (
                "SELECT * FROM dpu_seller_center.dpu_application "
                f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
                f"AND application_unique_id = {self._sql_literal(requested_application_unique_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
        else:
            latest_application_sql = (
                "SELECT * FROM dpu_seller_center.dpu_application "
                f"WHERE merchant_id = {self._sql_literal(merchant_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
        try:
            with DatabaseExecutor(env=self.db_executor.env) as db:
                latest_application = db.execute_query(latest_application_sql) or {}
        except Exception as exc:
            return {
                "success": False,
                "error": f"查询最新 dpu_application 失败: {exc}",
                "latest_application_query_sql": latest_application_sql,
                "steps": steps,
            }

        application_unique_id = str(latest_application.get("application_unique_id") or "").strip()
        if not application_unique_id:
            return {
                "success": False,
                "error": "未查询到指定/最新 dpu_application.application_unique_id",
                "latest_application_query_sql": latest_application_sql,
                "latest_application": latest_application,
                "steps": steps,
            }
        self.select_application(application_unique_id)

        auth_token = str(self.session_user_token or "").strip()
        if not auth_token:
            auth_token = self._lookup_user_token(self.db_executor, self.phone_number)
        if not auth_token:
            auth_token = self._login_user_token(currency=currency, funder_resource=funder_resource)
        if not auth_token:
            return {"success": False, "error": "未查询到用户 token，无法调用 BOSS application status webhook", "steps": steps}

        payload = {
            "approvedDate": approved_date,
            "approvedLimit": str(approved_limit),
            "interestType": interest_type,
            "rate": str(rate),
            "tenor": int(tenor),
            "applicationStatus": application_status,
            "applicationUniqueId": application_unique_id,
            "updateBy": update_by,
            "pspStatus": psp_status,
            "pspAggregateStatus": psp_aggregate_status,
            "currency": currency,
            "eventType": event_type,
        }
        host_header = self.api_config.base_url.replace("https://", "").replace("http://", "")
        portal_base_url = self._build_portal_base_url(self.db_executor.env)
        headers = {
            "X-Internal-Request": "true",
            "Authorization": auth_token,
            "Funder-Resource": funder_resource,
            "accept-language": "en",
            "finance-product": "LINE_OF_CREDIT",
            "origin": portal_base_url,
            "priority": "u=1, i",
            "product-currency": currency,
            "referer": f"{portal_base_url}/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": host_header,
            "Connection": "keep-alive",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            "x-hsbc-request-correlation-id": "",
            "x-hsbc-request-idempotency-key": "",
        }
        url = f"{self.api_config.base_url}/dpu-merchant/webhook/handleBossApplicationStatus"
        result = self._do_post_custom(url, "BOSS application status", json_data=payload, headers=headers)
        step_result = {
            "success": result.get("success"),
            "status_code": result.get("status_code"),
            "response": result.get("response"),
            "response_body": result.get("response_body"),
            "response_headers": result.get("response_headers"),
            "response_json": result.get("response_json"),
            "error_message": result.get("error_message"),
            "request_info": result.get("request_info"),
            "response_info": result.get("response_info"),
        }
        steps.append({
            "step": "boss.handleBossApplicationStatus",
            "endpoint": url,
            "payload": payload,
            "request_info": result.get("request_info"),
            "response_info": result.get("response_info"),
            "result": step_result,
        })
        result.update({
            "application_unique_id": application_unique_id,
            "latest_application_query_sql": latest_application_sql,
            "latest_application": latest_application,
            "actual_request": result.get("request_info"),
            "actual_response": result.get("response_info"),
            "steps": steps,
        })
        return result

    # ======================== 16. Abandon(application.status) ========================

    def mock_application_abandon_status(self, abandon_reason: str = None) -> dict:
        """Send application.status Abandoned notification without interactive input."""
        if abandon_reason is None:
            return super().mock_application_abandon_status()

        valid_reasons = {
            "SellerCancelled",
            "OfferExpired",
            "ApplicationInfoNotSubmitted",
            "LenderOfferNotReturned",
        }
        if abandon_reason not in valid_reasons:
            return {"success": False, "error": f"不支持的 abandon_reason: {abandon_reason}"}

        dpu_application_id = self.credit_offer_application_unique_id or self.application_unique_id
        if not self.merchant_id:
            return {"success": False, "error": "未获取到 merchant_id，无法发送 abandon 通知"}
        if not dpu_application_id:
            return {"success": False, "error": "未获取到 dpuApplicationId，无法发送 abandon 通知"}

        request_body = {
            "data": {
                "eventType": "application.status",
                "eventId": generate_uuid37(),
                "eventMessage": "Application approval process completed successfully",
                "enquiryUrl": "https://api.lender.com/enquiry/12345",
                "datetime": get_current_time("%Y-%m-%dT%H:%M:%S"),
                "details": {
                    "merchantId": self.merchant_id,
                    "dpuApplicationId": dpu_application_id,
                    "status": "Abandoned",
                    "abandonReason": abandon_reason,
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system"
                }
            }
        }

        result = self._do_post_webhook(request_body, "Abandon状态")
        result.update({"dpu_application_id": dpu_application_id, "abandon_reason": abandon_reason})
        return result

    # ======================== 14. PSP 开始（HSBC） ========================

    def mock_psp_start_status_hsbc(self, merchant_account_id: Optional[str] = None) -> dict:
        """发送HSBC版PSP开始通知"""
        log.info("开始处理PSP开始（HSBC）...")
        return self._send_hsbc_psp_notification_web(
            event_type="psp.verification.started",
            result="PROCESSING",
            failure_reason=None,
            title="PSP开始（HSBC）",
            for_completed=False,
            merchant_account_id=merchant_account_id,
        )

    # ======================== 15. PSP 完成（HSBC） ========================

    def mock_psp_completed_status_hsbc(self, result: str = None, merchant_account_id: Optional[str] = None) -> dict:
        """发送HSBC版PSP完成通知"""
        if result is None:
            return super().mock_psp_completed_status_hsbc()

        log.info("开始处理PSP完成（HSBC）...")
        failure_reason = None if result == "SUCCESS" else "Bank account verification failed"
        return self._send_hsbc_psp_notification_web(
            event_type="psp.verification.completed",
            result=result,
            failure_reason=failure_reason,
            title="PSP完成（HSBC）",
            for_completed=True,
            merchant_account_id=merchant_account_id,
        )

    def _select_initial_hsbc_psp_limit_row(self) -> tuple[Optional[str], Optional[dict]]:
        sql = (
            "SELECT * FROM dpu_merchant_account_limit "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND psp_status = 'INITIAL' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        return sql, self.db_executor.execute_query(sql)

    def _lookup_active_sp_auth_for_merchant_account(self, merchant_account_id: str) -> tuple[str, Optional[dict]]:
        sql = (
            "SELECT merchant_id, authorization_id, merchant_account_id, status, created_at, updated_at "
            "FROM dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f"AND merchant_account_id = {self._sql_literal(merchant_account_id)} "
            "AND authorization_party = 'SP' "
            "AND status = 'ACTIVE' "
            "AND authorization_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1"
        )
        return sql, self.db_executor.execute_query(sql)

    def _wait_until_hsbc_psp_account_not_initial(
        self,
        merchant_account_id: str,
        timeout_seconds: int = 12,
        interval_seconds: float = 1.0,
    ) -> dict:
        sql = (
            "SELECT merchant_account_id, psp_status, created_at, updated_at "
            "FROM dpu_merchant_account_limit "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f"AND merchant_account_id = {self._sql_literal(merchant_account_id)} "
            "ORDER BY created_at DESC LIMIT 1"
        )
        deadline = time.time() + timeout_seconds
        latest_row = None
        while time.time() <= deadline:
            latest_row = self.db_executor.execute_query(sql)
            status = str((latest_row or {}).get("psp_status") or "").upper()
            if status and status != "INITIAL":
                return {"success": True, "query_sql": sql, "row": latest_row, "psp_status": status}
            time.sleep(interval_seconds)
        return {"success": False, "query_sql": sql, "row": latest_row, "psp_status": str((latest_row or {}).get("psp_status") or "")}

    def complete_all_hsbc_psp_bindings_web(self, result: str = "SUCCESS", max_iterations: int = 20) -> dict:
        """Loop over all INITIAL HSBC merchant account limits and send start + completed PSP notifications."""
        if not self.merchant_id:
            return {"success": False, "error": "未查询到 merchant_id，无法完成 HSBC PSP 绑定"}

        result = result or "SUCCESS"
        processed: list[dict] = []
        for index in range(1, max_iterations + 1):
            limit_sql, limit_row = self._select_initial_hsbc_psp_limit_row()
            if not limit_row:
                return {
                    "success": True,
                    "message": "所有 INITIAL 店铺 PSP 绑定已处理完成",
                    "processed_count": len(processed),
                    "processed": processed,
                    "final_lookup_sql": limit_sql,
                }

            merchant_account_id = str(limit_row.get("merchant_account_id") or "").strip()
            if not merchant_account_id:
                return {
                    "success": False,
                    "error": "查询到 INITIAL 记录但 merchant_account_id 为空",
                    "lookup_sql": limit_sql,
                    "limit_row": limit_row,
                    "processed": processed,
                }

            auth_sql, auth_row = self._lookup_active_sp_auth_for_merchant_account(merchant_account_id)
            current = {
                "iteration": index,
                "lookup_sql": limit_sql,
                "limit_row": limit_row,
                "merchant_account_id": merchant_account_id,
                "sp_auth_lookup_sql": auth_sql,
                "sp_auth_row": auth_row,
            }
            if not auth_row:
                current["success"] = False
                current["error"] = "未查询到该店铺 ACTIVE SP 授权记录"
                processed.append(current)
                return {
                    "success": False,
                    "error": f"未查询到该店铺 ACTIVE SP 授权记录 | merchant_account_id={merchant_account_id}",
                    "processed_count": len(processed),
                    "processed": processed,
                }

            start_result = self.mock_psp_start_status_hsbc(merchant_account_id=merchant_account_id)
            current["start_result"] = start_result
            if not start_result.get("success"):
                current["success"] = False
                current["error"] = start_result.get("error") or "psp-hsbc-start failed"
                processed.append(current)
                return {
                    "success": False,
                    "error": current["error"],
                    "processed_count": len(processed),
                    "processed": processed,
                }

            completed_result = self.mock_psp_completed_status_hsbc(
                result=result,
                merchant_account_id=merchant_account_id,
            )
            current["completed_result"] = completed_result
            if not completed_result.get("success"):
                current["success"] = False
                current["error"] = completed_result.get("error") or "psp-hsbc-completed failed"
                processed.append(current)
                return {
                    "success": False,
                    "error": current["error"],
                    "processed_count": len(processed),
                    "processed": processed,
                }

            status_wait = self._wait_until_hsbc_psp_account_not_initial(merchant_account_id)
            current["status_wait"] = status_wait
            current["success"] = bool(status_wait.get("success"))
            processed.append(current)
            if not status_wait.get("success"):
                return {
                    "success": False,
                    "error": f"PSP 通知已发送，但店铺状态仍为 INITIAL | merchant_account_id={merchant_account_id}",
                    "processed_count": len(processed),
                    "processed": processed,
                }

        limit_sql, limit_row = self._select_initial_hsbc_psp_limit_row()
        return {
            "success": not bool(limit_row),
            "error": "达到最大循环次数后仍存在 INITIAL 店铺" if limit_row else None,
            "processed_count": len(processed),
            "processed": processed,
            "final_lookup_sql": limit_sql,
            "remaining_initial_row": limit_row,
        }

    def _get_hsbc_psp_notification_context_web(
        self,
        for_completed: bool = False,
        merchant_account_id: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """获取HSBC版PSP通知上下文（Web版，不调用 input）"""
        requested_account_id = str(merchant_account_id or "").strip()
        if requested_account_id:
            limit_row = self.db_executor.execute_query(
                "SELECT psp_status FROM dpu_merchant_account_limit "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if str((limit_row or {}).get("psp_status") or "").upper() == "SUCCESS":
                log.error(f"PSP状态已为SUCCESS，不允许选择 | merchant_account_id={requested_account_id}")
                return None
            sp_auth_info = self.db_executor.execute_query(
                "SELECT merchant_id, authorization_id, merchant_account_id, status FROM dpu_auth_token "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "AND authorization_party = 'SP' "
                "AND status = 'ACTIVE' "
                "AND authorization_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1"
            )
        else:
            sp_auth_info = self._select_hsbc_psp_auth_token_info(for_completed=for_completed)
        if not sp_auth_info:
            return None

        limit_application_unique_id = self.dpu_limit_application_id
        if not limit_application_unique_id:
            log.warning("未查询到limitApplicationUniqueId，使用默认值")
            limit_application_unique_id = "DEFAULT_LIMIT_APP_ID"

        return {
            "merchant_id": sp_auth_info["merchant_id"],
            "merchant_account_id": sp_auth_info["authorization_id"],
            "limit_application_unique_id": limit_application_unique_id
        }

    def _send_hsbc_psp_notification_web(self, event_type: str, result: str,
                                         failure_reason: Optional[str], title: str,
                                         for_completed: bool = False,
                                         merchant_account_id: Optional[str] = None) -> dict:
        """发送HSBC版PSP通知（Web版）"""
        context = self._get_hsbc_psp_notification_context_web(
            for_completed=for_completed,
            merchant_account_id=merchant_account_id,
        )
        if not context:
            return {"success": False, "error": "无法获取HSBC PSP通知上下文"}

        payload = {
            "eventType": event_type,
            "eventReceiver": "DPU",
            "eventData": {
                "merchantId": context["merchant_id"],
                "merchantAccountId": context["merchant_account_id"],
                "limitApplicationUniqueId": context["limit_application_unique_id"],
                "pspName": "Payoneer",
                "pspId": "PSP_12345",
                "result": result,
                "failureReason": failure_reason,
                "lastUpdatedOn": get_current_time("%Y-%m-%dT%H:%M:%S"),
                "lastUpdatedBy": "HSBC_SYSTEM"
            }
        }

        host_header = self.api_config.base_url.replace("https://", "").replace("http://", "")
        headers = {
            "X-Internal-Request": "true",
            "Authorization": "Bearer",
            "Content-Type": "application/json",
            "Host": host_header,
        }
        url = f"{self.api_config.base_url}/dpu-openapi/notification/system-events"

        api_result = self._do_post_custom(url, title, json_data=payload, headers=headers)

        if api_result.get("success"):
            if for_completed:
                self.hsbc_psp_completed_account_ids_in_session.add(context["merchant_account_id"])
                self.hsbc_psp_pending_account_id_by_merchant.pop(self.merchant_id, None)
            else:
                self.hsbc_psp_pending_account_id_by_merchant[self.merchant_id] = context["merchant_account_id"]

        api_result.update({
            "result": result,
            "merchant_account_id": context["merchant_account_id"],
            "selected_merchant_account_id": str(merchant_account_id or "").strip() or None,
        })
        return api_result

    # ======================== 注册：场景树拆分版（无状态，逐步调用） ========================
    # 与 register_new_account_web / register_and_run_multishop_flow_web 并存。
    # 这里的方法**不依赖 session**，每一步只接受上一步返回的字段作为入参，
    # 返回结构化结果，方便场景树按步执行并把响应分别展示。

    _JOURNEY_YEARLY_REPAYMENT = {"200K": 15000, "500K": 1666666, "2000K": 16666667}

    @staticmethod
    def step_create_offer_web(
        env: str,
        journey: str = "500K",
        currency: str = "USD",
        yearly_repayment_amount: Optional[int] = None,
    ) -> dict:
        """线上注册流程第 1 步：调用 generate-shop-performance 生成 mock offer_id。

        单独暴露成一步，方便前端在 UI 上看到真正打给上游的 POST body + response。

        - 传入 yearly_repayment_amount 时直接用该金额（DS-CNY 场景固定 950000），
          忽略 journey 档位映射。
        - 不传时按 journey 档位映射到年还款额，保持 FP 线上场景原行为。
        """
        api_config = WebDPUMockService._build_api_config(env)
        if yearly_repayment_amount is not None:
            yearly_amount = yearly_repayment_amount
        else:
            yearly_amount = WebDPUMockService._JOURNEY_YEARLY_REPAYMENT.get((journey or "").upper())
        if not yearly_amount:
            return {"success": False, "error": f"不支持的 journey: {journey}"}
        payload = {"yearlyRepaymentAmount": yearly_amount, "currency": currency}
        headers = {"content-type": "application/json"}
        request_info = {
            "method": "POST",
            "url": api_config.create_offerid_url,
            "headers": headers,
            "body": payload,
        }
        try:
            resp = http_requests.post(
                api_config.create_offerid_url,
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"创建 offer_id 失败: {exc}",
                "journey": journey,
                "currency": currency,
                "request_info": request_info,
            }
        try:
            offer_id = (resp.json() or {}).get("data", {}).get("amazon3plOfferId", "") or ""
        except Exception:
            offer_id = ""
        if not offer_id:
            return {
                "success": False,
                "error": "generate-shop-performance 未返回 amazon3plOfferId",
                "journey": journey,
                "currency": currency,
                "status_code": resp.status_code,
                "response_body": (resp.text or "")[:500],
                "request_info": request_info,
            }
        return {
            "success": True,
            "stage": "offer_created",
            "journey": journey,
            "currency": currency,
            "offer_id": offer_id,
            "endpoint": api_config.create_offerid_url,
            "status_code": resp.status_code,
            "response_body": (resp.text or "")[:500],
            "request_info": request_info,
        }

    @staticmethod
    def step_amazon_redirect_web(
        env: str,
        offer_id: str,
        phone_number: str,
        currency: str = "USD",
        funder_resource: str = "FUNDPARK",
        token: Optional[str] = None,
    ) -> dict:
        """线上注册流程第 2 步：GET redirect 让 offer 生效 + POST redirect 二次确认。

        传入 token 时，GET/POST 都会带上 Authorization: Bearer <token>（DS-CNY 场景在
        signup 后透传 ${token}）；token 为空则不加该头，保持原行为。
        """
        if not offer_id:
            return {"success": False, "error": "offer_id 不能为空"}
        api_config = WebDPUMockService._build_api_config(env)
        redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource,
        }
        auth_token = str(token or "").strip()
        if auth_token:
            common_headers["Authorization"] = f"Bearer {auth_token}"
        get_request_info = {
            "method": "GET",
            "url": redirect_url,
            "headers": common_headers,
            "body": None,
        }
        try:
            get_resp = http_requests.get(redirect_url, headers=common_headers, timeout=30)
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"GET amazon/redirect 失败: {exc}",
                "offer_id": offer_id,
                "request_info": get_request_info,
            }

        post_body = {"offerId": offer_id, "relayPage": 1}
        post_request_info = {
            "method": "POST",
            "url": redirect_url,
            "headers": common_headers,
            "body": post_body,
        }
        try:
            post_resp = http_requests.post(
                redirect_url, json=post_body, headers=common_headers, timeout=30,
            )
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"POST amazon/redirect 失败: {exc}",
                "offer_id": offer_id,
                "steps": [
                    {"step": "GET amazon/redirect", "request_info": get_request_info,
                     "result": {"status_code": get_resp.status_code, "response_body": (get_resp.text or "")[:500]}},
                ],
                "request_info": post_request_info,
            }
        return {
            "success": True,
            "stage": "amazon_redirect_activated",
            "offer_id": offer_id,
            "steps": [
                {"step": "GET amazon/redirect", "request_info": get_request_info,
                 "result": {"status_code": get_resp.status_code, "response_body": (get_resp.text or "")[:500]}},
                {"step": "POST amazon/redirect", "request_info": post_request_info,
                 "result": {"status_code": post_resp.status_code, "response_body": (post_resp.text or "")[:500]}},
            ],
        }

    @staticmethod
    def step_send_register_sms_web(
        env: str,
        journey: str = "500K",
        currency: str = "USD",
        offline: bool = False,
        funder_resource: str = "FUNDPARK",
        offer_id: str = "",
    ) -> dict:
        """注册流程发短信步骤。

        - 线下模式：不使用 offer_id。
        - 线上模式：调用方（新版拆分场景）会先调 /register/create-offer 拿到 offer_id
          再传进来。为了兼容早期 DMF 场景 / 老一体化 flow，这里若 online 且未传
          offer_id 就仍然内部调 _create_offer_id 兜底。
        """
        if offline:
            journey = "500K"
        api_config = WebDPUMockService._build_api_config(env)
        phone_number = "".join(filter(str.isdigit, faker.phone_number()))
        email = f"{phone_number}y@163doushabao.com"
        effective_offer_id = (offer_id or "").strip()
        if not offline and not effective_offer_id:
            effective_offer_id = DPUMockService._create_offer_id(journey, currency, api_config) or ""
            if not effective_offer_id:
                return {
                    "success": False,
                    "error": "创建 offer_id 失败",
                    "phone_number": phone_number,
                    "email": email,
                    "journey": journey,
                    "currency": currency,
                    "funder_resource": funder_resource,
                    "offline": offline,
                }
        offer_id = effective_offer_id

        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36",
        }
        verification_url = f"{api_config.base_url}/dpu-user/auth/verification-codes"
        verification_payload = {"areaCode": "+86", "code": "SIGNUP_VERIFICATION", "phone": phone_number}
        request_info = {
            "method": "POST",
            "url": verification_url,
            "headers": common_headers,
            "body": verification_payload,
        }
        try:
            verify_resp = http_requests.post(
                verification_url,
                json=verification_payload,
                headers=common_headers,
                timeout=30,
            )
            verify_resp.raise_for_status()
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"验证码触发失败: {exc}",
                "phone_number": phone_number,
                "email": email,
                "offer_id": offer_id,
                "journey": journey,
                "currency": currency,
                "funder_resource": funder_resource,
                "offline": offline,
                "request_info": request_info,
            }
        return {
            "success": True,
            "stage": "sms_sent",
            "phone_number": phone_number,
            "email": email,
            "offer_id": offer_id,
            "journey": journey,
            "currency": currency,
            "funder_resource": funder_resource,
            "offline": offline,
            "verification_endpoint": verification_url,
            "status_code": verify_resp.status_code,
            "response_body": (verify_resp.text or "")[:500],
            "request_info": request_info,
        }

    @staticmethod
    def step_validate_register_sms_web(
        env: str,
        phone_number: str,
        currency: str = "USD",
        funder_resource: str = "FUNDPARK",
        offer_id: str = "",
    ) -> dict:
        """注册流程第 2 步：读取真实验证码并调用 validateSmsCode-sign。"""
        api_config = WebDPUMockService._build_api_config(env)
        try:
            with DatabaseExecutor(env=env) as sms_db_executor:
                verification_code = fetch_sms_verification_code(sms_db_executor, phone_number)
        except Exception as exc:
            return {
                "success": False,
                "error": f"从 dpu_sms_record 获取验证码失败: {exc}",
                "phone_number": phone_number,
            }
        if not verification_code:
            return {
                "success": False,
                "error": "未读取到验证码，可能短信下发未落库",
                "phone_number": phone_number,
            }
        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36",
        }
        validate_url = f"{api_config.base_url}/dpu-user/auth/validateSmsCode-sign"
        validate_payload = {
            "phoneNumber": phone_number,
            "phone": phone_number,
            "areaCode": "+86",
            "code": verification_code,
            "verificationCode": verification_code,
            "smsCode": verification_code,
            "offerId": offer_id or "",
        }
        request_info = {
            "method": "POST",
            "url": validate_url,
            "headers": common_headers,
            "body": validate_payload,
        }
        try:
            resp = http_requests.post(
                validate_url,
                json=validate_payload,
                headers=common_headers,
                timeout=30,
            )
            resp.raise_for_status()
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"验证码校验失败: {exc}",
                "phone_number": phone_number,
                "verification_code": verification_code,
                "request_info": request_info,
            }
        return {
            "success": True,
            "stage": "sms_validated",
            "phone_number": phone_number,
            "verification_code": verification_code,
            "offer_id": offer_id or "",
            "endpoint": validate_url,
            "status_code": resp.status_code,
            "response_body": (resp.text or "")[:500],
            "request_info": request_info,
        }

    @staticmethod
    def step_signup_register_web(
        env: str,
        phone_number: str,
        email: str,
        verification_code: str,
        currency: str = "USD",
        funder_resource: str = "FUNDPARK",
        journey: str = "500K",
        offline: bool = False,
        offer_id: str = "",
    ) -> dict:
        """注册流程第 3 步：调 /auth/signup，落地 token + 写入 register_<env>.txt。"""
        api_config = WebDPUMockService._build_api_config(env)
        redirect_url = (
            api_config.redirect_url
            if offline
            else f"{api_config.redirect_url}?offerId={offer_id}"
        )
        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36",
        }
        register_payload = {
            "phoneNumber": phone_number,
            "phone": phone_number,
            "areaCode": "+86",
            "code": verification_code,
            "verificationCode": verification_code,
            "smsCode": verification_code,
            "email": email,
            "offerId": offer_id or "",
            "password": "Aa11111111..",
            "confirmPassword": "Aa11111111..",
            "isAcceptMarketing": True,
            "securityQuestionCode": "SEC_Q_004",
            "securityAnswer": "test",
            "preferFinanceProductCurrency": currency,
        }
        request_info = {
            "method": "POST",
            "url": api_config.register_url,
            "headers": common_headers,
            "body": register_payload,
        }
        try:
            if not offline:
                try:
                    http_requests.get(redirect_url, timeout=30)
                except Exception:
                    pass  # redirect failure is non-fatal for signup
            resp = http_requests.post(
                api_config.register_url,
                json=register_payload,
                headers=common_headers,
                timeout=30,
            )
            resp.raise_for_status()
        except http_requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"用户注册失败: {exc}",
                "phone_number": phone_number,
                "email": email,
                "request_info": request_info,
            }
        try:
            token = (resp.json() or {}).get("data", {}).get("token", "") or ""
        except Exception:
            token = ""
        try:
            with open(api_config.txt_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n{journey}\n{phone_number}\n{'线下' if offline else redirect_url}\n")
        except Exception as exc:
            log.warning(f"写入 register_{env}.txt 失败: {exc}")
        return {
            "success": True,
            "stage": "signup_done",
            "phone_number": phone_number,
            "email": email,
            "journey": journey,
            "currency": currency,
            "funder_resource": funder_resource,
            "offline": offline,
            "offer_id": offer_id or "",
            "token": token,
            "redirect_url": redirect_url if not offline else None,
            "endpoint": api_config.register_url,
            "status_code": resp.status_code,
            "response_body": (resp.text or "")[:500],
            "request_info": request_info,
        }

    @staticmethod
    def step_sp_auth_url_web(
        env: str,
        phone_number: str,
        token: str,
        currency: str = "USD",
        funder_resource: str = "FUNDPARK",
        offline: bool = False,
    ) -> dict:
        """注册流程第 4 步：生成 state + 调 sp-auth-url，返回 state / selling_partner_id。"""
        if not token:
            return {"success": False, "error": "缺少 token，无法发起 SP 授权"}
        api_config = WebDPUMockService._build_api_config(env)
        with DatabaseExecutor(env=env) as db:
            state = db.execute_sql("SELECT UUID() AS state") or str(uuid.uuid4())
            selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"
            sp_auth_url = f"{api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-auth-url"
            sp_auth_payload = {
                "state": state,
                "sceneCode": "SHOP_BIND" if offline else "SHOP_BIND_NO_OFFER",
                "sourceCode": funder_resource,
                "redirectUrl": f"{WebDPUMockService._build_portal_base_url(env)}/redirect-loading?state={state}",
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "content-type": "application/json",
                "finance-product": "LINE_OF_CREDIT",
                "funder-resource": funder_resource,
                "product-currency": currency,
                "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            }
            request_info = {
                "method": "POST",
                "url": sp_auth_url,
                "headers": headers,
                "body": sp_auth_payload,
            }
            try:
                resp = http_requests.post(sp_auth_url, json=sp_auth_payload, headers=headers, timeout=30)
                resp.raise_for_status()
            except http_requests.exceptions.RequestException as exc:
                return {
                    "success": False,
                    "error": f"sp-auth-url 请求失败: {exc}",
                    "endpoint": sp_auth_url,
                    "payload": sp_auth_payload,
                    "request_info": request_info,
                }
        return {
            "success": True,
            "stage": "sp_auth_url",
            "endpoint": sp_auth_url,
            "payload": sp_auth_payload,
            "status_code": resp.status_code,
            "response_body": (resp.text or "")[:500],
            "state": state,
            "selling_partner_id": selling_partner_id,
            "request_info": request_info,
        }

    @staticmethod
    def step_sp_auth_callback_web(
        env: str,
        phone_number: str,
        token: str,
        state: str,
        selling_partner_id: str,
        currency: str = "USD",
        funder_resource: str = "FUNDPARK",
    ) -> dict:
        """注册流程第 5 步：GET sp-shop-auth-result + 等 dpu_auth_token.state + GET amazon-sp/auth 回调。"""
        if not (token and state and selling_partner_id):
            return {"success": False, "error": "token / state / selling_partner_id 不能为空"}
        api_config = WebDPUMockService._build_api_config(env)
        steps_out: list = []
        with DatabaseExecutor(env=env) as db:
            service = WebDPUMockService(phone_number, db)
            service.session_user_token = token
            service.generated_selling_partner_id = selling_partner_id

            # 1) GET sp-shop-auth-result
            sp_auth_result_url = (
                f"{api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-shop-auth-result?state={state}"
            )
            sp_auth_result_headers = {
                "Authorization": f"Bearer {token}",
                "finance-product": "LINE_OF_CREDIT",
                "product-currency": currency,
                "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            }
            sp_auth_result = service._do_get_custom_with_retry(
                sp_auth_result_url,
                "SP auth-result",
                headers=sp_auth_result_headers,
                attempts=2,
            )
            sp_auth_result_request_info = {
                "method": "GET",
                "url": sp_auth_result_url,
                "headers": sp_auth_result_headers,
                "body": None,
            }
            steps_out.append({
                "step": "SP auth-result",
                "endpoint": sp_auth_result_url,
                "request_info": sp_auth_result_request_info,
                "result": {
                    "success": sp_auth_result.get("success"),
                    "status_code": sp_auth_result.get("status_code"),
                    "response_body": (sp_auth_result.get("response_body") or "")[:500],
                    "request_info": sp_auth_result_request_info,
                },
            })
            merchant_id = service.merchant_id
            if not merchant_id:
                return {
                    "success": False,
                    "error": "未能根据 phone 反查到 merchant_id（注册可能未完成）",
                    "steps": steps_out,
                }
            db_state_sql = (
                "SELECT state FROM dpu_auth_token "
                f"WHERE merchant_id = '{merchant_id}' "
                "AND authorization_party = 'SP' "
                f"AND state = '{state}' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            db_state = None
            for _ in range(15):
                db_state = db.execute_sql(db_state_sql)
                if db_state:
                    break
                time.sleep(1)
            if not db_state:
                return {
                    "success": False,
                    "error": "等待 dpu_auth_token.state 超时，SP 授权未落库",
                    "merchant_id": merchant_id,
                    "state": state,
                    "steps": steps_out,
                }

            # 2) GET amazon-sp/auth 回调
            auth_params = {
                "mws_auth_token": "1235",
                "selling_partner_id": selling_partner_id,
                "spapi_oauth_code": "123123",
                "state": db_state,
            }
            auth_get_url = f"{api_config.multi_shop_sp_auth_url}?{urlencode(auth_params)}"
            auth_headers = {
                "Authorization": f"Bearer {token}",
                "content-type": "application/json",
                "finance-product": "LINE_OF_CREDIT",
                "funder-resource": funder_resource,
                "product-currency": currency,
            }
            auth_request_info = {
                "method": "GET",
                "url": auth_get_url,
                "headers": auth_headers,
                "body": None,
                "params": auth_params,
            }
            try:
                auth_resp = http_requests.get(
                    api_config.multi_shop_sp_auth_url,
                    params=auth_params,
                    headers=auth_headers,
                    timeout=30,
                )
                auth_resp.raise_for_status()
            except http_requests.exceptions.RequestException as exc:
                return {
                    "success": False,
                    "error": f"amazon-sp/auth 回调失败: {exc}",
                    "auth_url": auth_get_url,
                    "steps": steps_out,
                    "request_info": auth_request_info,
                }
            steps_out.append({
                "step": "SP auth",
                "endpoint": api_config.multi_shop_sp_auth_url,
                "payload": auth_params,
                "request_info": auth_request_info,
                "result": {
                    "success": True,
                    "status_code": auth_resp.status_code,
                    "response_body": service._format_redirect_body_for_log(auth_resp.text),
                    "selling_partner_id": selling_partner_id,
                    "request_info": auth_request_info,
                },
            })
        return {
            "success": True,
            "stage": "sp_authorized",
            "state": db_state,
            "selling_partner_id": selling_partner_id,
            "merchant_id": merchant_id,
            "steps": steps_out,
        }

    @staticmethod
    def step_sp_update_offer_web(
        env: str,
        phone_number: str,
        selling_partner_id: str,
        sp_status: str = "SUCCESS",
        failure_reason_index: Optional[int] = None,
    ) -> dict:
        """注册流程第 6 步：调 mock_sp_status_update（其本质就是 POST /amazon-sp/updateOffer）。

        failure_reason_index 仅在 sp_status=FAIL 时生效；缺省时按历史行为给 4 (others)。
        """
        if not selling_partner_id:
            return {"success": False, "error": "selling_partner_id 不能为空"}
        with DatabaseExecutor(env=env) as db:
            service = WebDPUMockService(phone_number, db)
            service.generated_selling_partner_id = selling_partner_id
            if sp_status == "FAIL":
                effective_failure_reason_index = (
                    failure_reason_index if failure_reason_index in (1, 2, 3, 4) else 4
                )
            else:
                effective_failure_reason_index = None
            result = service.mock_sp_status_update(
                platform_seller_id=selling_partner_id,
                status=sp_status,
                failure_reason_index=effective_failure_reason_index,
            )
        return {
            "success": bool(result.get("success")),
            "stage": "sp_update_offer",
            "selling_partner_id": result.get("platform_seller_id") or selling_partner_id,
            "status": result.get("status") or sp_status,
            "failure_reason_index": effective_failure_reason_index,
            "result": result,
        }

    @staticmethod
    def step_3pl_link_wait_web(
        env: str,
        phone_number: str,
        selling_partner_id: str,
        offline: bool = True,
    ) -> dict:
        """注册流程第 7 步：等 dpu_manual_offer 落地（platform_offer_id 出现）。线上场景会调 link-sp-3pl-shops 兜底。"""
        if not selling_partner_id:
            return {"success": False, "error": "selling_partner_id 不能为空"}
        with DatabaseExecutor(env=env) as db:
            service = WebDPUMockService(phone_number, db)
            service.generated_selling_partner_id = selling_partner_id
            merchant_id = service.merchant_id
            if not merchant_id:
                return {"success": False, "error": "未能根据 phone 反查到 merchant_id"}
            manual_offer_row = service._wait_for_manual_offer(
                selling_partner_id=selling_partner_id,
                merchant_id=merchant_id,
                timeout_seconds=120 if offline else 30,
            )
            fallback_link = None
            if not manual_offer_row and not offline:
                fallback_link = service._do_post_custom(
                    service.api_config.link_sap_3pl_url,
                    "SP-3PL关联补偿",
                    params={"phone": phone_number},
                )
                manual_offer_row = service._wait_for_manual_offer(
                    selling_partner_id=selling_partner_id,
                    merchant_id=merchant_id,
                    timeout_seconds=20,
                )
            if not manual_offer_row:
                debug_rows = service._get_manual_offer_debug_rows(
                    selling_partner_id=selling_partner_id,
                    merchant_id=merchant_id,
                )
                return {
                    "success": False,
                    "error": "等待 dpu_manual_offer 落地超时",
                    "selling_partner_id": selling_partner_id,
                    "merchant_id": merchant_id,
                    "fallback_link_result": fallback_link,
                    "manual_offer_debug_rows": debug_rows,
                }
            ready_seller_id = manual_offer_row.get("platform_seller_id") or selling_partner_id
        return {
            "success": True,
            "stage": "manual_offer_ready",
            "selling_partner_id": ready_seller_id,
            "merchant_id": manual_offer_row.get("merchant_id"),
            "platform_offer_id": manual_offer_row.get("platform_offer_id"),
            "idempotency_key": manual_offer_row.get("idempotency_key"),
            "fallback_link_result": fallback_link,
        }

    @staticmethod
    def step_3pl_redirect_web(
        env: str,
        phone_number: str,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        """注册流程第 8 步：3PL 重定向回调 POST。

        注意：DS-CNY 场景已在前端拆分为独立的「生成 offerId」(/register/create-offer)
        + 「GET redirect + POST redirect」(/register/amazon-redirect) 两步，不再走下面的
        CNY+DOWSURE 合并分支。该分支保留仅为兼容其它可能的调用方。
        """
        with DatabaseExecutor(env=env) as db:
            service = WebDPUMockService(phone_number, db)
            if (currency or "").upper() == "CNY" and (funder_resource or "").upper() == "DOWSURE":
                offer_payload = {"yearlyRepaymentAmount": 950000, "currency": "CNY"}
                offer_headers = {"Content-Type": "application/json"}
                offer_request_info = {
                    "method": "POST",
                    "url": service.api_config.create_offerid_url,
                    "headers": offer_headers,
                    "body": offer_payload,
                }
                try:
                    offer_response = http_requests.post(
                        service.api_config.create_offerid_url,
                        json=offer_payload,
                        headers=offer_headers,
                        timeout=30,
                    )
                    offer_response.raise_for_status()
                except http_requests.exceptions.RequestException as exc:
                    return {
                        "success": False,
                        "stage": "generate_cny_offer",
                        "error": f"generate-shop-performance 失败: {exc}",
                        "offer_generation": {
                            "request_info": offer_request_info,
                            "status_code": exc.response.status_code if getattr(exc, "response", None) is not None else None,
                            "response_body": (
                                service._format_redirect_body_for_log(exc.response.text)
                                if getattr(exc, "response", None) is not None
                                else None
                            ),
                        },
                    }
                try:
                    platform_offer_id = (offer_response.json() or {}).get("data", {}).get("amazon3plOfferId", "")
                except Exception:
                    platform_offer_id = ""
                if not platform_offer_id:
                    return {
                        "success": False,
                        "stage": "generate_cny_offer",
                        "error": "generate-shop-performance 未返回 amazon3plOfferId",
                        "offer_generation": {
                            "request_info": offer_request_info,
                            "status_code": offer_response.status_code,
                            "response_body": service._format_redirect_body_for_log(offer_response.text),
                        },
                    }
                redirect_result = service._run_multishop_3pl_redirect_with_post(
                    platform_offer_id=platform_offer_id,
                )
                redirect_result["offer_generation"] = {
                    "request_info": offer_request_info,
                    "status_code": offer_response.status_code,
                    "response_body": service._format_redirect_body_for_log(offer_response.text),
                    "platform_offer_id": platform_offer_id,
                }
            else:
                redirect_result = service._run_multishop_3pl_redirect_with_post()
        return {
            "success": bool(redirect_result.get("success")),
            "stage": "3pl_redirect",
            "result": redirect_result,
        }

    @staticmethod
    def remove_test_offer_suffix_web(env: str, phone_number: str) -> dict:
        """Run the standalone post-redirect TESTOFFER cleanup step."""
        try:
            with DatabaseExecutor(env=env) as db:
                result = WebDPUMockService._remove_test_offer_suffix(db, phone_number)
            return {"success": True, **result}
        except Exception as exc:
            return {"success": False, "error": f"移除 TESTOFFER 后缀失败: {exc}"}

    # ======================== 注册（静态方法改为实例无关的独立函数） ========================

    @staticmethod
    def register_new_account_web(env: str, journey: str = "500K",
                                  currency: str = "USD", offline: bool = False,
                                  funder_resource: str = "FUNDPARK") -> dict:
        """注册新账号（Web 版，接受参数而非 input）"""
        if offline:
            journey = "500K"
            log.info(f"[线下模式] 开始注册新账号，流程: {journey}")
        else:
            log.info(f"开始注册新账号，流程: {journey}")

        log.info(f"融资产品货币: {currency}")

        # 生成账号信息
        phone_number = ''.join(filter(str.isdigit, faker.phone_number()))
        email = f"{phone_number}y@163doushabao.com"
        log.info(f"生成账号信息 | 手机号：{phone_number} | 邮箱：{email}")

        # 初始化 API 配置
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "reg": "https://dpu-gateway-reg.dowsure.com",
            "local": "http://192.168.11.3:8080"
        }
        base_url = base_url_dict[env]
        redirect_url_base = (
            f"{base_url}/dpu-merchant/amazon/redirect"
            if env in ("uat", "preprod")
            else f"https://dpu-gateway-{env}.dowsure.com/dpu-merchant/amazon/redirect"
        )
        api_config = ApiConfig(
            base_url=base_url,
            create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            redirect_url=redirect_url_base,
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=f"{base_url}/dpu-merchant/amz/sp/shop/auth",
            multi_shop_sp_auth_url=f"{base_url}/dpu-auth/amazon-sp/auth",
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            update_offer_url=f"{base_url}/dpu-auth/amazon-sp/updateOffer",
            txt_path=str(SCRIPT_DIR / f"register_{env}.txt")
        )

        # 创建 offer_id
        offer_id = ""
        redirect_url = redirect_url_base
        if not offline:
            offer_id = DPUMockService._create_offer_id(journey, currency, api_config)
            if not offer_id:
                return {"success": False, "error": "创建 offer_id 失败"}
            redirect_url = f"{redirect_url_base}?offerId={offer_id}"

        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36",
        }

        # 先触发短信验证码落库，再从 dpu_sms_record 读取真实验证码。
        verification_url = f"{base_url}/dpu-user/auth/verification-codes"
        verification_payload = {"areaCode": "+86", "code": "SIGNUP_VERIFICATION", "phone": phone_number}
        try:
            verify_resp = http_requests.post(
                verification_url,
                json=verification_payload,
                headers=common_headers,
                timeout=30,
            )
            log.info(
                f"验证码触发请求完成 | status={verify_resp.status_code} | phone={phone_number} | body={verify_resp.text}"
            )
            verify_resp.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            log.error(f"验证码触发失败: {e}")
            return {"success": False, "error": f"验证码触发失败: {e}"}

        try:
            with DatabaseExecutor(env=env) as sms_db_executor:
                verification_code = fetch_sms_verification_code(sms_db_executor, phone_number)
        except Exception as e:
            log.error(f"从 dpu_sms_record 获取验证码失败: {e}")
            return {"success": False, "error": f"从 dpu_sms_record 获取验证码失败: {e}"}

        validate_url = f"{base_url}/dpu-user/auth/validateSmsCode-sign"
        validate_payload = {
            "phoneNumber": phone_number,
            "phone": phone_number,
            "areaCode": "+86",
            "code": verification_code,
            "verificationCode": verification_code,
            "smsCode": verification_code,
            "offerId": offer_id,
        }
        try:
            validate_resp = http_requests.post(
                validate_url,
                json=validate_payload,
                headers=common_headers,
                timeout=30,
            )
            log.info(
                f"验证码校验请求完成 | status={validate_resp.status_code} | phone={phone_number} | body={validate_resp.text}"
            )
            validate_resp.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            log.error(f"验证码校验失败: {e}")
            return {"success": False, "error": f"验证码校验失败: {e}"}

        # 注册
        register_payload = {
            "phoneNumber": phone_number,
            "phone": phone_number,
            "areaCode": "+86",
            "code": verification_code,
            "verificationCode": verification_code,
            "smsCode": verification_code,
            "email": email, "offerId": offer_id,
            "password": "Aa11111111..", "confirmPassword": "Aa11111111..",
            "isAcceptMarketing": True,
            "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test",
            "preferFinanceProductCurrency": currency
        }

        try:
            if not offline:
                http_requests.get(redirect_url, timeout=30)

            resp = http_requests.post(api_config.register_url, json=register_payload,
                                      headers=common_headers, timeout=30)
            resp.raise_for_status()
            token = resp.json().get("data", {}).get("token", "")
            log.info(f"注册成功！手机号: {phone_number} | Token: {token}")

            with open(api_config.txt_path, 'a', encoding='utf-8') as f:
                line = f"\n{journey}\n{phone_number}\n{'线下' if offline else redirect_url}\n"
                f.write(line)

            return {
                "success": True,
                "phone_number": phone_number,
                "email": email,
                "journey": journey,
                "currency": currency,
                "funder_resource": funder_resource,
                "token": token,
                "verification_code": verification_code,
                "offer_id": offer_id,
                "redirect_url": redirect_url if not offline else None,
            }
        except http_requests.exceptions.RequestException as e:
            log.error(f"注册失败: {e}")
            return {"success": False, "error": str(e), "phone_number": phone_number}
