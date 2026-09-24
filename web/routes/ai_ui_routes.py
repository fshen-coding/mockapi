"""HTTP API for the independent AI UI automation mode."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from web.models.responses import ApiResponse
from web.routes.auth_guard import require_valid_username
from web.services.ai_ui_automation import (
    build_run_sop,
    delete_case,
    generate_case_spec,
    get_run,
    list_cases,
    list_runs,
    runtime_status,
    save_case,
    start_run,
    stop_run,
)

router = APIRouter(prefix="/api/ai-ui", tags=["AI UI 自动化"])


class AiUiCaseRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=200)
    environment: str = Field(default="custom", max_length=40)
    url: str = Field(default="", max_length=2000)
    prompt: str = Field(..., min_length=1, max_length=20000)
    context: str = Field(default="", max_length=5000)
    variables: dict[str, str] = Field(default_factory=dict)
    structured_spec: dict[str, Any] | None = None
    headed: bool = False
    viewport: dict[str, int] = Field(default_factory=lambda: {"width": 1440, "height": 900})


class AiUiRunRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    case_id: str = Field(..., min_length=1, max_length=120)


class AiUiGenerateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    instruction: str = Field(..., min_length=8, max_length=10000)
    environment: str = Field(default="custom", max_length=40)
    context: str = Field(default="", max_length=5000)


@router.get("/status", response_model=ApiResponse)
async def get_ai_ui_status(username: str):
    require_valid_username(username)
    return ApiResponse(success=True, message="AI UI runtime status", data=runtime_status())


@router.get("/cases", response_model=ApiResponse)
async def get_ai_ui_cases(username: str):
    require_valid_username(username)
    return ApiResponse(success=True, message="AI UI cases", data=await asyncio.to_thread(list_cases, username))


@router.post("/generate", response_model=ApiResponse)
async def generate_ai_ui_case(req: AiUiGenerateRequest):
    require_valid_username(req.username)
    try:
        result = await asyncio.to_thread(
            generate_case_spec,
            req.instruction,
            req.environment,
            req.context,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="AI UI 结构化用例已生成", data=result)


@router.post("/cases", response_model=ApiResponse)
async def create_ai_ui_case(req: AiUiCaseRequest):
    caller = require_valid_username(req.username)
    try:
        row = await asyncio.to_thread(save_case, caller, req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="AI UI 用例已创建", data=row)


@router.put("/cases/{case_id}", response_model=ApiResponse)
async def update_ai_ui_case(case_id: str, req: AiUiCaseRequest):
    caller = require_valid_username(req.username)
    try:
        row = await asyncio.to_thread(save_case, caller, req.model_dump(), case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="AI UI 用例已更新", data=row)


@router.delete("/cases/{case_id}", response_model=ApiResponse)
async def remove_ai_ui_case(case_id: str, username: str):
    caller = require_valid_username(username)
    ok = await asyncio.to_thread(delete_case, caller, case_id)
    if not ok:
        raise HTTPException(status_code=404, detail="AI UI 用例不存在")
    return ApiResponse(success=True, message="AI UI 用例已删除", data=None)


@router.get("/runs", response_model=ApiResponse)
async def get_ai_ui_runs(username: str):
    require_valid_username(username)
    return ApiResponse(success=True, message="AI UI runs", data=await asyncio.to_thread(list_runs, username))


@router.post("/runs", response_model=ApiResponse)
async def create_ai_ui_run(req: AiUiRunRequest):
    caller = require_valid_username(req.username)
    cases = await asyncio.to_thread(list_cases, caller)
    case = next((item for item in cases if item.get("id") == req.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="AI UI 用例不存在")
    try:
        run = await asyncio.to_thread(start_run, caller, case)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, message="AI UI 用例已启动", data=run)


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def get_ai_ui_run(run_id: str, username: str):
    caller = require_valid_username(username)
    run = await asyncio.to_thread(get_run, caller, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="AI UI 执行记录不存在")
    return ApiResponse(success=True, message="AI UI run", data=run)


@router.get("/runs/{run_id}/report")
async def get_ai_ui_report(run_id: str, username: str):
    caller = require_valid_username(username)
    run = await asyncio.to_thread(get_run, caller, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="AI UI 执行记录不存在")
    report_file = Path(str(run.get("report_file") or ""))
    if not report_file.is_file():
        raise HTTPException(status_code=404, detail="Midscene 报告尚未生成")
    return FileResponse(report_file, media_type="text/html", filename=f"ai-ui-{run_id}.html")


@router.get("/runs/{run_id}/sop")
async def get_ai_ui_sop(run_id: str, username: str):
    caller = require_valid_username(username)
    try:
        archive = await asyncio.to_thread(build_run_sop, caller, run_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if archive is None:
        raise HTTPException(status_code=404, detail="AI UI 执行记录不存在")
    return FileResponse(archive, media_type="application/zip", filename=f"ai-ui-sop-{run_id}.zip")


@router.post("/runs/{run_id}/stop", response_model=ApiResponse)
async def stop_ai_ui_run(run_id: str, username: str):
    caller = require_valid_username(username)
    run = await asyncio.to_thread(stop_run, caller, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="AI UI 执行记录不存在")
    return ApiResponse(success=True, message="AI UI 执行已停止", data=run)
