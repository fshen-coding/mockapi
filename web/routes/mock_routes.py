# -*- coding: utf-8 -*-
"""Mock operation routes."""
import asyncio
import json
import threading
import time
import uuid
from urllib.parse import urlparse

import requests as http_requests
from fastapi import APIRouter, HTTPException

from web.models.requests import (
    LinkSp3plRequest, UnderwrittenRequest, ApprovedOfferRequest,
    DowsureCreditResultRequest, WebankCreditResultRequest,
    CgbCreditResultRequest, CgbLoanResultRequest, CgbRepaymentResultRequest,
    WebankDrawdownResultRequest, WebankRepaymentResultRequest,
    DowsureEsignDrawdownResultRequest,
    DowsureRepaymentResultRequest, DowsureRetryCallbackRequest,
    PspStartRequest, PspCompletedRequest, StartReassessmentRequest, EsignRequest, DrawdownRequest,
    RepaymentStartRequest, RepaymentRequest,
    MultiShopBindingRequest, SpStatusUpdateRequest, MultiShop3plRedirectRequest,
    SystemEventRequest, BossApplicationStatusRequest, PspHsbcStartRequest, PspHsbcCompletedRequest,
    PspHsbcCompleteAllRequest,
    ApplicationAbandonRequest,
    CreateApplicationContextRequest, FpApplicationStepRequest,
    ShopPerformanceUpdateRequest,
    UpstreamDebugRequest,
)
from web.models.responses import ApiResponse
from web.routes.auth_guard import require_admin, require_valid_username
from web.services.audit_store import ADMIN_USERNAME, audit_store
from web.services.mock_adapter import WebDPUMockService
from web.services.session_manager import session_manager

router = APIRouter(prefix="/api/mock", tags=["Mock"])

_scheduled_submit_jobs: dict[str, dict] = {}
_scheduled_submit_jobs_lock = threading.Lock()
_SCHEDULED_SUBMIT_JOB_TTL_SECONDS = 3600
_DOWSURE_COMPANY_TEMPLATE_SCENARIO = "mockApi"
_DOWSURE_COMPANY_TEMPLATE_STEP = "dowsure-cny-company-templates"


def _find_dowsure_company_template(username: str | None, cn_name: str | None) -> dict | None:
    if not (username or "").strip() or not (cn_name or "").strip():
        return None
    selected_name = str(cn_name).strip()
    rows = audit_store.list_scenario_step_overrides(ADMIN_USERNAME)
    for row in rows:
        if (
            row.get("scenario_key") != _DOWSURE_COMPANY_TEMPLATE_SCENARIO
            or row.get("step_key") != _DOWSURE_COMPANY_TEMPLATE_STEP
        ):
            continue
        templates = (row.get("payload") or {}).get("templates")
        if not isinstance(templates, list):
            return None
        for item in templates:
            template = item.get("template") if isinstance(item, dict) else None
            if not isinstance(template, dict):
                continue
            if str(item.get("name") or "").strip() == selected_name:
                return item
            if str(template.get("cnName") or "").strip() == selected_name:
                return item
    return None


def _cleanup_scheduled_submit_jobs() -> None:
    cutoff = time.time() - _SCHEDULED_SUBMIT_JOB_TTL_SECONDS
    with _scheduled_submit_jobs_lock:
        expired_job_ids = [
            job_id
            for job_id, job in _scheduled_submit_jobs.items()
            if job.get("created_at", 0) < cutoff
        ]
        for job_id in expired_job_ids:
            _scheduled_submit_jobs.pop(job_id, None)


def _get_scheduled_submit_job(job_id: str) -> dict | None:
    _cleanup_scheduled_submit_jobs()
    with _scheduled_submit_jobs_lock:
        job = _scheduled_submit_jobs.get(job_id)
        return dict(job) if job else None


def _update_scheduled_submit_job(job_id: str, **updates) -> None:
    with _scheduled_submit_jobs_lock:
        job = _scheduled_submit_jobs.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = time.time()


def _run_scheduled_submit_job(job_id: str, service, journey: str | None) -> None:
    _update_scheduled_submit_job(job_id, status="RUNNING", started_at=time.time())
    try:
        result = service.run_fp_scheduled_tasks_and_poll_submitted_web(journey)
        status = "SUCCESS" if result.get("success") else "FAILED"
        _update_scheduled_submit_job(
            job_id,
            status=status,
            success=bool(result.get("success")),
            result=result,
            error=result.get("error") or result.get("error_message"),
            completed_at=time.time(),
        )
    except Exception as exc:
        _update_scheduled_submit_job(
            job_id,
            status="FAILED",
            success=False,
            result={
                "success": False,
                "error": str(exc),
            },
            error=str(exc),
            completed_at=time.time(),
        )


def _get_service(session_id: str, application_unique_id: str | None = None, username: str | None = None):
    """Get the service instance from a live session."""
    if username is not None:
        require_valid_username(username)
    ctx = session_manager.get_session(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="session not found or expired")
    if application_unique_id:
        try:
            ctx = session_manager.select_application(session_id, application_unique_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found or expired") from exc
    return ctx.service


def _get_context(session_id: str):
    """Get a live session context for read-only refresh endpoints."""
    ctx = session_manager.get_session(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="session not found or expired")
    return ctx


def _serialize_context(session_id: str) -> dict | None:
    ctx = session_manager.get_session(session_id)
    if not ctx:
        return None
    return session_manager.serialize_session(ctx)


def _operation_response(req, operation_name: str, result: dict, message: str) -> ApiResponse:
    username = require_valid_username(getattr(req, "username", None))
    audit_operation_name = (getattr(req, "operation_name", None) or operation_name).strip()
    success = result.get("success", False)
    response = ApiResponse(success=success, message=message, data=result)
    try:
        audit_store.record_operation(
            username=username,
            session_data=_serialize_context(req.session_id),
            operation_name=audit_operation_name,
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=success,
        )
    except Exception:
        # Audit persistence should not block a mock operation result.
        import logging
        logging.getLogger(__name__).exception("Failed to record mock operation audit")
    return response


@router.post("/upstream-debug", response_model=ApiResponse)
async def debug_upstream_request(req: UpstreamDebugRequest):
    """Send one editable request to the real upstream service for debugging."""
    username = require_valid_username(req.username)
    parsed = urlparse(req.url)
    request_info = {
        "method": req.method,
        "url": req.url,
        "headers": req.headers or {},
        "params": req.params or {},
        "body": req.body,
    }
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ApiResponse(
            success=False,
            message="invalid upstream url",
            data={
                "success": False,
                "error": "请填写合法的 http/https 上游 URL",
                "request_info": request_info,
            },
        )

    method = req.method.upper()
    headers = {
        str(key): str(value)
        for key, value in (req.headers or {}).items()
        if value is not None
    }
    request_kwargs = {
        "method": method,
        "url": req.url,
        "headers": headers or None,
        "params": req.params or None,
        "timeout": req.timeout_seconds,
    }
    if method != "GET" and req.body is not None:
        request_kwargs["json"] = req.body

    try:
        resp = await asyncio.to_thread(http_requests.request, **request_kwargs)
        try:
            response_json = resp.json()
        except ValueError:
            response_json = None
        response_body = (
            json.dumps(response_json, ensure_ascii=False, indent=2)
            if response_json is not None
            else resp.text
        )
        success = 200 <= resp.status_code < 400
        result = {
            "success": success,
            "status_code": resp.status_code,
            "request_info": request_info,
            "response_info": {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": response_body,
                "json": response_json,
            },
            "response_headers": dict(resp.headers),
            "response_body": response_body,
            "response_json": response_json,
        }
        response = ApiResponse(
            success=True,
            message="upstream request completed" if success else "upstream request failed",
            data=result,
        )
    except Exception as exc:
        result = {
            "success": False,
            "error": str(exc),
            "request_info": request_info,
        }
        response = ApiResponse(success=False, message=str(exc), data=result)

    try:
        audit_store.record_operation(
            username=username,
            session_data=None,
            operation_name=(req.operation_name or "upstream-debug").strip(),
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=response.success,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to record upstream debug audit")
    return response


# 1. SP-3PL 閸忓疇浠?
@router.post("/link-sp-3pl", response_model=ApiResponse)
async def mock_link_sp_3pl(req: LinkSp3plRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.mock_link_sp_3pl_shop)
    return _operation_response(req, req.__class__.__name__, result, "SP-3PL鍏宠仈瀹屾垚")


# 2. 閺嶉晲绻?
@router.post("/underwritten", response_model=ApiResponse)
async def mock_underwritten(req: UnderwrittenRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_underwritten_status,
        amount=req.amount,
        status=req.status,
        limit_application_unique_id=req.limit_application_unique_id,
        use_latest_submitted_limit_application=req.use_latest_submitted_limit_application,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 3. 鐎光剝澹?
@router.post("/approved-offer", response_model=ApiResponse)
async def mock_approved_offer(req: ApprovedOfferRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_approved_offer_status,
        amount=req.amount, status=req.status,
        failure_reason_index=req.failure_reason_index,
        rejection_reason=req.rejection_reason,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 4. PSP 瀵偓婵?
@router.post("/psp-start", response_model=ApiResponse)
async def mock_psp_start(req: PspStartRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_start_status,
        status=req.status,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 5. PSP 鐎瑰本鍨?
@router.post("/psp-completed", response_model=ApiResponse)
async def mock_psp_completed(req: PspCompletedRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_completed_status,
        status=req.status,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/start-reassessment", response_model=ApiResponse)
async def mock_start_reassessment(req: StartReassessmentRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.start_reassessment_web,
        business_context=req.business_context,
        currency=req.currency,
        funder_resource=req.funder_resource,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/restart-reassessment", response_model=ApiResponse)
async def mock_restart_reassessment(req: StartReassessmentRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.start_reassessment_web,
        business_context=req.business_context,
        currency=req.currency,
        funder_resource=req.funder_resource,
    )
    msg = "reassessment restarted" if result.get("success") else result.get("error", "reassessment restart failed")
    return _operation_response(req, "RestartReassessmentRequest", result, msg)


# 6. 閻㈤潧鐡欑粵?
@router.post("/esign", response_model=ApiResponse)
async def mock_esign(req: EsignRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_esign_status, signed_amount=req.signed_amount, status=req.status
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 7. 閺€鐐儥
@router.post("/drawdown", response_model=ApiResponse)
async def mock_drawdown(req: DrawdownRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_drawdown_status,
        amount=req.amount, status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 8. 鏉╂ɑ顑欏鈧慨?
@router.post("/repayment-start", response_model=ApiResponse)
async def mock_repayment_start(req: RepaymentStartRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_repayment_start_status,
        principal_amount=req.principal_amount,
        outstanding_amount=req.outstanding_amount,
        loan_code=req.loan_code,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 9. 鏉╂ɑ顑?
@router.post("/repayment", response_model=ApiResponse)
async def mock_repayment(req: RepaymentRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_repayment_status,
        principal_amount=req.principal_amount,
        outstanding_amount=req.outstanding_amount,
        status=req.status,
        failure_reason_index=req.failure_reason_index,
        loan_code=req.loan_code,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 10. 婢舵艾绨甸柧?SP 缂佹垵鐣?
@router.post("/multi-shop-binding", response_model=ApiResponse)
async def mock_multi_shop_binding(req: MultiShopBindingRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_multi_shop_binding,
        state=req.state,
        platform_seller_id=req.platform_seller_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 11. SP 閻樿埖鈧焦娲块弬?
@router.post("/sp-status-update", response_model=ApiResponse)
async def mock_sp_status_update(req: SpStatusUpdateRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_sp_status_update,
        platform_seller_id=req.platform_seller_id,
        status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 12. 3PL 闁插秴鐣鹃崥?
@router.post("/multi-shop-3pl-redirect", response_model=ApiResponse)
async def mock_multi_shop_3pl_redirect(req: MultiShop3plRedirectRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.mock_multi_shop_3pl_redirect)
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/create-application-context", response_model=ApiResponse)
async def create_application_context(req: CreateApplicationContextRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.ensure_application_context_web,
        req.journey,
        req.currency,
        req.funder_resource,
        req.tier_code,
        req.offer_id,
    )
    msg = "application context prepared" if result.get("success") else result.get("error", "application context prepare failed")
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/fp-business-profile", response_model=ApiResponse)
async def submit_fp_business_profile(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    company_template_bundle = await asyncio.to_thread(
        _find_dowsure_company_template,
        req.username,
        req.cnName,
    )
    result = await asyncio.to_thread(
        service.submit_fp_business_profile_web,
        req.journey,
        req.currency,
        req.funder_resource,
        req.cnName,
        (company_template_bundle or {}).get("template"),
        req.businessLicenseImageId,
    )
    msg = "business profile submitted" if result.get("success") else result.get("error", "business profile submit failed")
    return _operation_response(req, "SubmitFpBusinessProfile", result, msg)


@router.post("/fp-director-info", response_model=ApiResponse)
async def submit_fp_director_info(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    selected_company = getattr(service, "_dowsure_selected_company_cn_name", "") or req.cnName
    company_template_bundle = await asyncio.to_thread(
        _find_dowsure_company_template,
        req.username,
        selected_company,
    )
    result = await asyncio.to_thread(
        service.submit_fp_director_info_web,
        req.journey,
        req.currency,
        req.funder_resource,
        req.nameCn,
        req.addressDetail,
        (company_template_bundle or {}).get("directorTemplate"),
        req.directorIdFrontImageId,
        req.directorIdBackImageId,
    )
    msg = "director info submitted" if result.get("success") else result.get("error", "director info submit failed")
    return _operation_response(req, "SubmitFpDirectorInfo", result, msg)


@router.post("/fp-bank-info", response_model=ApiResponse)
async def submit_fp_bank_info(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_fp_bank_info_web,
        req.currency,
        req.funder_resource,
    )
    msg = "bank info submitted" if result.get("success") else result.get("error", "bank info submit failed")
    return _operation_response(req, "SubmitFpBankInfo", result, msg)


@router.post("/fp-registration-documents", response_model=ApiResponse)
async def submit_fp_registration_documents(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_fp_registration_documents_web,
        req.currency,
        req.funder_resource,
    )
    msg = "registration documents submitted" if result.get("success") else result.get("error", "registration documents submit failed")
    return _operation_response(req, "SubmitFpRegistrationDocuments", result, msg)


@router.post("/fp-add-contact-information", response_model=ApiResponse)
async def submit_fp_add_contact_information(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    selected_company = getattr(service, "_dowsure_selected_company_cn_name", "") or req.cnName
    company_template_bundle = await asyncio.to_thread(
        _find_dowsure_company_template,
        req.username,
        selected_company,
    )
    result = await asyncio.to_thread(
        service.submit_fp_add_contact_information_web,
        req.currency,
        req.funder_resource,
        req.nameCn,
        (company_template_bundle or {}).get("contactTemplate"),
    )
    msg = "contact information submitted" if result.get("success") else result.get("error", "contact information submit failed")
    return _operation_response(req, "SubmitFpAddContactInformation", result, msg)


@router.post("/fp-activate-additional-limit", response_model=ApiResponse)
async def fp_activate_additional_limit(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.activate_additional_limit_web,
        req.currency,
        req.funder_resource,
    )
    msg = "additional limit activated" if result.get("success") else result.get("error", "activate additional limit failed")
    return _operation_response(req, "ActivateAdditionalLimit", result, msg)


@router.post("/fp-submit-additional-documents", response_model=ApiResponse)
async def fp_submit_additional_documents(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_additional_documents_web,
        req.currency,
        req.funder_resource,
    )
    msg = "additional documents submitted" if result.get("success") else result.get("error", "submit additional documents failed")
    return _operation_response(req, "SubmitAdditionalDocuments", result, msg)


@router.post("/fp-submit-additional-business-info", response_model=ApiResponse)
async def fp_submit_additional_business_info(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_additional_business_info_web,
        req.currency,
        req.funder_resource,
    )
    msg = "additional business info submitted" if result.get("success") else result.get("error", "submit additional business info failed")
    return _operation_response(req, "SubmitAdditionalBusinessInfo", result, msg)


@router.post("/fp-submit-additional-director-info", response_model=ApiResponse)
async def fp_submit_additional_director_info(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_additional_director_info_web,
        req.currency,
        req.funder_resource,
    )
    msg = "additional director info submitted" if result.get("success") else result.get("error", "submit additional director info failed")
    return _operation_response(req, "SubmitAdditionalDirectorInfo", result, msg)


@router.post("/fp-re-esign", response_model=ApiResponse)
async def fp_re_esign(req: EsignRequest):
    # 800K 场景：re-approved-offer 会新落一条 dpu_credit_offer，esign 必须用
    # 最新的 lender_approved_offer_id，否则 webhook 挂到老 offer 上导致签约
    # 数据错乱。这里显式让 service 重新按 merchant_id 查一次 DB。
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.refresh_and_esign_status_web,
        signed_amount=req.signed_amount,
        status=req.status,
    )
    msg = "re-esign sent" if result.get("success") else result.get("error", "re-esign failed")
    return _operation_response(req, "ReEsign", result, msg)


@router.post("/fp-increase-esign", response_model=ApiResponse)
async def fp_increase_esign(req: EsignRequest):
    # 多店铺提额：先查最新两条 dpu_credit_offer，确认旧 offer 的 e_sign_status=SUCCESS，
    # 再使用最新 lender_approved_offer_id 发送 esign.completed。
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.increase_esign_status_web,
        signed_amount=req.signed_amount,
        status=req.status,
    )
    msg = "increase esign sent" if result.get("success") else result.get("error", "increase esign failed")
    return _operation_response(req, "IncreaseEsign", result, msg)


@router.post("/fp-activate-offer", response_model=ApiResponse)
async def fp_activate_offer(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.activate_new_offer_web,
        req.currency,
        req.funder_resource,
    )
    msg = "new offer activated" if result.get("success") else result.get("error", "activate new offer failed")
    return _operation_response(req, "ActivateNewOffer", result, msg)


@router.post("/fp-re-approved-offer", response_model=ApiResponse)
async def fp_re_approved_offer(req: ApprovedOfferRequest):
    # 800K 场景：activate-additional-limit 之后会新落一条 dpu_application 记录，
    # 需要拿最新的 application_unique_id 再跑一次 approved-offer 完成额度审批。
    # 这里显式让 service 用最新 id，而不是复用之前 select_application 绑定的值。
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.refresh_and_approved_offer_status_web,
        amount=req.amount,
        status=req.status,
        failure_reason_index=req.failure_reason_index,
        rejection_reason=req.rejection_reason,
    )
    msg = "re-approved offer sent" if result.get("success") else result.get("error", "re-approved offer failed")
    return _operation_response(req, "ReApprovedOffer", result, msg)


@router.post("/fp-increase-approved-offer", response_model=ApiResponse)
async def fp_increase_approved_offer(req: ApprovedOfferRequest):
    # 多店铺提额：先从 dpu_application 查最新两条记录，确认旧申请单为 APPROVED，
    # 再绑定最新 application_unique_id，复用 approved-offer webhook。
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.increase_approved_offer_status_web,
        amount=req.amount,
        status=req.status,
        failure_reason_index=req.failure_reason_index,
        rejection_reason=req.rejection_reason,
    )
    msg = "increase approved offer sent" if result.get("success") else result.get("error", "increase approved offer failed")
    return _operation_response(req, "IncreaseApprovedOffer", result, msg)


@router.post("/dmf-poll-application-ready", response_model=ApiResponse)
async def poll_dmf_application_ready(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.poll_dmf_application_ready_web,
        use_latest_submitted_application=req.use_latest_submitted_application,
    )
    msg = "application ready" if result.get("success") else result.get("error", "poll application ready failed")
    return _operation_response(req, "PollDmfApplicationReady", result, msg)


@router.post("/shop-performance-cny-boost", response_model=ApiResponse)
async def update_shop_performance_cny_boost(req: ShopPerformanceUpdateRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.update_shop_performance_cny_boost_web,
        req.offer_id,
        req.access_type,
        req.custom_sql,
    )
    msg = "shop performance updated" if result.get("success") else result.get("error", "shop performance update failed")
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.get("/shop-performance-cny-boost/presets", response_model=ApiResponse)
async def list_shop_performance_cny_boost_presets(username: str | None = None):
    require_admin(username)
    presets = await asyncio.to_thread(WebDPUMockService.list_shop_performance_builtin_presets_web)
    return ApiResponse(
        success=True,
        message=f"{len(presets)} builtin shop performance presets",
        data={"presets": presets},
    )


@router.post("/kiosk-seller-id-check", response_model=ApiResponse)
async def check_kiosk_seller_id(req: ShopPerformanceUpdateRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.check_kiosk_seller_id_web,
        req.offer_id,
    )
    msg = "kiosk seller_id ready" if result.get("success") else result.get("error", "kiosk seller_id check failed")
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/fp-start-reassessment", response_model=ApiResponse)
async def start_fp_reassessment(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.start_fp_reassessment_web,
        req.journey,
        req.currency,
        req.funder_resource,
    )
    msg = "reassessment started" if result.get("success") else result.get("error", "reassessment start failed")
    return _operation_response(req, "StartFpReassessment", result, msg)


@router.post("/hsbc-start-reassessment", response_model=ApiResponse)
async def start_hsbc_reassessment(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.start_fp_reassessment_web,
        req.journey,
        req.currency,
        req.funder_resource,
    )
    msg = "hsbc reassessment started" if result.get("success") else result.get("error", "hsbc reassessment start failed")
    return _operation_response(req, "StartHsbcReassessment", result, msg)


@router.post("/dowsure-start-reassessment", response_model=ApiResponse)
async def start_dowsure_reassessment(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.start_fp_reassessment_web,
        req.journey,
        req.currency,
        req.funder_resource,
    )
    msg = "dowsure reassessment started" if result.get("success") else result.get("error", "dowsure reassessment start failed")
    return _operation_response(req, "StartDowsureReassessment", result, msg)


@router.post("/fp-offer-limit-select", response_model=ApiResponse)
async def select_fp_offer_limit(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.select_fp_offer_limit_web, req.journey)
    msg = "offer limit selected" if result.get("success") else result.get("error", "offer limit select failed")
    return _operation_response(req, "SelectFpOfferLimit", result, msg)


@router.post("/fp-offer-quote-activate", response_model=ApiResponse)
async def activate_fp_offer_quote(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.activate_fp_offer_quote_web, req.journey)
    msg = "offer quote activated" if result.get("success") else result.get("error", "offer quote activate failed")
    return _operation_response(req, "ActivateFpOfferQuote", result, msg)


@router.post("/fp-link-sp-3pl-shops", response_model=ApiResponse)
async def link_fp_sp_3pl_shops(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.link_fp_sp_3pl_shops_web, req.journey)
    msg = "sp and 3pl shops linked" if result.get("success") else result.get("error", "sp and 3pl shop link failed")
    return _operation_response(req, "LinkFpSp3plShops", result, msg)


@router.post("/fp-scheduled-submit", response_model=ApiResponse)
async def run_fp_scheduled_submit(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    username = require_valid_username(req.username)
    _cleanup_scheduled_submit_jobs()
    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        "job_id": job_id,
        "status": "PENDING",
        "success": None,
        "session_id": req.session_id,
        "application_unique_id": req.application_unique_id,
        "operation_name": (req.operation_name or "RunFpScheduledSubmit").strip(),
        "journey": req.journey,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    with _scheduled_submit_jobs_lock:
        _scheduled_submit_jobs[job_id] = job

    threading.Thread(
        target=_run_scheduled_submit_job,
        args=(job_id, service, req.journey),
        name=f"fp-scheduled-submit-{job_id[:8]}",
        daemon=True,
    ).start()

    result = {
        "success": True,
        "accepted": True,
        "job_id": job_id,
        "job_status": "PENDING",
        "retry_after": 3,
    }
    response = ApiResponse(success=True, message="scheduled submit job accepted", data=result)
    try:
        audit_store.record_operation(
            username=username,
            session_data=_serialize_context(req.session_id),
            operation_name=job["operation_name"],
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=True,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to record scheduled submit job audit")
    return response


@router.get("/fp-scheduled-submit/jobs/{job_id}", response_model=ApiResponse)
async def get_fp_scheduled_submit_job(job_id: str, username: str | None = None):
    if username is not None:
        require_valid_username(username)
    job = _get_scheduled_submit_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="scheduled submit job not found or expired")

    result = {
        "success": job.get("status") == "SUCCESS",
        "job_id": job_id,
        "job_status": job.get("status"),
        "retry_after": 3 if job.get("status") in {"PENDING", "RUNNING"} else None,
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "result": job.get("result"),
        "error": job.get("error"),
    }
    if job.get("status") in {"PENDING", "RUNNING"}:
        return ApiResponse(success=True, message="scheduled submit job running", data=result)

    final_result = job.get("result") or {}
    result.update({
        "success": bool(final_result.get("success")),
        "application_unique_id": final_result.get("application_unique_id"),
        "limit_application_unique_id": final_result.get("limit_application_unique_id"),
        "application_status": final_result.get("application_status"),
    })
    message = "scheduled submit job completed" if result["success"] else (result.get("error") or "scheduled submit job failed")
    return ApiResponse(success=True, message=message, data=result)


# 13. 缁崵绮烘禍瀣╂闁氨鐓?
@router.post("/system-event", response_model=ApiResponse)
async def mock_system_event(req: SystemEventRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_system_event_notification,
        event_type=req.event_type,
        application_unique_id=req.application_unique_id,
        error_code=req.error_code
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/boss-application-status", response_model=ApiResponse)
async def mock_boss_application_status(req: BossApplicationStatusRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.handle_boss_application_status_web,
        approved_date=req.approved_date,
        approved_limit=req.approved_limit,
        interest_type=req.interest_type,
        rate=req.rate,
        tenor=req.tenor,
        application_status=req.application_status,
        update_by=req.update_by,
        psp_status=req.psp_status,
        psp_aggregate_status=req.psp_aggregate_status,
        currency=req.currency,
        funder_resource=req.funder_resource,
        event_type=req.event_type,
        application_unique_id=req.application_unique_id,
    )
    msg = "boss application status handled" if result.get("success") else result.get("error", "boss application status failed")
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.get("/dowsure-merchant-accounts", response_model=ApiResponse)
async def list_dowsure_merchant_accounts(session_id: str):
    ctx = _get_context(session_id)
    session_manager._get_application_rows(ctx, force=True)
    session_manager._refresh_application_snapshot(ctx)
    service = ctx.service
    result = await asyncio.to_thread(service.get_dowsure_merchant_accounts)
    return ApiResponse(
        success=result.get("success", False),
        message="DOWSURE merchant accounts loaded" if result.get("success") else result.get("error", "DOWSURE merchant accounts load failed"),
        data=result,
    )


@router.get("/application-codes", response_model=ApiResponse)
async def list_application_codes(session_id: str):
    service = _get_service(session_id)
    result = await asyncio.to_thread(service.get_application_code_options)
    return ApiResponse(
        success=result.get("success", False),
        message="application codes loaded" if result.get("success") else result.get("error", "application codes load failed"),
        data=result,
    )


@router.get("/psp-authorization-rows", response_model=ApiResponse)
async def list_psp_authorization_rows(session_id: str):
    service = _get_service(session_id)
    result = await asyncio.to_thread(service.get_psp_authorization_rows)
    return ApiResponse(
        success=result.get("success", False),
        message="PSP authorization rows loaded" if result.get("success") else result.get("error", "PSP authorization rows load failed"),
        data=result,
    )


@router.get("/limit-applications", response_model=ApiResponse)
async def list_limit_applications(session_id: str):
    try:
        result = await asyncio.to_thread(session_manager.get_limit_application_rows, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found or expired") from exc
    return ApiResponse(
        success=result.get("success", False),
        message="limit applications loaded" if result.get("success") else result.get("error", "limit applications load failed"),
        data=result,
    )


@router.get("/drawdown-repayment-rows", response_model=ApiResponse)
async def list_drawdown_repayment_rows(session_id: str):
    try:
        result = await asyncio.to_thread(session_manager.get_drawdown_repayment_rows, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found or expired") from exc
    return ApiResponse(
        success=result.get("success", False),
        message="drawdown repayment rows loaded" if result.get("success") else result.get("error", "drawdown repayment rows load failed"),
        data=result,
    )


@router.post("/dowsure-credit-result", response_model=ApiResponse)
async def send_dowsure_credit_result(req: DowsureCreditResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_dowsure_credit_result_web,
        application_code=req.applicationCode,
        amount=req.amount,
        processing_fee=req.processingFee,
        credit_result_list=[item.model_dump() for item in req.creditResultList],
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.get("/webank-seller-offers", response_model=ApiResponse)
async def list_webank_seller_offers(session_id: str):
    service = _get_service(session_id)
    result = await asyncio.to_thread(service.get_webank_seller_offers)
    return ApiResponse(
        success=result.get("success", False),
        message="WEBANK seller offers loaded" if result.get("success") else result.get("error", "WEBANK seller offers load failed"),
        data=result,
    )


@router.post("/webank-credit-result", response_model=ApiResponse)
async def send_webank_credit_result(req: WebankCreditResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_webank_credit_result_web,
        application_code=req.application_code,
        business_sum=req.businessSum,
        seller_offers=[item.model_dump() for item in req.seller_offers],
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/cgb-credit-result", response_model=ApiResponse)
async def send_cgb_credit_result(req: CgbCreditResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_cgb_credit_result_web,
        amount=req.amount,
        processing_fee=req.processingFee,
        credit_status=req.creditStatus,
        application_code=req.application_code,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/cgb-loan-result", response_model=ApiResponse)
async def send_cgb_loan_result(req: CgbLoanResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_cgb_loan_result_web,
        amount=req.amount,
        processing_fee=req.processingFee,
        application_code=req.application_code,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/cgb-repayment-result", response_model=ApiResponse)
async def send_cgb_repayment_result(req: CgbRepaymentResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_cgb_repayment_result_web,
        application_code=req.application_code,
        loan_code=req.loan_code,
        payment_principal=req.payment_principal,
        payment_interest=req.payment_interest,
        payment_overdue_interest=req.payment_overdue_interest,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/webank-drawdown-result", response_model=ApiResponse)
async def send_webank_drawdown_result(req: WebankDrawdownResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_webank_drawdown_result_web,
        loan_amount=req.loan_amount,
        service_fee_amount=req.service_fee_amount,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/webank-repayment-result", response_model=ApiResponse)
async def send_webank_repayment_result(req: WebankRepaymentResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_webank_repayment_result_web,
        loan_code=req.loan_code,
        payment_principal=req.payment_principal,
        payment_interest=req.payment_interest,
        payment_penalty_interest=req.payment_penalty_interest,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-esign-drawdown-result", response_model=ApiResponse)
async def send_dowsure_esign_drawdown_result(req: DowsureEsignDrawdownResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_dowsure_esign_drawdown_result_web,
        application_code=req.application_code,
        credit_contract_no=req.credit_contract_no,
        amount=req.amount,
        processing_fee=req.processing_fee,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-repayment-result", response_model=ApiResponse)
async def send_dowsure_repayment_result(req: DowsureRepaymentResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_dowsure_repayment_result_web,
        application_code=req.application_code,
        loan_code=req.loan_code,
        payment_principal=req.payment_principal,
        payment_overdue_interest=req.payment_overdue_interest,
        payment_interest=req.payment_interest,
        deal_amount=req.deal_amount,
        surplus_principal=req.surplus_principal,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-retry-callback", response_model=ApiResponse)
async def retry_dowsure_callback(req: DowsureRetryCallbackRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.retry_dowsure_callback_web)
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 16. Abandon(application.status)
@router.post("/application-abandon", response_model=ApiResponse)
async def mock_application_abandon(req: ApplicationAbandonRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_application_abandon_status,
        abandon_reason=req.abandon_reason,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 14. PSP 瀵偓婵绱橦SBC閿?
@router.post("/psp-hsbc-start", response_model=ApiResponse)
async def mock_psp_hsbc_start(req: PspHsbcStartRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_start_status_hsbc,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 15. PSP 鐎瑰本鍨氶敍鍦歋BC閿?
@router.post("/psp-hsbc-completed", response_model=ApiResponse)
async def mock_psp_hsbc_completed(req: PspHsbcCompletedRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_completed_status_hsbc,
        result=req.result,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/psp-hsbc-complete-all", response_model=ApiResponse)
async def mock_psp_hsbc_complete_all(req: PspHsbcCompleteAllRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.complete_all_hsbc_psp_bindings_web,
        result=req.result,
        max_iterations=req.max_iterations,
    )
    msg = "all HSBC PSP bindings completed" if result.get("success") else result.get("error", "HSBC PSP binding failed")
    return _operation_response(req, req.__class__.__name__, result, msg)
