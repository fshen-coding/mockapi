# -*- coding: utf-8 -*-
"""System routes for health, enums, sessions, and logs."""
import asyncio
import json
import logging
import re
import time
from pathlib import Path
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, HTTPException
import requests

from web.models.requests import ConnectRequest
from web.models.responses import ApiResponse, ConnectResponse, EnumsResponse
from web.routes.auth_guard import require_admin, require_valid_username
from web.services.ai_service import available_ai_sql_data_sources
from web.services.audit_store import audit_store
from web.services.log_capture import ws_log_handler
from web.services.mock_adapter import WebDPUMockService
from web.services.session_manager import session_manager

router = APIRouter(prefix="/api", tags=["System"])
log = logging.getLogger(__name__)

ENV_MONITOR_TARGETS = [
    {"env": "dev", "label": "DEV", "url": "https://dpu-gateway-dev.dowsure.com"},
    {"env": "reg", "label": "REG", "url": "https://dpu-gateway-reg.dowsure.com"},
    {"env": "sit", "label": "SIT", "url": "https://sit.api.expressfinance.business.hsbc.com"},
    {"env": "uat", "label": "UAT", "url": "https://uat.api.expressfinance.business.hsbc.com"},
    {"env": "preprod", "label": "PREPROD", "url": "https://preprod.api.expressfinance.business.hsbc.com"},
]
ENV_MONITOR_CACHE: dict | None = None
ENV_MONITOR_REFRESHING = False
CHANNEL_MONITOR_INTERVAL_SECONDS = 30 * 60
CHANNEL_MONITOR_HISTORY_LIMIT = 60
CHANNEL_MONITOR_LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "environment_channel_monitor.jsonl"
CHANNEL_MONITOR_SAMPLES: dict[str, list[dict]] = {target["env"]: [] for target in ENV_MONITOR_TARGETS}
CHANNEL_MONITOR_TASK: asyncio.Task | None = None
CHANNEL_MONITOR_RUNNING = False
CHANNEL_MONITOR_NEXT_RUN_AT: float | None = None

STATUS_PATTERNS = [
    re.compile(r"status_code[\"']?\s*[:=]\s*(\d{3})", re.IGNORECASE),
    re.compile(r"status[\s_-]*code[：:\s]+(\d{3})", re.IGNORECASE),
    re.compile(r"响应状态码[：:\s]*(\d{3})"),
    re.compile(r"response status[：:\s]*(\d{3})", re.IGNORECASE),
    re.compile(r"POST status[：:\s]*(\d{3})", re.IGNORECASE),
]


def _status_to_monitor_state(status_code: int | None) -> str:
    if status_code is None:
        return "down"
    return "ok" if status_code < 500 else "degraded"


def _extract_status_code(text: str) -> int | None:
    for pattern in STATUS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            continue
    return None


def _channel_sample_state(success: bool, status_code: int | None) -> str:
    if success and status_code is not None and status_code < 500:
        return "ok"
    if status_code is not None and status_code < 500:
        return "degraded"
    return "down"


def _load_channel_monitor_samples() -> None:
    if not CHANNEL_MONITOR_LOG_PATH.exists():
        return
    loaded: dict[str, list[dict]] = {target["env"]: [] for target in ENV_MONITOR_TARGETS}
    try:
        with CHANNEL_MONITOR_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                except json.JSONDecodeError:
                    continue
                env = sample.get("env")
                if env in loaded:
                    loaded[env].append(sample)
    except OSError as exc:
        log.warning("channel monitor sample load failed: %s", exc)
        return
    for env, samples in loaded.items():
        CHANNEL_MONITOR_SAMPLES[env] = samples[-CHANNEL_MONITOR_HISTORY_LIMIT:]


def _append_channel_monitor_sample(sample: dict) -> None:
    env = sample.get("env")
    if env not in CHANNEL_MONITOR_SAMPLES:
        return
    CHANNEL_MONITOR_SAMPLES[env].append(sample)
    CHANNEL_MONITOR_SAMPLES[env] = CHANNEL_MONITOR_SAMPLES[env][-CHANNEL_MONITOR_HISTORY_LIMIT:]
    try:
        CHANNEL_MONITOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CHANNEL_MONITOR_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sample, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        log.warning("channel monitor sample write failed: %s", exc)


def _channel_monitor_summary(env: str) -> dict:
    samples = CHANNEL_MONITOR_SAMPLES.get(env, [])[-CHANNEL_MONITOR_HISTORY_LIMIT:]
    history = [sample.get("state", "down") for sample in samples]
    sample_count = len(history)
    availability = None
    if sample_count:
        success_count = sum(1 for state in history if state == "ok")
        availability = round(success_count / sample_count * 100, 2)
    last_sample = samples[-1] if samples else None
    next_run_at = ""
    if CHANNEL_MONITOR_NEXT_RUN_AT:
        next_run_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(CHANNEL_MONITOR_NEXT_RUN_AT))
    return {
        "channel_endpoint": "/api/register/send-sms",
        "channel_interval_seconds": CHANNEL_MONITOR_INTERVAL_SECONDS,
        "channel_next_run_at": next_run_at,
        "channel_checked_at": last_sample.get("checked_at", "") if last_sample else "",
        "channel_status": last_sample.get("state", "checking") if last_sample else "checking",
        "channel_success": last_sample.get("success") if last_sample else None,
        "channel_status_code": last_sample.get("status_code") if last_sample else None,
        "channel_latency_ms": last_sample.get("latency_ms") if last_sample else None,
        "channel_error": last_sample.get("error", "") if last_sample else "",
        "channel_availability": availability,
        "channel_sample_count": sample_count,
        "channel_history": history,
    }


def _run_channel_probe(target: dict) -> dict:
    start = time.perf_counter()
    result: dict = {}
    error = ""
    try:
        result = WebDPUMockService.step_send_register_sms_web(
            env=target["env"],
            journey="500K",
            currency="USD",
            offline=True,
            funder_resource="FUNDPARK",
            offer_id="",
        )
        success = bool(result.get("success"))
    except Exception as exc:  # noqa: BLE001 - background monitor must survive failures
        success = False
        error = str(exc)
    latency_ms = round((time.perf_counter() - start) * 1000)
    status_code = result.get("status_code") if result else None
    state = _channel_sample_state(success, status_code)
    return {
        "env": target["env"],
        "label": target["label"],
        "endpoint": "/api/register/send-sms",
        "phone_number": result.get("phone_number") if result else "",
        "success": success,
        "status_code": status_code,
        "state": state,
        "latency_ms": latency_ms,
        "error": error or result.get("error", "") if result else error,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


async def _run_channel_monitor_once() -> None:
    global ENV_MONITOR_CACHE
    results = await asyncio.gather(*[
        asyncio.to_thread(_run_channel_probe, target)
        for target in ENV_MONITOR_TARGETS
    ])
    for sample in results:
        _append_channel_monitor_sample(sample)
    if ENV_MONITOR_CACHE is not None:
        ENV_MONITOR_CACHE = await _build_environment_monitor_data()


async def _channel_monitor_loop() -> None:
    global CHANNEL_MONITOR_RUNNING, CHANNEL_MONITOR_NEXT_RUN_AT
    await asyncio.sleep(3)
    while True:
        CHANNEL_MONITOR_RUNNING = True
        try:
            await _run_channel_monitor_once()
        except Exception:
            log.exception("environment channel monitor run failed")
        finally:
            CHANNEL_MONITOR_RUNNING = False
            CHANNEL_MONITOR_NEXT_RUN_AT = time.time() + CHANNEL_MONITOR_INTERVAL_SECONDS
        await asyncio.sleep(CHANNEL_MONITOR_INTERVAL_SECONDS)


def start_environment_channel_monitor() -> None:
    global CHANNEL_MONITOR_TASK, CHANNEL_MONITOR_NEXT_RUN_AT
    if CHANNEL_MONITOR_TASK and not CHANNEL_MONITOR_TASK.done():
        return
    _load_channel_monitor_samples()
    CHANNEL_MONITOR_NEXT_RUN_AT = time.time() + 3
    CHANNEL_MONITOR_TASK = asyncio.create_task(_channel_monitor_loop())


async def stop_environment_channel_monitor() -> None:
    global CHANNEL_MONITOR_TASK
    if not CHANNEL_MONITOR_TASK:
        return
    CHANNEL_MONITOR_TASK.cancel()
    with suppress(asyncio.CancelledError):
        await CHANNEL_MONITOR_TASK
    CHANNEL_MONITOR_TASK = None


def _recent_environment_samples(logs: list[dict], base_url: str, limit: int = 60) -> list[dict]:
    samples: list[dict] = []
    for entry in logs:
        text = f"{entry.get('formatted', '')}\n{entry.get('message', '')}"
        if base_url not in text:
            continue
        status_code = _extract_status_code(text)
        samples.append({
            "status_code": status_code,
            "state": _status_to_monitor_state(status_code),
            "timestamp": entry.get("timestamp") or "",
            "created": entry.get("created") or 0,
        })
        if len(samples) >= limit:
            break
    return list(reversed(samples))


def _probe_environment(target: dict, logs: list[dict]) -> dict:
    samples = _recent_environment_samples(logs, target["url"])
    start = time.perf_counter()
    status = "down"
    status_code = None
    error = ""
    try:
        response = requests.get(target["url"], timeout=2, allow_redirects=False)
        status_code = response.status_code
        status = "operational" if status_code < 500 else "degraded"
    except requests.RequestException as exc:
        error = str(exc)
    latency_ms = round((time.perf_counter() - start) * 1000)
    history = [sample["state"] for sample in samples]
    sample_count = len(history)
    if sample_count:
        success_count = sum(1 for state in history if state == "ok")
        availability = round(success_count / sample_count * 100, 2)
    else:
        availability = None
    return {
        "env": target["env"],
        "display_env": target.get("display_env") or target["env"],
        "label": target["label"],
        "base_url": target["url"],
        "status": status,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "endpoint_ping_ms": latency_ms,
        "availability": availability,
        "sample_count": sample_count,
        "history": history,
        "error": error,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **_channel_monitor_summary(target["env"]),
    }


def _empty_environment_monitor_data() -> dict:
    checked_at = time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "overall": "checking",
        "checked_at": checked_at,
        "cached": False,
        "items": [
            {
                "env": target["env"],
                "display_env": target.get("display_env") or target["env"],
                "label": target["label"],
                "base_url": target["url"],
                "status": "checking",
                "status_code": None,
                "latency_ms": None,
                "endpoint_ping_ms": None,
                "availability": None,
                "sample_count": 0,
                "history": [],
                "error": "",
                "checked_at": checked_at,
                **_channel_monitor_summary(target["env"]),
            }
            for target in ENV_MONITOR_TARGETS
        ],
    }


async def _build_environment_monitor_data() -> dict:
    try:
        recent_logs = await asyncio.to_thread(ws_log_handler.query_logs, limit=2000)
    except Exception as exc:  # noqa: BLE001 - monitor should still return current ping
        log.warning("environment monitor recent log lookup failed: %s", exc)
        recent_logs = []
    results = await asyncio.gather(*[
        asyncio.to_thread(_probe_environment, target, recent_logs)
        for target in ENV_MONITOR_TARGETS
    ])
    overall = (
        "operational"
        if all(item["status"] == "operational" for item in results)
        else "degraded"
        if any(item["status"] == "operational" for item in results)
        else "down"
    )
    return {
        "overall": overall,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cached": False,
        "items": results,
    }


async def _refresh_environment_monitor_cache() -> None:
    global ENV_MONITOR_CACHE, ENV_MONITOR_REFRESHING
    if ENV_MONITOR_REFRESHING:
        return
    ENV_MONITOR_REFRESHING = True
    try:
        ENV_MONITOR_CACHE = await _build_environment_monitor_data()
    finally:
        ENV_MONITOR_REFRESHING = False


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/environments", response_model=ApiResponse)
async def list_environments():
    envs = ["sit", "uat", "dev", "preprod", "reg", "local"]
    return ApiResponse(success=True, message="environments loaded", data=envs)


@router.get("/environment-monitor", response_model=ApiResponse)
async def environment_monitor(force: bool = False):
    global ENV_MONITOR_CACHE
    if force:
        await _refresh_environment_monitor_cache()
    elif ENV_MONITOR_CACHE is None:
        asyncio.create_task(_refresh_environment_monitor_cache())

    data = ENV_MONITOR_CACHE or _empty_environment_monitor_data()
    if ENV_MONITOR_CACHE is not None and not force:
        data = {**ENV_MONITOR_CACHE, "cached": True}
    return ApiResponse(
        success=True,
        message="environment monitor loaded",
        data=data,
    )


@router.get("/enums", response_model=ApiResponse)
async def list_enums():
    data = EnumsResponse(
        environments=["sit", "uat", "dev", "preprod", "reg", "local"],
        ai_sql_data_sources=list(available_ai_sql_data_sources()),
        journeys=["200K", "500K", "2000K"],
        currencies=["USD", "CNY"],
        funder_resources=["FUNDPARK", "HSBC", "DOWSURE"],
        underwritten_statuses=["APPROVED", "REJECTED"],
        approved_offer_statuses=["APPROVED", "RETURNED", "REJECTED"],
        esign_statuses=["SUCCESS", "FAIL"],
        drawdown_statuses=["APPROVED", "REJECTED"],
        psp_start_statuses=["PROCESSING", "FAIL", "INITIAL"],
        psp_completed_statuses=["SUCCESS", "FAIL", "INITIAL"],
        repayment_statuses=["Success", "Failure"],
        system_event_types=[
            "EXCEPTION-APPLICATION-CREATION",
            "INDICATIVE-OFFER",
            "IN-PROCESS",
            "ERROR",
            "ETB-customer",
        ],
        returned_failure_reasons=[
            {"index": 1, "label": "incorrect BRN"},
            {"index": 2, "label": "unable to retrieve customer ID number"},
            {"index": 3, "label": "ID number does not match CR record"},
            {"index": 4, "label": "company structure validation failed"},
            {"index": 5, "label": "manual AML review required"},
            {"index": 6, "label": "incorrect unified social credit code"},
            {"index": 7, "label": "ID number does not match company registration data"},
        ],
        approved_rejection_reasons=[
            {"value": "fraud", "label": "fraud"},
            {"value": "others", "label": "others"},
        ],
        drawdown_failure_reasons=[
            {"index": 1, "code": "ER001", "label": "no valid bank account"},
            {"index": 2, "code": "ER002", "label": "available limit is lower than drawdown amount"},
            {"index": 3, "code": "ER003", "label": "unknown error"},
            {"index": 4, "code": "ER004", "label": "bank or payment service provider rejected"},
            {"index": 5, "code": "ER005", "label": "overdue"},
        ],
        repayment_failure_reasons=[
            {"index": 1, "code": "ER001", "label": "bank slip amount does not match repayment amount"},
            {"index": 2, "code": "ER002", "label": "operation rejected"},
        ],
        sp_update_failure_reasons=[
            {"index": 1, "label": "The lender country doesn't match with the Seller reporting country"},
            {"index": 2, "label": "Active credit approval exists"},
            {"index": 3, "label": "An offer already exists for the seller for the same partner product combination"},
            {"index": 4, "label": "others"},
        ],
        application_abandon_reasons=[
            {"value": "SellerCancelled", "label": "seller cancelled"},
            {"value": "OfferExpired", "label": "offer expired"},
            {"value": "ApplicationInfoNotSubmitted", "label": "application info not submitted"},
            {"value": "LenderOfferNotReturned", "label": "lender offer not returned"},
        ],
    )
    return ApiResponse(success=True, message="enums loaded", data=data.model_dump())


@router.post("/connect", response_model=ApiResponse)
async def connect(req: ConnectRequest):
    username = require_valid_username(req.username)
    try:
        ctx = await asyncio.to_thread(session_manager.create_session, req.env, req.phone_number)
        session_data = await asyncio.to_thread(session_manager.serialize_session, ctx)
        resp = ConnectResponse(
            session_id=session_data["session_id"],
            env=session_data["env"],
            phone_number=session_data["phone_number"],
            merchant_id=session_data.get("merchant_id"),
            preferred_currency=session_data.get("preferred_currency") or "USD",
            application_unique_id=session_data.get("application_unique_id"),
            selected_application_unique_id=session_data.get("selected_application_unique_id"),
            applications=session_data.get("applications") or [],
            finance_product_currency=session_data.get("finance_product_currency"),
            lender_code=session_data.get("lender_code"),
            application_status=session_data.get("application_status"),
        )
        try:
            await asyncio.to_thread(audit_store.record_session, username, resp.model_dump())
            await asyncio.to_thread(
                audit_store.record_operation,
                username=username,
                session_data=resp.model_dump(),
                operation_name="ConnectSession",
                request_payload=req.model_dump(),
                response_payload=ApiResponse(success=True, message="connected", data=resp.model_dump()).model_dump(),
                success=True,
            )
            log.info("Connect audit recorded | username=%s | session_id=%s", username, resp.session_id)
        except Exception:
            log.exception("Connect audit failed | username=%s | session_id=%s", username, resp.session_id)
        return ApiResponse(success=True, message="connected", data=resp.model_dump())
    except HTTPException:
        raise
    except LookupError:
        raise HTTPException(status_code=404, detail="PHONE_NOT_FOUND")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"connect failed: {exc}") from exc


@router.post("/disconnect", response_model=ApiResponse)
async def disconnect(session_id: str):
    destroyed = session_manager.destroy_session(session_id)
    if destroyed:
        try:
            await asyncio.to_thread(audit_store.mark_session_disconnected, session_id)
        except Exception:
            pass
        return ApiResponse(success=True, message="session disconnected")
    raise HTTPException(status_code=404, detail="session not found")


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(session_id: Optional[str] = None):
    if session_id:
        sessions = await asyncio.to_thread(session_manager.list_session, session_id)
    else:
        sessions = await asyncio.to_thread(session_manager.list_sessions)
    return ApiResponse(success=True, message=f"{len(sessions)} active sessions", data=sessions)


@router.get("/logs", response_model=ApiResponse)
async def query_logs(
    username: Optional[str] = None,
    keyword: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 500,
):
    require_admin(username)
    logs = await asyncio.to_thread(
        ws_log_handler.query_logs,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        session_id=session_id,
        limit=limit,
    )
    return ApiResponse(success=True, message=f"{len(logs)} matching logs", data=logs)


@router.get("/audit/operations", response_model=ApiResponse)
async def query_user_operations(
    username: Optional[str] = None,
    phone_number: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 200,
):
    """Return operation audit records.

    Admin can view all users when no target username is provided; normal users
    are always restricted to their own records.
    """
    caller = require_valid_username(username)
    is_admin = audit_store.get_user_role(caller) == "admin"
    rows = await asyncio.to_thread(
        audit_store.list_user_operations,
        username=None if is_admin else caller,
        phone_number=phone_number,
        session_id=session_id,
        limit=limit,
        include_all=is_admin,
    )
    return ApiResponse(success=True, message=f"{len(rows)} matching operations", data=rows)
