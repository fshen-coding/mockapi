# -*- coding: utf-8 -*-
"""Registration routes."""
import asyncio
import json
import logging

from fastapi import APIRouter

from web.models.requests import (
    Register3plLinkWaitRequest,
    Register3plRedirectRequest,
    RegisterAmazonRedirectRequest,
    RegisterAndRunMultiShopRequest,
    RegisterCreateOfferRequest,
    RegisterRequest,
    RegisterSendSmsRequest,
    RegisterSignupRequest,
    RegisterSpAuthCallbackRequest,
    RegisterSpAuthUrlRequest,
    RegisterSpUpdateOfferRequest,
    RegisterValidateSmsRequest,
)
from web.models.responses import ApiResponse
from web.routes.auth_guard import require_valid_username
from web.services.audit_store import audit_store
from web.services.mock_adapter import WebDPUMockService

router = APIRouter(prefix="/api", tags=["Registration"])
log = logging.getLogger(__name__)


@router.post("/register", response_model=ApiResponse)
async def register_account(req: RegisterRequest):
    username = require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.register_new_account_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
        funder_resource=req.funder_resource,
    )
    if result.get("success"):
        response = ApiResponse(success=True, message="registration succeeded", data=result)
    else:
        response = ApiResponse(success=False, message=result.get("error", "registration failed"), data=result)
    try:
        await asyncio.to_thread(
            audit_store.record_operation,
            username=username,
            session_data=None,
            operation_name=(req.operation_name or "RegisterAccount").strip(),
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=response.success,
        )
    except Exception:
        log.exception("Failed to record register audit")
    return response


@router.post("/register-and-run-multishop", response_model=ApiResponse)
async def register_and_run_multishop(req: RegisterAndRunMultiShopRequest):
    username = require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.register_and_run_multishop_flow_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
        funder_resource=req.funder_resource,
        sp_status=req.sp_status,
    )
    log_payload = {
        "request": req.model_dump(),
        "result": result,
    }
    if result.get("success"):
        log.info(
            "register and multishop flow completed: %s",
            json.dumps(log_payload, ensure_ascii=False, default=str),
        )
        response = ApiResponse(success=True, message="register and multishop flow succeeded", data=result)
        success = True
    else:
        log.error(
            "register and multishop flow failed: %s",
            json.dumps(log_payload, ensure_ascii=False, default=str),
        )
        response = ApiResponse(
            success=False,
            message=result.get("error", "register and multishop flow failed"),
            data=result,
        )
        success = False
    try:
        await asyncio.to_thread(
            audit_store.record_operation,
            username=username,
            session_data=result.get("session"),
            operation_name=(req.operation_name or "RegisterAndRunMultiShop").strip(),
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=success,
        )
    except Exception:
        log.exception("Failed to record multishop register audit")
    return response


# ---------------------------------------------------------------------------
# Step-by-step registration (used by the scenario tree). These are stateless
# wrappers around individual mock HTTP calls; each step takes the bits of state
# it needs from the previous step's response. The legacy /api/register and
# /api/register-and-run-multishop endpoints above are deliberately left alone
# so the dashboard's one-click button and the AI assistant tool keep working.
# ---------------------------------------------------------------------------

@router.post("/register/create-offer", response_model=ApiResponse)
async def register_create_offer(req: RegisterCreateOfferRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_create_offer_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="offer_id created", data=result)
    return ApiResponse(success=False, message=result.get("error", "create offer_id failed"), data=result)


@router.post("/register/amazon-redirect", response_model=ApiResponse)
async def register_amazon_redirect(req: RegisterAmazonRedirectRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_amazon_redirect_web,
        env=req.env,
        offer_id=req.offer_id,
        currency=req.currency,
        funder_resource=req.funder_resource,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="amazon redirect activated", data=result)
    return ApiResponse(success=False, message=result.get("error", "amazon redirect failed"), data=result)


@router.post("/register/send-sms", response_model=ApiResponse)
async def register_send_sms(req: RegisterSendSmsRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_send_register_sms_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
        funder_resource=req.funder_resource,
        offer_id=req.offer_id or "",
    )
    if result.get("success"):
        return ApiResponse(success=True, message="register sms triggered", data=result)
    return ApiResponse(success=False, message=result.get("error", "register sms failed"), data=result)


@router.post("/register/validate-sms", response_model=ApiResponse)
async def register_validate_sms(req: RegisterValidateSmsRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_validate_register_sms_web,
        env=req.env,
        phone_number=req.phone_number,
        currency=req.currency,
        funder_resource=req.funder_resource,
        offer_id=req.offer_id or "",
    )
    if result.get("success"):
        return ApiResponse(success=True, message="register sms validated", data=result)
    return ApiResponse(success=False, message=result.get("error", "register sms validate failed"), data=result)


@router.post("/register/signup", response_model=ApiResponse)
async def register_signup(req: RegisterSignupRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_signup_register_web,
        env=req.env,
        phone_number=req.phone_number,
        email=req.email,
        verification_code=req.verification_code,
        currency=req.currency,
        funder_resource=req.funder_resource,
        journey=req.journey,
        offline=req.offline,
        offer_id=req.offer_id or "",
    )
    if result.get("success"):
        return ApiResponse(success=True, message="register signup succeeded", data=result)
    return ApiResponse(success=False, message=result.get("error", "register signup failed"), data=result)


@router.post("/register/sp-auth-url", response_model=ApiResponse)
async def register_sp_auth_url(req: RegisterSpAuthUrlRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_sp_auth_url_web,
        env=req.env,
        phone_number=req.phone_number,
        token=req.token,
        currency=req.currency,
        funder_resource=req.funder_resource,
        offline=req.offline,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="sp-auth-url ok", data=result)
    return ApiResponse(success=False, message=result.get("error", "sp-auth-url failed"), data=result)


@router.post("/register/sp-auth-callback", response_model=ApiResponse)
async def register_sp_auth_callback(req: RegisterSpAuthCallbackRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_sp_auth_callback_web,
        env=req.env,
        phone_number=req.phone_number,
        token=req.token,
        state=req.state,
        selling_partner_id=req.selling_partner_id,
        currency=req.currency,
        funder_resource=req.funder_resource,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="sp-auth-callback ok", data=result)
    return ApiResponse(success=False, message=result.get("error", "sp-auth-callback failed"), data=result)


@router.post("/register/sp-update-offer", response_model=ApiResponse)
async def register_sp_update_offer(req: RegisterSpUpdateOfferRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_sp_update_offer_web,
        env=req.env,
        phone_number=req.phone_number,
        selling_partner_id=req.selling_partner_id,
        sp_status=req.sp_status,
        failure_reason_index=req.failure_reason_index,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="sp-update-offer ok", data=result)
    return ApiResponse(success=False, message=result.get("error", "sp-update-offer failed"), data=result)


@router.post("/register/3pl-link-wait", response_model=ApiResponse)
async def register_3pl_link_wait(req: Register3plLinkWaitRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_3pl_link_wait_web,
        env=req.env,
        phone_number=req.phone_number,
        selling_partner_id=req.selling_partner_id,
        offline=req.offline,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="manual offer ready", data=result)
    return ApiResponse(success=False, message=result.get("error", "manual offer wait failed"), data=result)


@router.post("/register/3pl-redirect", response_model=ApiResponse)
async def register_3pl_redirect(req: Register3plRedirectRequest):
    if req.username is not None:
        require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.step_3pl_redirect_web,
        env=req.env,
        phone_number=req.phone_number,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="3pl redirect ok", data=result)
    return ApiResponse(success=False, message=result.get("error", "3pl redirect failed"), data=result)


@router.post("/register/attach-session-token", response_model=ApiResponse)
async def register_attach_session_token(payload: dict):
    """Attach a freshly-issued user token to an existing session's service.

    The split register flow (`/api/register/*`) returns the signup token to
    the frontend; once the frontend connects a session, this endpoint copies
    the token onto the session's service instance so downstream `/api/mock/*`
    calls don't have to re-look it up from `dpu_users.token`.
    """
    from web.services.session_manager import session_manager  # local import to avoid cycles

    session_id = (payload or {}).get("session_id")
    token = (payload or {}).get("token")
    username = (payload or {}).get("username")
    if username is not None:
        require_valid_username(username)
    if not session_id or not token:
        return ApiResponse(success=False, message="session_id 与 token 都不能为空", data=None)
    ctx = session_manager.get_session(session_id)
    if not ctx:
        return ApiResponse(success=False, message="session 不存在或已过期", data=None)
    service = getattr(ctx, "service", None)
    if service is None:
        return ApiResponse(success=False, message="session 内部 service 不可用", data=None)
    service.session_user_token = str(token).strip()
    return ApiResponse(
        success=True,
        message="token 已绑定到 session",
        data={"session_id": session_id, "token_len": len(service.session_user_token)},
    )
