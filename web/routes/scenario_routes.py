# -*- coding: utf-8 -*-
"""Per-user scenario step parameter overrides.

The interface-test scenario tree lets users open a step, tweak its payload
fields (e.g. sp-update-offer's `sp_status` / `failure_reason_index`) and hit
"保存". Their choices are persisted per user via these endpoints so the next
scenario run automatically uses them — no need to re-enter the parameters on a
different machine or browser.
"""

from __future__ import annotations

import asyncio
import ast
import inspect
import logging
import re
import textwrap
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from web.models.responses import ApiResponse
from web.routes.auth_guard import require_admin, require_valid_username
from web.services.audit_store import audit_store, ADMIN_USERNAME

router = APIRouter(prefix="/api/scenario-overrides", tags=["Scenario Overrides"])
log = logging.getLogger(__name__)

# Admin-owned global config rows. Old per-user tables such as step order can
# reuse the admin row as the shared baseline without a migration.
# This makes the
# "admin 点保存 → 全员同步" behaviour work without a per-user migration — the
# admin's own historical rows already live under this key.
GLOBAL_CONFIG_OWNER = ADMIN_USERNAME


class ScenarioOverrideUpsertRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    step_key: str = Field(..., min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class ScenarioOverrideDeleteRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    step_key: str = Field(..., min_length=1, max_length=200)


class ScenarioMetaUpsertRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class ScenarioStepMetaUpsertRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    step_key: str = Field(..., min_length=1, max_length=200)
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_hidden: bool = False


class ScenarioStepMetaDeleteRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    step_key: str = Field(..., min_length=1, max_length=200)


class ScenarioStepOrderUpsertRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    step_order: list[str] = Field(default_factory=list)


def _normalize_step_source_endpoint(endpoint: str) -> str:
    value = (endpoint or "").strip().split("?", 1)[0]
    if value == "flow: register-and-run-multishop":
        return "/api/register-and-run-multishop"
    return value


def _source_block(title: str, module_path: str, obj: Any) -> dict[str, Any]:
    source_lines, start_line = inspect.getsourcelines(obj)
    source = "".join(source_lines).rstrip()
    return {
        "title": title,
        "language": "Python",
        "file": module_path,
        "function": getattr(obj, "__name__", ""),
        "start_line": start_line,
        "source": source,
        "planned_requests": _extract_planned_requests_from_source(source),
    }


def _node_source(source: str, node: ast.AST | None) -> Any:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    segment = ast.get_source_segment(source, node)
    if segment is not None:
        return segment
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _name_of_target(target: ast.AST) -> str:
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _dict_literal_values(source: str, node: ast.AST) -> dict[str, Any]:
    if not isinstance(node, ast.Dict):
        return {}
    out: dict[str, Any] = {}
    for key_node, value_node in zip(node.keys, node.values):
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            out[key_node.value] = _node_source(source, value_node)
    return out


def _resolve_expr(source: str, node: ast.AST | None, assignments: dict[str, Any]) -> Any:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return assignments.get(node.id, node.id)
    return _node_source(source, node)


def _resolve_source_value(value: Any, assignments: dict[str, Any]) -> Any:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return assignments.get(value, value)
    return value


def _method_from_call(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        name = func.attr.lower()
        if name == "get":
            return "GET"
        if name == "post":
            return "POST"
    return "POST"


def _add_planned_request(
    requests: list[dict[str, Any]],
    seen: set[str],
    *,
    source_name: str,
    method: Any,
    url: Any,
    headers: Any = None,
    body: Any = None,
    params: Any = None,
    line: int | None = None,
) -> None:
    if not url:
        return
    normalized_method = str(method or "POST").strip("'\"") or "POST"
    key = f"{normalized_method}|{url}|{body}|{params}|{headers}"
    if key in seen:
        return
    seen.add(key)
    requests.append({
        "source": source_name,
        "method": normalized_method,
        "url": url,
        "headers": headers,
        "body": body,
        "params": params,
        "line": line,
    })


def _extract_planned_requests_from_source(source: str) -> list[dict[str, Any]]:
    dedented = textwrap.dedent(source)
    try:
        tree = ast.parse(dedented)
    except SyntaxError:
        return []

    assignments: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target_name = _name_of_target(node.targets[0])
            if target_name:
                assignments[target_name] = _node_source(dedented, node.value)

    requests: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target_name = _name_of_target(node.targets[0])
            values = _dict_literal_values(dedented, node.value)
            if target_name and "request_info" in target_name and values.get("url"):
                _add_planned_request(
                    requests,
                    seen,
                    source_name=target_name,
                    method=values.get("method") or "POST",
                    url=_resolve_source_value(values.get("url"), assignments),
                    headers=_resolve_source_value(values.get("headers"), assignments),
                    body=_resolve_source_value(values.get("body"), assignments),
                    params=_resolve_source_value(values.get("params"), assignments),
                    line=getattr(node, "lineno", None),
                )
        elif isinstance(node, ast.Call):
            func = node.func
            func_name = func.attr if isinstance(func, ast.Attribute) else ""
            if func_name in {"_do_post_custom", "_do_post_custom_with_retry"}:
                kw = {item.arg: item.value for item in node.keywords if item.arg}
                _add_planned_request(
                    requests,
                    seen,
                    source_name=func_name,
                    method="POST",
                    url=_resolve_expr(dedented, node.args[0] if node.args else None, assignments),
                    headers=_resolve_expr(dedented, kw.get("headers"), assignments),
                    body=_resolve_expr(dedented, kw.get("json_data"), assignments),
                    params=_resolve_expr(dedented, kw.get("params"), assignments),
                    line=getattr(node, "lineno", None),
                )
            elif func_name == "_do_post_webhook":
                _add_planned_request(
                    requests,
                    seen,
                    source_name=func_name,
                    method="POST",
                    url="self.api_config.webhook_url",
                    body=_resolve_expr(dedented, node.args[0] if node.args else None, assignments),
                    line=getattr(node, "lineno", None),
                )
            elif (
                func_name in {"post", "get"}
                and isinstance(func.value, ast.Name)
                and func.value.id in {"http_requests", "requests"}
            ):
                kw = {item.arg: item.value for item in node.keywords if item.arg}
                _add_planned_request(
                    requests,
                    seen,
                    source_name=f"http_requests.{func_name}",
                    method=_method_from_call(node),
                    url=_resolve_expr(dedented, node.args[0] if node.args else None, assignments),
                    headers=_resolve_expr(dedented, kw.get("headers"), assignments),
                    body=_resolve_expr(dedented, kw.get("json"), assignments),
                    params=_resolve_expr(dedented, kw.get("params"), assignments),
                    line=getattr(node, "lineno", None),
                )
    return requests


def _find_step_source_blocks(endpoint: str) -> list[dict[str, Any]]:
    from web.routes import mock_routes, register_routes
    from web.services.mock_adapter import WebDPUMockService

    normalized = _normalize_step_source_endpoint(endpoint)
    route_modules = [
        (register_routes.router, "mockapi/web/routes/register_routes.py"),
        (mock_routes.router, "mockapi/web/routes/mock_routes.py"),
    ]
    blocks: list[dict[str, Any]] = []
    handler_source = ""

    for router_obj, module_path in route_modules:
        prefix = getattr(router_obj, "prefix", "")
        for route in getattr(router_obj, "routes", []):
            route_path = getattr(route, "path", "")
            candidates = {route_path}
            if prefix and not route_path.startswith(prefix):
                candidates.add(f"{prefix}{route_path}")
            if normalized not in candidates:
                continue
            endpoint_func = getattr(route, "endpoint", None)
            if endpoint_func is None:
                continue
            blocks.append(_source_block("FastAPI route handler", module_path, endpoint_func))
            handler_source = blocks[-1]["source"]
            break
        if blocks:
            break

    method_names = set(re.findall(r"service\.([A-Za-z_][A-Za-z0-9_]*)", handler_source))
    method_names.update(re.findall(r"WebDPUMockService\.([A-Za-z_][A-Za-z0-9_]*)", handler_source))
    for method_name in sorted(method_names):
        method = getattr(WebDPUMockService, method_name, None)
        if method is not None:
            blocks.append(_source_block("Service method", "mockapi/web/services/mock_adapter.py", method))

    return blocks


@router.get("", response_model=ApiResponse)
async def list_scenario_step_overrides(username: Optional[str] = None):
    caller = require_valid_username(username)
    rows = await asyncio.to_thread(audit_store.list_scenario_step_overrides, caller)
    return ApiResponse(success=True, message=f"{len(rows)} overrides", data=rows)


@router.post("", response_model=ApiResponse)
async def upsert_scenario_step_override(req: ScenarioOverrideUpsertRequest):
    caller = require_valid_username(req.username)
    try:
        row = await asyncio.to_thread(
            audit_store.upsert_scenario_step_override,
            caller,
            req.scenario_key,
            req.step_key,
            req.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="override saved", data=row)


@router.delete("", response_model=ApiResponse)
async def delete_scenario_step_override(req: ScenarioOverrideDeleteRequest):
    caller = require_valid_username(req.username)
    ok = await asyncio.to_thread(
        audit_store.delete_scenario_step_override,
        caller,
        req.scenario_key,
        req.step_key,
    )
    return ApiResponse(
        success=True,
        message="override deleted" if ok else "no override to delete",
        data={"deleted": bool(ok)},
    )


# ---------------------------------------------------------------------------
# Scenario meta overrides (name / description) — admin editable, visible to all.
# ---------------------------------------------------------------------------

@router.get("/meta", response_model=ApiResponse)
async def list_scenario_meta_overrides(username: Optional[str] = None):
    if username is not None:
        require_valid_username(username)
    rows = await asyncio.to_thread(audit_store.list_scenario_meta_overrides)
    return ApiResponse(success=True, message=f"{len(rows)} meta overrides", data=rows)


@router.post("/meta", response_model=ApiResponse)
async def upsert_scenario_meta_override(req: ScenarioMetaUpsertRequest):
    caller = require_admin(req.username)
    try:
        row = await asyncio.to_thread(
            audit_store.upsert_scenario_meta_override,
            req.scenario_key,
            req.name,
            req.description,
            caller,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="scenario meta updated", data=row)


# ---------------------------------------------------------------------------
# Scenario step meta overrides (title / description / soft hide) - admin global.
# ---------------------------------------------------------------------------

@router.get("/step-meta", response_model=ApiResponse)
async def list_scenario_step_meta_overrides(username: Optional[str] = None):
    if username is not None:
        require_valid_username(username)
    rows = await asyncio.to_thread(audit_store.list_scenario_step_meta_overrides)
    return ApiResponse(success=True, message=f"{len(rows)} step meta overrides", data=rows)


@router.post("/step-meta", response_model=ApiResponse)
async def upsert_scenario_step_meta_override(req: ScenarioStepMetaUpsertRequest):
    caller = require_admin(req.username)
    try:
        row = await asyncio.to_thread(
            audit_store.upsert_scenario_step_meta_override,
            req.scenario_key,
            req.step_key,
            req.title,
            req.description,
            req.is_hidden,
            caller,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="scenario step meta updated", data=row)


@router.delete("/step-meta", response_model=ApiResponse)
async def delete_scenario_step_meta_override(req: ScenarioStepMetaDeleteRequest):
    caller = require_admin(req.username)
    ok = await asyncio.to_thread(
        audit_store.delete_scenario_step_meta_override,
        req.scenario_key,
        req.step_key,
    )
    return ApiResponse(
        success=True,
        message="scenario step meta deleted" if ok else "no step meta override to delete",
        data={"deleted": bool(ok), "updated_by": caller},
    )


@router.get("/step-source", response_model=ApiResponse)
async def get_scenario_step_source(endpoint: str):
    normalized = _normalize_step_source_endpoint(endpoint)
    blocks = await asyncio.to_thread(_find_step_source_blocks, endpoint)
    planned_requests = [
        {**request, "block_title": block.get("title"), "file": block.get("file"), "function": block.get("function")}
        for block in blocks
        for request in (block.get("planned_requests") or [])
    ]
    return ApiResponse(
        success=True,
        message=f"{len(blocks)} source blocks",
        data={
            "language": "Python",
            "endpoint": normalized,
            "planned_requests": planned_requests,
            "blocks": blocks,
        },
    )


# ---------------------------------------------------------------------------
# Per-user drag-and-drop step ordering. Each user picks their own order for
# each scenario (unlike scenario meta which is global admin-managed).
# ---------------------------------------------------------------------------

@router.get("/order", response_model=ApiResponse)
async def list_scenario_step_orders(username: Optional[str] = None):
    # Global drag order: every user reads the admin-owned rows.
    require_valid_username(username)
    rows = await asyncio.to_thread(audit_store.list_scenario_step_orders, GLOBAL_CONFIG_OWNER)
    return ApiResponse(success=True, message=f"{len(rows)} step orders", data=rows)


@router.post("/order", response_model=ApiResponse)
async def upsert_scenario_step_order(req: ScenarioStepOrderUpsertRequest):
    # Admin-only: step order is global config now.
    require_admin(req.username)
    try:
        row = await asyncio.to_thread(
            audit_store.upsert_scenario_step_order,
            GLOBAL_CONFIG_OWNER,
            req.scenario_key,
            req.step_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="step order saved", data=row)
