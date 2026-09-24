# -*- coding: utf-8 -*-
"""Prompt template management + AI-driven execution."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import traceback
from contextlib import redirect_stdout
from typing import Any, Optional

import requests
from fastapi import APIRouter, HTTPException

from mock_sit import DatabaseExecutor
from web.models.responses import ApiResponse
from web.models.requests import (
    PromptTemplateCreateRequest,
    PromptTemplateDeleteRequest,
    PromptTemplateExecuteRequest,
    PromptTemplateToggleRequest,
    PromptTemplateUpdateRequest,
)
from web.routes.auth_guard import require_admin, require_valid_username
from web.services.audit_store import audit_store
from web.services.ai_service import DPUAIService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompt-templates", tags=["提示词模板"])

ai_service = DPUAIService()


def _call_ai_raw(
    message: str,
    model: Optional[str],
    system_prompt: Optional[str] = None,
) -> str:
    """Bypass ai_service.chat() shortcuts and hit the underlying model directly."""
    options = {"model": (model or "").strip() or None, "reasoning_effort": None}
    ai_service._call_options = options  # noqa: SLF001 - reuse private hook
    messages = [
        {"role": "system", "content": system_prompt or _AI_SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    return ai_service._call_model(messages, temperature=0.0)  # noqa: SLF001

SUPPORTED_ENVS = ("sit", "uat", "dev", "preprod", "reg", "local")
SQL_EXECUTION_TIMEOUT = 30
HTTP_EXECUTION_TIMEOUT = 30
PYTHON_EXECUTION_TIMEOUT = 30


def _all_supported_envs() -> tuple[str, ...]:
    """Built-in envs plus dynamically configured external SQL sources (douke, dowsure, ...)."""
    from web.services.ai_service import load_external_sql_data_sources  # local import to avoid cycles
    return (*SUPPORTED_ENVS, *sorted(load_external_sql_data_sources()))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=ApiResponse)
async def list_prompt_templates(username: Optional[str] = None):
    """Visible to every authenticated user."""
    require_valid_username(username)
    rows = await asyncio.to_thread(audit_store.list_prompt_templates)
    return ApiResponse(success=True, message=f"{len(rows)} templates", data=rows)


@router.post("", response_model=ApiResponse)
async def create_prompt_template(req: PromptTemplateCreateRequest):
    caller = require_admin(req.username)
    try:
        row = await asyncio.to_thread(
            audit_store.create_prompt_template,
            req.model_dump(exclude={"username"}),
            caller,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="模板已创建", data=row)


@router.put("/{template_id}", response_model=ApiResponse)
async def update_prompt_template(template_id: int, req: PromptTemplateUpdateRequest):
    caller = require_admin(req.username)
    # `locked_env: null` is the only way the UI can clear a pinned env, so it has
    # to survive the None filter that keeps omitted fields from being overwritten.
    sent = req.model_dump(exclude={"username"}, exclude_unset=True)
    payload = {k: v for k, v in sent.items() if v is not None or k == "locked_env"}
    try:
        row = await asyncio.to_thread(
            audit_store.update_prompt_template,
            template_id,
            payload,
            caller,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在或已删除")
    return ApiResponse(success=True, message="模板已更新", data=row)


@router.delete("/{template_id}", response_model=ApiResponse)
async def delete_prompt_template(template_id: int, req: PromptTemplateDeleteRequest):
    require_admin(req.username)
    ok = await asyncio.to_thread(audit_store.delete_prompt_template, template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在或已删除")
    return ApiResponse(success=True, message="模板已删除", data={"id": template_id})


@router.post("/{template_id}/toggle", response_model=ApiResponse)
async def toggle_prompt_template(template_id: int, req: PromptTemplateToggleRequest):
    """Admin-only: enable or disable a template.

    Disabled templates are still visible (so users see why something is greyed
    out) but the execute endpoint and the AI shortcut both refuse to run them.
    """
    caller = require_admin(req.username)
    try:
        row = await asyncio.to_thread(
            audit_store.update_prompt_template,
            template_id,
            {"is_disabled": bool(req.is_disabled)},
            caller,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在或已删除")
    return ApiResponse(
        success=True,
        message="模板已禁用" if req.is_disabled else "模板已启用",
        data=row,
    )


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

@router.post("/{template_id}/execute", response_model=ApiResponse)
async def execute_prompt_template(template_id: int, req: PromptTemplateExecuteRequest):
    caller = require_valid_username(req.username)
    template = await asyncio.to_thread(audit_store.get_prompt_template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在或已删除")
    if template.get("is_disabled"):
        raise HTTPException(status_code=403, detail="模板已被管理员禁用，暂不可使用")

    env = (req.env or "").strip().lower()

    # A template can pin itself to a specific environment (e.g. "douke" approval
    # flow). When that's set, it always wins — the UI greys the picker, but the
    # backend must enforce it too in case anyone calls /execute directly.
    locked_env = (template.get("locked_env") or "").strip().lower()
    if locked_env:
        env = locked_env

    allowed_envs = _all_supported_envs()
    if env and env not in allowed_envs:
        raise HTTPException(status_code=400, detail=f"不支持的环境: {env}")

    # Step 1: resolve concrete parameters into the template logic.
    # When the caller passes structured `params` (front-end split inputs), do a
    # deterministic mechanical `${key}` substitution and skip the AI entirely —
    # this is safe for very long scripts (stored procedures) where an AI round
    # trip risks truncation or accidental rewrites. Otherwise fall back to the
    # AI materialise pipeline that infers params from free-text user_input.
    if req.params:
        try:
            rendered, missing = _apply_params(template["logic"], req.params)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"参数替换失败: {exc}") from exc
        if missing:
            hints = "、".join(missing)
            return ApiResponse(
                success=False,
                message=f"缺少参数：{hints}",
                data={
                    "template": template,
                    "user_input": req.user_input,
                    "env": env or "",
                    "rendered": template["logic"],
                    "params": dict(req.params),
                    "placeholders": _extract_placeholders(template["logic"]),
                    "ai_error": f"缺少参数：{hints}",
                },
            )
        params = dict(req.params)
        notes = "参数由前端分列输入，机械替换（未经过 AI）。"
    else:
        try:
            materialised = await asyncio.to_thread(
                _ai_materialise,
                template,
                req.user_input,
                env,
                req.model,
            )
        except Exception as exc:  # pragma: no cover - AI failures bubble up
            log.exception("AI materialise failed")
            raise HTTPException(status_code=500, detail=f"AI 翻译失败: {exc}") from exc

        # If the AI flagged the request as under-specified, return a structured
        # diagnostic instead of trying to execute placeholder-laden SQL.
        if materialised.get("error"):
            return ApiResponse(
                success=False,
                message=materialised["error"],
                data={
                    "template": template,
                    "user_input": req.user_input,
                    "env": env or "",
                    "rendered": materialised.get("rendered") or template["logic"],
                    "params": materialised.get("params") or {},
                    "placeholders": materialised.get("placeholders") or [],
                    "ai_error": materialised["error"],
                    "raw_reply": materialised.get("raw_reply"),
                },
            )

        rendered = materialised.get("rendered") or template["logic"]
        params = materialised.get("params") or {}
        notes = materialised.get("notes") or ""

    # Step 2: execute the rendered logic.
    try:
        execution = await asyncio.to_thread(
            _execute_logic,
            template["logic_type"],
            rendered,
            env,
        )
    except Exception as exc:  # pragma: no cover - executor failures bubble up
        log.exception("Prompt template execute failed")
        raise HTTPException(status_code=500, detail=f"执行失败: {exc}") from exc

    # Step 3: ask the AI to interpret what actually happened (affected_rows=0,
    # 0 rows returned, etc.), and if the target looks missing, probe the other
    # envs for the same business key.
    summary: dict[str, Any] = {}
    cross_env_hits: list[dict[str, Any]] = []
    try:
        summary = await asyncio.to_thread(
            _ai_summarise_execution,
            template,
            req.user_input,
            env,
            rendered,
            params,
            execution,
            req.model,
        )
    except Exception as exc:  # noqa: BLE001 - summary failure must not break execute
        log.warning("summarise execution failed: %s", exc)

    # Guarantee the AI 解读 panel always has text to show. The summary helper
    # already falls back to a mechanical sentence on its own, but if it raised
    # we synthesise one here so every template execution surfaces a 解读.
    if not summary.get("summary"):
        summary = {
            "summary": _build_mechanical_summary(execution, env),
            "target_missing": bool(summary.get("target_missing")),
            "probe_sql": summary.get("probe_sql"),
            "probe_label": summary.get("probe_label"),
        }

    if summary.get("target_missing") and summary.get("probe_sql"):
        try:
            cross_env_hits = await asyncio.to_thread(
                _probe_other_envs,
                summary["probe_sql"],
                env,
            )
        except Exception as exc:  # noqa: BLE001 - probe is best-effort
            log.warning("cross-env probe failed: %s", exc)

    audit_payload = {
        "template_id": template["id"],
        "title": template["title"],
        "logic_type": template["logic_type"],
        "user_input": req.user_input,
        "env": env or "",
        "rendered": rendered,
        "params": params,
        "notes": notes,
    }
    try:
        await asyncio.to_thread(
            audit_store.record_operation,
            username=caller,
            session_data={"env": env or "", "phone_number": None, "merchant_id": None},
            operation_name=f"prompt_template:{template['title']}",
            request_payload=audit_payload,
            response_payload={
                "execution": execution,
                "summary": summary,
                "cross_env_hits": cross_env_hits,
            },
            success=bool(execution.get("success")),
        )
    except Exception as exc:  # noqa: BLE001 - audit failure should not block result
        log.warning("audit prompt-template execute failed: %s", exc)

    return ApiResponse(
        success=bool(execution.get("success")),
        message=execution.get("message") or "执行完成",
        data={
            "template": template,
            "user_input": req.user_input,
            "env": env or "",
            "rendered": rendered,
            "params": params,
            "notes": notes,
            "execution": execution,
            "summary": summary,
            "cross_env_hits": cross_env_hits,
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AI_SYSTEM_PROMPT = (
    "你是 DPU 提示词模板执行助手。模板可能是 SQL / HTTP / Python，由管理员预先写好。\n\n"
    "硬规则（违反任何一条都视为失败）：\n"
    "1) 字面值原样保留：模板里所有字符串、数字、日期、表名、列名、关键字一律保持原样，"
    "绝不改写、绝不翻译。例如 'US' 不能变成 '美国'，'Electronics' 不能变成 '电子产品'，"
    "'NORMAL' 不能变成 '正常'，'2026-05-18' 不能变。模板里写什么就是什么。\n"
    "2) 仅在以下两种情况修改模板内容：\n"
    "   a. 替换 ${variable} 或 :variable 形式的占位符，使用用户描述里给出的对应值；\n"
    "   b. 当用户描述里给出一个聚合参数（例如 sales_value=3505000）而模板里把该指标拆成多个细分字段时"
    "（例如 month1_sales_value..month12_sales_value、year1/2/3_sales_value），"
    "需要按合理的分布把聚合值重新分配进这些细分字段：\n"
    "      - 月度拆分默认按递减曲线分布，12 个月之和必须严格等于用户给的聚合值；\n"
    "      - 同时若模板里存在年度字段（year1_sales_value 等），把当年（year1）也同步成用户给的聚合值；\n"
    "      - 把改动写进 params，并在 notes 里说明分布方式与求和校验。\n"
    "   除上述两种情况外，模板里的任何字面值都不要碰。\n"
    "3) 输出严格 JSON：{\"rendered\": \"最终可直接执行的脚本\", \"params\": {键值对}, \"notes\": \"简要说明\"}。\n"
    "4) 如果连占位符都无法从用户描述里取到值，返回 {\"error\": \"...\"} 并明确写出缺哪个占位符；"
    "已经能拿到值的占位符不要在 error 里抱怨。\n"
    "5) 绝不输出 JSON 以外的内容（不要 Markdown 围栏、不要解释、不要前后缀文字）。"
)


def _extract_placeholders(logic: str) -> list[str]:
    """Pull `${var}` / `:var` style placeholders out of a template body.

    Used to tell the user exactly which slots a template expects when the AI
    rejects a request as under-specified.
    """
    if not logic:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for pattern in (r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"(?<![A-Za-z0-9_:]):([A-Za-z_][A-Za-z0-9_]*)\b"):
        for match in re.findall(pattern, logic):
            if match not in seen:
                seen.add(match)
                found.append(match)
    return found


def _apply_params(logic: str, params: dict[str, Any]) -> tuple[str, list[str]]:
    """Mechanically substitute `${key}` placeholders with provided values.

    Returns (rendered, missing) where `missing` lists placeholder names that the
    template requires but the caller did not supply a non-empty value for.
    Values are substituted verbatim (caller is responsible for the SQL literal
    quoting inside the template, e.g. SET @phone = '${phone}').
    """
    placeholders = _extract_placeholders(logic)
    rendered = logic
    missing: list[str] = []
    for key in placeholders:
        value = params.get(key)
        if value is None or str(value).strip() == "":
            # Blank is allowed only when the template author intends optional
            # slots; we treat empty as "missing" for required-looking keys, but
            # still substitute an empty string so optional ones (e.g. seller_id
            # auto-generate) work when explicitly left blank by the user.
            if key in params:
                rendered = rendered.replace("${" + key + "}", "")
            else:
                missing.append(key)
            continue
        rendered = rendered.replace("${" + key + "}", str(value))
    return rendered, missing


def _ai_materialise(template: dict[str, Any], user_input: str, env: str, model: Optional[str]) -> dict[str, Any]:
    """Use the AI service to plug user_input into the template logic.

    Returns a dict whose shape depends on the outcome:
    - success: {"rendered": str, "params": dict, "notes": str}
    - AI says params are missing: {"error": str, "rendered": str, "params": dict,
      "placeholders": list, "raw_reply": str}
    Callers should branch on the `error` key rather than relying on exceptions.
    """
    logic_type = template.get("logic_type", "sql")
    logic = template.get("logic", "")
    prompt_message = (
        f"模板类型: {logic_type}\n"
        f"模板标题: {template.get('title', '')}\n"
        f"模板描述: {template.get('description', '')}\n"
        f"目标执行环境: {env or '(未指定)'}\n\n"
        f"模板原始逻辑:\n```\n{logic}\n```\n\n"
        f"用户描述:\n{user_input}\n\n"
        "请输出 JSON。"
    )

    history = [{"role": "system", "content": _AI_SYSTEM_PROMPT}]
    try:
        reply = _call_ai_raw(prompt_message, model)
    except Exception as exc:
        # Last-ditch fallback to the conversational pipeline (kept for robustness)
        log.warning("raw model call failed, fallback to chat(): %s", exc)
        result = ai_service.chat(
            message=prompt_message,
            history=history,
            context={"selected_env": env or None},
            model=model,
        )
        reply = (result.get("reply") or "").strip()
    reply = (reply or "").strip()
    parsed = _try_parse_json(reply)
    if not parsed:
        # AI 没按 JSON 输出时，退回到原模板，让用户至少能看到默认脚本
        return {"rendered": logic, "params": {}, "notes": "AI 未返回结构化 JSON，已回退到模板原文。"}
    if "error" in parsed:
        return {
            "error": str(parsed.get("error") or "").strip() or "AI 拒绝渲染该模板",
            "rendered": parsed.get("rendered") or logic,
            "params": parsed.get("params") or {},
            "placeholders": _extract_placeholders(logic),
            "raw_reply": reply,
        }
    rendered = parsed.get("rendered") or logic
    return {
        "rendered": rendered,
        "params": parsed.get("params") or {},
        "notes": parsed.get("notes") or "",
    }


def _try_parse_json(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    candidates = [text]
    if "```" in text:
        for block in text.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            if block.startswith("{") and block.endswith("}"):
                candidates.append(block)
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:  # noqa: BLE001 - try the next candidate
            continue
    return None


def _normalise_error_message(message: Any) -> str:
    text = str(message or "").strip()
    # PyMySQL formats SIGNAL errors as: (1644, 'message') or (1644, "message").
    match = re.search(r"\(\s*\d+\s*,\s*['\"](.+?)['\"]\s*\)", text)
    return match.group(1) if match else text


def _known_template_error_summary(
    execution: dict[str, Any],
    env: str,
    params: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if execution.get("success"):
        return None

    message = _normalise_error_message(execution.get("message"))
    lowered = message.lower()
    phone = str(params.get("phone") or "").strip()
    offer_id = str(params.get("offer_id") or params.get("source_dpu_offer_id") or "").strip()
    prefix = f"执行失败：{message}"

    if "source offerid not found under this user" in lowered:
        detail = []
        if phone:
            detail.append(f"手机号={phone}")
        if offer_id:
            detail.append(f"source offerId={offer_id}")
        suffix = f"（{', '.join(detail)}）" if detail else ""
        return {
            "summary": (
                f"{prefix}。这个 source offerId 没有挂在当前手机号对应的豆沙用户下面{suffix}。"
                "请换成该手机号名下的 DPU_3PL offerId，或改用这个 offerId 实际所属的手机号后再执行。"
            ),
            "target_missing": True,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "SOURCE_OFFER_USER_MISMATCH",
        }
    if "source offerid must be dpu_3pl" in lowered:
        return {
            "summary": f"{prefix}。源店铺必须是 offer_source=DPU_3PL，不能用 SP/3PL 或其它类型的 offerId。",
            "target_missing": False,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "SOURCE_OFFER_NOT_DPU_3PL",
        }
    if "source dpu_3pl must have exactly one dsb_offer" in lowered:
        return {
            "summary": f"{prefix}。源 DPU_3PL 在 dsb_offer 中必须刚好有 1 条数据；当前是 0 条或多条，不能作为克隆源。",
            "target_missing": True,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "SOURCE_DSB_OFFER_INVALID",
        }
    if "source dpu_3pl missing dsb_offer_history" in lowered:
        return {
            "summary": f"{prefix}。源 DPU_3PL 缺少 dsb_offer_history 最新经营数据，不能克隆新店铺。",
            "target_missing": True,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "SOURCE_HISTORY_MISSING",
        }
    if "phone must match exactly one user" in lowered:
        return {
            "summary": f"{prefix}。手机号在豆沙 t_user 里必须且只能命中 1 个用户；当前手机号={phone or '-'} 不满足条件。",
            "target_missing": True,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "PHONE_USER_NOT_UNIQUE",
        }
    if "quota_year1_sales_value must be >= 1000" in lowered:
        return {
            "summary": f"{prefix}。ADMITTED + CUSTOM 时年销售额必须 >= 1000；如果是不准入，请选择 NOT_ADMITTED 并留空年销售额。",
            "target_missing": False,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "CUSTOM_QUOTA_TOO_SMALL",
        }
    if "transaction characteristics can't be changed while a transaction is in progress" in lowered:
        return {
            "summary": f"{prefix}。脚本里有 SET TRANSACTION/事务特性语句，但当前连接已经开启事务；需要把该语句放到 START TRANSACTION 前，或由执行器使用 autocommit 执行。",
            "target_missing": False,
            "probe_sql": None,
            "probe_label": None,
            "error_code": "TRANSACTION_CHARACTERISTICS_IN_PROGRESS",
        }
    return None


def _execute_logic(logic_type: str, rendered: str, env: str) -> dict[str, Any]:
    logic_type = (logic_type or "sql").lower()
    if logic_type == "sql":
        return _execute_sql(rendered, env)
    if logic_type == "http":
        return _execute_http(rendered)
    if logic_type == "python":
        return _execute_python(rendered, env)
    return {"success": False, "message": f"未知的 logic_type: {logic_type}"}


_MATCHED_ROWS_RE = re.compile(rb"Rows matched:\s*(\d+)")


def _matched_rows_from_conn(conn: Any) -> Optional[int]:
    """Extract "Rows matched: N" from the last write's server message.

    PyMySQL exposes the raw OK-packet info string on the connection right after
    an UPDATE. ``cursor.rowcount`` (affected_rows) only counts *changed* rows, so
    an UPDATE that sets a column to the value it already holds reports 0 even
    though the WHERE clause matched an existing row. The "Rows matched" figure
    lets us tell "no such row" (0 matched) apart from "row found, value already
    correct" (>=1 matched, 0 changed). Returns None when the info is absent.
    """
    try:
        message = getattr(getattr(conn, "_result", None), "message", None)
        if not message:
            return None
        if isinstance(message, str):
            message = message.encode("utf-8", "ignore")
        found = _MATCHED_ROWS_RE.search(message)
        return int(found.group(1)) if found else None
    except Exception:  # noqa: BLE001 - best-effort parsing, never block execution
        return None


def _split_sql_statements(sql: str) -> list[str]:
    """Split multi-statement SQL into individual statements.

    Understands the ``DELIMITER`` client directive so stored-procedure bodies
    (CREATE PROCEDURE ... BEGIN ...; ...; END$$) are kept as a single statement.
    String literals ('...', "...", `...`), line comments (-- / #) and block
    comments (/* */) are respected so their inner ``;`` never split a statement.
    Templates without DELIMITER behave exactly like the old ``split(';')``.
    """
    statements: list[str] = []
    delimiter = ";"
    buf: list[str] = []
    i = 0
    n = len(sql)
    at_stmt_start = True

    def flush() -> None:
        stmt = "".join(buf).strip()
        if stmt:
            statements.append(stmt)
        buf.clear()

    while i < n:
        if at_stmt_start:
            m = re.match(r"[ \t]*DELIMITER[ \t]+(\S+)[ \t]*(?:\r?\n|$)", sql[i:], re.IGNORECASE)
            if m:
                flush()
                delimiter = m.group(1)
                i += m.end()
                at_stmt_start = True
                continue
        ch = sql[i]
        # string literal ('...', "...", `...`)
        if ch in ("'", '"', "`"):
            buf.append(ch)
            i += 1
            while i < n:
                c = sql[i]
                buf.append(c)
                i += 1
                if c == "\\" and ch != "`":
                    if i < n:
                        buf.append(sql[i])
                        i += 1
                    continue
                if c == ch:
                    break
            at_stmt_start = False
            continue
        # line comment (-- ... or # ...)
        if sql.startswith("--", i) or ch == "#":
            while i < n and sql[i] not in "\r\n":
                buf.append(sql[i])
                i += 1
            continue
        # block comment (/* ... */)
        if sql.startswith("/*", i):
            buf.append("/*")
            i += 2
            while i < n and not sql.startswith("*/", i):
                buf.append(sql[i])
                i += 1
            if sql.startswith("*/", i):
                buf.append("*/")
                i += 2
            continue
        # statement delimiter
        if sql.startswith(delimiter, i):
            i += len(delimiter)
            flush()
            at_stmt_start = True
            continue
        buf.append(ch)
        if not ch.isspace():
            at_stmt_start = False
        i += 1
    flush()
    return statements


def _execute_sql(rendered: str, env: str) -> dict[str, Any]:
    if not env:
        return {"success": False, "message": "SQL 执行需要指定环境"}
    # External SQL sources (douke / dowsure / ...) live in ai_service and have
    # their own connection logic. Route to them transparently so prompt
    # templates can target a 3PL/外部数据源 the same way they target reg / uat.
    from web.services.ai_service import load_external_sql_data_sources  # local import
    external_sources = load_external_sql_data_sources()
    if env in external_sources:
        return _execute_sql_external(rendered, env, external_sources[env])
    if env not in SUPPORTED_ENVS:
        return {"success": False, "message": f"不支持的环境: {env}"}
    statements = _split_sql_statements(rendered)
    if not statements:
        return {"success": False, "message": "无可执行的 SQL"}
    results: list[dict[str, Any]] = []
    try:
        with DatabaseExecutor(env=env) as db:
            for stmt in statements:
                db.cursor.execute(stmt)
                # Detect a result set via cursor.description rather than the
                # leading keyword — CALL / stored procedures return rows too.
                if db.cursor.description is not None:
                    columns = [desc[0] for desc in (db.cursor.description or [])]
                    rows = db.cursor.fetchall()
                    truncated = len(rows) > 100
                    results.append({
                        "sql": stmt,
                        "type": "query",
                        "columns": columns,
                        "rows": [dict(zip(columns, row)) for row in rows[:100]],
                        "row_count": len(rows),
                        "truncated": truncated,
                    })
                else:
                    entry = {
                        "sql": stmt,
                        "type": "write",
                        "affected_rows": db.cursor.rowcount,
                        "lastrowid": getattr(db.cursor, "lastrowid", None),
                    }
                    # MySQL's affected_rows counts *changed* rows, so an UPDATE
                    # whose target value already matches reports 0 even though
                    # the WHERE clause matched an existing row. Parse the server
                    # message so callers can tell "row missing" apart from
                    # "row found, value already correct".
                    matched = _matched_rows_from_conn(db.conn)
                    if matched is not None:
                        entry["matched_rows"] = matched
                    results.append(entry)
                # Drain any extra result sets a CALL leaves behind so the next
                # statement doesn't hit "commands out of sync".
                try:
                    while db.cursor.nextset():
                        pass
                except Exception:  # noqa: BLE001 - best effort
                    pass
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "results": results,
            "logic_type": "sql",
            "env": env,
        }
    return {
        "success": True,
        "message": f"执行成功，共 {len(results)} 条语句",
        "results": results,
        "logic_type": "sql",
        "env": env,
    }


def _execute_sql_external(rendered: str, env: str, source: Any) -> dict[str, Any]:
    """Run multi-statement SQL against an external data source (douke/dowsure)."""
    import pymysql  # local import to keep top-level imports lean

    statements = _split_sql_statements(rendered)
    if not statements:
        return {"success": False, "message": "无可执行的 SQL"}

    if getattr(source, "read_only", False):
        for stmt in statements:
            if not stmt.lower().startswith(("select", "show", "describe", "desc", "explain", "with")):
                return {
                    "success": False,
                    "message": f"{env} 数据源为只读，禁止执行 {stmt.split()[0].upper()} 语句",
                    "logic_type": "sql",
                    "env": env,
                }

    uses_transaction_characteristics = bool(
        re.search(
            r"\bSET\s+TRANSACTION\s+(?:ISOLATION\s+LEVEL|READ\s+(?:ONLY|WRITE))\b",
            rendered,
            re.IGNORECASE,
        )
    )
    results: list[dict[str, Any]] = []
    connection = None
    try:
        connection = pymysql.connect(
            host=source.host,
            port=source.port,
            user=source.user,
            password=source.password,
            database=source.database or None,
            charset=source.charset,
            connect_timeout=15,
            read_timeout=60,
            write_timeout=60,
            autocommit=uses_transaction_characteristics,
        )
        with connection.cursor() as cursor:
            for stmt in statements:
                cursor.execute(stmt)
                # Detect a result set via cursor.description rather than the
                # leading keyword — CALL / stored procedures return rows too.
                if cursor.description is not None:
                    columns = [desc[0] for desc in (cursor.description or [])]
                    rows = cursor.fetchall()
                    truncated = len(rows) > 100
                    results.append({
                        "sql": stmt,
                        "type": "query",
                        "columns": columns,
                        "rows": [dict(zip(columns, row)) for row in rows[:100]],
                        "row_count": len(rows),
                        "truncated": truncated,
                    })
                else:
                    entry = {
                        "sql": stmt,
                        "type": "write",
                        "affected_rows": cursor.rowcount,
                        "lastrowid": getattr(cursor, "lastrowid", None),
                    }
                    # Same Rows matched parsing as the built-in path so the AI
                    # summary can distinguish "row missing" from "already at
                    # target value" on external sources too.
                    matched = _matched_rows_from_conn(connection)
                    if matched is not None:
                        entry["matched_rows"] = matched
                    results.append(entry)
                # Drain any extra result sets a CALL leaves behind so the next
                # statement doesn't hit "commands out of sync".
                try:
                    while cursor.nextset():
                        pass
                except Exception:  # noqa: BLE001 - best effort
                    pass
        connection.commit()
    except Exception as exc:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        return {
            "success": False,
            "message": str(exc),
            "results": results,
            "logic_type": "sql",
            "env": env,
        }
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    return {
        "success": True,
        "message": f"执行成功，共 {len(results)} 条语句",
        "results": results,
        "logic_type": "sql",
        "env": env,
    }


def _execute_http(rendered: str) -> dict[str, Any]:
    """Run a rendered HTTP request.

    Supported payload formats:
    - JSON object `{ "method": "POST", "url": "...", "headers": {...}, "body": ... }`
    - HTTP-style raw text starting with `METHOD URL`.
    """
    payload = _try_parse_json(rendered)
    if payload is None:
        payload = _parse_raw_http(rendered)
    if not payload:
        return {"success": False, "message": "无法解析 HTTP 请求内容"}

    method = (payload.get("method") or "GET").upper()
    url = payload.get("url")
    if not url:
        return {"success": False, "message": "缺少 url"}
    headers = payload.get("headers") or {}
    body = payload.get("body")
    params = payload.get("params")
    json_body = body if isinstance(body, (dict, list)) else None
    data_body = body if isinstance(body, (str, bytes)) else None

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            data=data_body,
            timeout=HTTP_EXECUTION_TIMEOUT,
        )
    except Exception as exc:
        return {"success": False, "message": str(exc), "logic_type": "http"}

    content_type = response.headers.get("content-type", "")
    response_body: Any
    if "application/json" in content_type:
        try:
            response_body = response.json()
        except Exception:
            response_body = response.text
    else:
        response_body = response.text[:5000]

    return {
        "success": response.ok,
        "message": f"HTTP {response.status_code}",
        "logic_type": "http",
        "request": {"method": method, "url": url, "headers": headers, "body": body, "params": params},
        "status_code": response.status_code,
        "response_headers": dict(response.headers),
        "response_body": response_body,
    }


def _parse_raw_http(text: str) -> Optional[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    lines = text.splitlines()
    first = lines[0].strip()
    parts = first.split()
    if len(parts) >= 2 and parts[0].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        method, url = parts[0].upper(), parts[1]
        body_idx = None
        headers: dict[str, str] = {}
        for idx in range(1, len(lines)):
            line = lines[idx].strip()
            if not line:
                body_idx = idx + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        body = "\n".join(lines[body_idx:]) if body_idx else None
        parsed_body: Any = body
        if body:
            try:
                parsed_body = json.loads(body)
            except Exception:
                parsed_body = body
        return {"method": method, "url": url, "headers": headers, "body": parsed_body}
    return None


def _execute_python(rendered: str, env: str) -> dict[str, Any]:
    """Run arbitrary admin-supplied Python with a captured stdout buffer."""
    buffer = io.StringIO()
    locals_ns: dict[str, Any] = {}
    globals_ns: dict[str, Any] = {
        "__builtins__": __builtins__,
        "DatabaseExecutor": DatabaseExecutor,
        "env": env,
        "requests": requests,
        "json": json,
    }
    try:
        with redirect_stdout(buffer):
            exec(rendered, globals_ns, locals_ns)  # noqa: S102 - admin only
    except Exception:
        return {
            "success": False,
            "message": "Python 执行抛出异常",
            "stdout": buffer.getvalue(),
            "traceback": traceback.format_exc(),
            "logic_type": "python",
            "env": env,
        }
    result = locals_ns.get("result")
    return {
        "success": True,
        "message": "Python 执行完成",
        "stdout": buffer.getvalue(),
        "result": result,
        "logic_type": "python",
        "env": env,
    }


# ---------------------------------------------------------------------------
# AI post-execution analysis
# ---------------------------------------------------------------------------

_AI_SUMMARY_SYSTEM_PROMPT = (
    "你是 DPU 提示词模板的执行解读助手。下面会给你一段管理员定义的模板、用户的自然语言诉求、"
    "AI 渲染后的真实脚本，以及刚刚的执行结果（含影响行数 / 返回行数 / 行数据预览 / 错误信息等）。"
    "请用中文给用户写一段『真正解读数据』的回复（2-5 句话，不是机械描述行数）。\n\n"
    "硬规则（违反任何一条都视为失败）：\n"
    "0) 必须分析查询结果里的关键字段值，而不是只说『查询返回 N 行』。\n"
    "   - 拿到 SELECT 结果时，请从每条语句的 rows_preview 里**逐字段抽取业务关键值**，例如："
    "application_status、sanction_status、application_unique_id、limit_application_unique_id、"
    "merchant_id、finance_product_currency、lender_code、event_type、status、is_ready、"
    "is_processed、succeed、created_at 等，并把它们当作解读的依据告诉用户。\n"
    "   - 如果有多条 event/通知记录，要分别说出哪些已 ready / succeed / 待处理，"
    "用具体的 event_type 或字段值来表达，例如『scheduled-submit 通知已 ready』。\n"
    "   - 解读要面向用户的诉求：用户问『是否可以放行』，就基于查到的字段值给出『可以放行 / 不可以放行 / 卡在 XX』的结论，并列出依据。\n"
    "1) 区分『没找到』和『找到但值已是目标值』这两种情况，绝对不能混为一谈：\n"
    "   - 写操作里若带有 matched_rows 字段，它表示 WHERE 命中的行数（affected_rows 只统计真正被修改的行）。\n"
    "   - matched_rows>=1 但 affected_rows=0：说明记录存在、WHERE 命中了，只是目标字段原本就已经是要设置的值，"
    "     应明确告诉用户『记录已存在且字段本来就是目标值，无需修改』，绝不能说没找到。\n"
    "   - matched_rows=0（或没有 matched_rows 且 affected_rows=0）、SELECT 行数=0、或执行抛错时，"
    "     才视为没改到 / 没查到，要明确说『在 {env} 没找到 / 未更新』，绝不能笼统地说『执行成功』。\n"
    "2) 仅当当前 env 确实没找到记录（matched_rows=0 或 SELECT 行数=0）、"
    "   且用户的诉求里包含明显的业务键（手机号、申请单号、merchant_id、offer_id 等）时，"
    "   才在 JSON 里输出 probe_sql：一条只读 SELECT，用同一个业务键在其它环境里探测这条记录是否存在、关键状态字段值。"
    "   如果记录在当前 env 已存在，不要输出 probe_sql。"
    "   probe_sql 必须以 SELECT 开头，不要分号结尾，不要 UPDATE/DELETE/INSERT。\n"
    "3) 失败时也要给出解读：说明在哪个环境失败、错误信息是什么、可能的原因（表/字段不存在、外键冲突、约束违反、网络/权限错误等）以及下一步建议。\n"
    "4) 输出格式：先用一句话给结论（成功/失败 + 关键判断），再用 1-3 条短句列出依据（关键字段=值）。\n"
    "返回严格 JSON：{\"summary\": \"...\", \"target_missing\": bool, \"probe_sql\": \"...\" 或 null, "
    "\"probe_label\": \"用什么键探测，例如 application_unique_id=EFA...\" 或 null}。"
    "绝不要输出 JSON 以外的内容。"
)


def _execution_signals(execution: dict[str, Any]) -> dict[str, Any]:
    """Compact summary of what _execute_logic produced, for AI consumption.

    For SELECT statements we keep enough row content so the model can quote
    actual column values (application_status, sanction_status, event_type, ...)
    rather than describing row counts in the abstract.
    """
    signals: dict[str, Any] = {
        "logic_type": execution.get("logic_type"),
        "env": execution.get("env"),
        "success": bool(execution.get("success")),
        "message": execution.get("message"),
    }
    results = execution.get("results") or []
    if isinstance(results, list):
        trimmed = []
        for item in results:
            entry = {
                "sql": item.get("sql"),
                "type": item.get("type"),
            }
            if item.get("type") == "write":
                entry["affected_rows"] = item.get("affected_rows")
                entry["lastrowid"] = item.get("lastrowid")
                if item.get("matched_rows") is not None:
                    entry["matched_rows"] = item.get("matched_rows")
            elif item.get("type") == "query":
                rows = item.get("rows") or []
                entry["row_count"] = item.get("row_count")
                entry["columns"] = item.get("columns")
                # Keep up to 20 rows so the model can spot ready/processed/etc.
                # event records, not just the first 3. Stringify Decimals/dates
                # so JSON serialisation always succeeds.
                entry["rows_preview"] = [_jsonable(row) for row in rows[:20]]
                if len(rows) > 20:
                    entry["rows_preview_truncated"] = True
            trimmed.append(entry)
        signals["results"] = trimmed
    # HTTP / Python pass-throughs
    if execution.get("status_code") is not None:
        signals["status_code"] = execution.get("status_code")
        signals["response_body_preview"] = _stringify_preview(execution.get("response_body"))
    if execution.get("stdout") is not None:
        signals["stdout_preview"] = (execution.get("stdout") or "")[:1000]
    if execution.get("traceback"):
        signals["traceback_tail"] = "\n".join(
            (execution.get("traceback") or "").splitlines()[-8:]
        )
    return signals


def _stringify_preview(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    return text[:1000]


def _jsonable(value: Any) -> Any:
    """Convert a DB row (with Decimal / datetime / bytes) into JSON-friendly types."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Decimal, datetime, date, time, UUID, bytes — fall back to str so the
    # summary prompt JSON always serialises cleanly.
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return repr(value)
    return str(value)


def _build_mechanical_summary(execution: dict[str, Any], env: str) -> str:
    """Deterministic summary used when the AI fails to produce one.

    Guarantees the AI 解读 panel always has text to show. We also quote a few
    interesting field values from SELECT previews (application_status,
    sanction_status, event_type, ...) so the fallback still tells the user
    *what* was found, not just how many rows.
    """
    env_text = env or "(未指定环境)"
    logic_type = (execution.get("logic_type") or "sql").lower()

    if not execution.get("success"):
        message = execution.get("message") or "执行失败"
        return f"在 {env_text} 执行失败：{message}"

    if logic_type == "sql":
        results = execution.get("results") or []
        if not results:
            return f"在 {env_text} 执行完成，但没有返回任何结果。"

        interesting = {
            "application_unique_id",
            "limit_application_unique_id",
            "application_status",
            "sanction_status",
            "finance_product_currency",
            "lender_code",
            "merchant_id",
            "event_type",
            "status",
            "is_ready",
            "is_processed",
            "succeed",
            "created_at",
            "updated_at",
        }
        parts: list[str] = []
        for index, item in enumerate(results, start=1):
            kind = item.get("type")
            if kind == "query":
                row_count = item.get("row_count", 0)
                rows = item.get("rows") or []
                if row_count == 0:
                    parts.append(f"语句 {index} 查询返回 0 行")
                else:
                    highlights: list[str] = []
                    for row in rows[:5]:
                        if not isinstance(row, dict):
                            continue
                        snippet = [
                            f"{k}={row.get(k)}" for k in row.keys() if k in interesting and row.get(k) is not None
                        ]
                        if snippet:
                            highlights.append("[" + ", ".join(snippet[:4]) + "]")
                    detail = "；".join(highlights) if highlights else ""
                    if detail:
                        parts.append(f"语句 {index} 查询返回 {row_count} 行（{detail}）")
                    else:
                        parts.append(f"语句 {index} 查询返回 {row_count} 行")
            elif kind == "write":
                affected = item.get("affected_rows", 0)
                matched = item.get("matched_rows")
                if matched is not None and matched >= 1 and affected == 0:
                    parts.append(
                        f"语句 {index} 命中 {matched} 行但 0 行被修改（字段已为目标值）"
                    )
                elif matched == 0 or (matched is None and affected == 0):
                    parts.append(f"语句 {index} 未命中任何记录")
                else:
                    parts.append(f"语句 {index} 修改了 {affected} 行")
            else:
                parts.append(f"语句 {index} 已执行")
        return f"在 {env_text} 执行了 {len(results)} 条 SQL：" + "；".join(parts) + "。"

    if logic_type == "http":
        status_code = execution.get("status_code")
        return f"在 {env_text} 调用 HTTP 完成，状态码 {status_code}。" if status_code is not None else "HTTP 调用完成。"

    if logic_type == "python":
        return f"在 {env_text} 已运行 Python 脚本。"

    return execution.get("message") or "执行完成。"


def _ai_summarise_execution(
    template: dict[str, Any],
    user_input: str,
    env: str,
    rendered: str,
    params: dict[str, Any],
    execution: dict[str, Any],
    model: Optional[str],
) -> dict[str, Any]:
    """Ask the model to translate the raw execution result into user-facing prose.

    Always returns a non-empty ``summary``: when the AI call fails or returns
    empty content we fall back to a deterministic mechanical summary so the
    frontend's AI 解读 panel always has something to show.
    """
    payload = {
        "模板标题": template.get("title", ""),
        "模板类型": template.get("logic_type", ""),
        "模板描述": template.get("description", ""),
        "当前环境": env or "(未指定)",
        "用户诉求": user_input,
        "AI 渲染后的脚本": rendered,
        "填入参数": params,
        "执行信号": _execution_signals(execution),
    }
    prompt_message = (
        "请基于下面的 JSON 给用户解读这次执行：\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n按系统指示输出 JSON。"
    )
    mechanical = _build_mechanical_summary(execution, env)
    known_summary = _known_template_error_summary(execution, env, params)
    if known_summary:
        return known_summary

    try:
        reply = _call_ai_raw(prompt_message, model, system_prompt=_AI_SUMMARY_SYSTEM_PROMPT)
    except Exception as exc:
        log.warning("summary call failed: %s", exc)
        return {"summary": mechanical, "target_missing": False, "probe_sql": None, "probe_label": None}

    parsed = _try_parse_json(reply or "")
    if not parsed:
        # Use whatever plain text the model produced, or fall back to mechanical.
        text = (reply or "").strip()
        return {
            "summary": text or mechanical,
            "target_missing": False,
            "probe_sql": None,
            "probe_label": None,
        }

    probe_sql = (parsed.get("probe_sql") or "").strip().rstrip(";").strip()
    if probe_sql and not probe_sql.lower().startswith("select"):
        # Reject anything that isn't a pure read.
        probe_sql = ""
    summary_text = (parsed.get("summary") or "").strip() or mechanical
    return {
        "summary": summary_text,
        "target_missing": bool(parsed.get("target_missing")),
        "probe_sql": probe_sql or None,
        "probe_label": (parsed.get("probe_label") or "").strip() or None,
    }


def _probe_other_envs(probe_sql: str, current_env: str) -> list[dict[str, Any]]:
    """Run a read-only SELECT across the other supported envs.

    Skips the current env and any env that fails to connect. Truncates each env's
    result to a small preview so the model and the user only see what matters.
    """
    if not probe_sql or not probe_sql.lower().startswith("select"):
        return []
    hits: list[dict[str, Any]] = []
    for env in SUPPORTED_ENVS:
        if env == current_env:
            continue
        try:
            with DatabaseExecutor(env=env) as db:
                db.cursor.execute(probe_sql)
                columns = [desc[0] for desc in (db.cursor.description or [])]
                rows = db.cursor.fetchall()
                if not rows:
                    continue
                preview = [dict(zip(columns, row)) for row in rows[:3]]
                hits.append({
                    "env": env,
                    "row_count": len(rows),
                    "columns": columns,
                    "rows": preview,
                })
        except Exception as exc:  # noqa: BLE001 - probe failures are informational
            log.info("probe in env=%s failed: %s", env, exc)
            continue
    return hits
