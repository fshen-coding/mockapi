# -*- coding: utf-8 -*-
"""Pydantic request models."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., pattern=r"^\d{8}$|^\d{11}$")
    username: Optional[str] = None


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=200)


class ContactIssueCreateRequest(BaseModel):
    created_by: Optional[str] = None
    issue: str = Field(..., min_length=1)
    env: Optional[str] = None
    phone_number: Optional[str] = None
    session_id: Optional[str] = None
    merchant_id: Optional[str] = None


class ContactIssueReplyRequest(BaseModel):
    reply: str = Field(..., min_length=1)
    replied_by: Optional[str] = None


class RegisterRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    journey: Literal["200K", "500K", "2000K"] = "500K"
    currency: Literal["CNY", "USD"] = "USD"
    offline: bool = False
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    username: Optional[str] = None
    operation_name: Optional[str] = None


class RegisterAndRunMultiShopRequest(RegisterRequest):
    sp_status: Literal["SUCCESS", "FAIL"] = "SUCCESS"


# ---------------------------------------------------------------------------
# Step-by-step registration (scenario tree) — stateless: each step takes the
# pieces it needs from the previous step's response. See register_routes.py for
# the corresponding endpoints. The old `/api/register-and-run-multishop` is
# untouched and still used by the dashboard's one-click button.
# ---------------------------------------------------------------------------


class RegisterSendSmsRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    journey: Literal["200K", "500K", "2000K"] = "500K"
    currency: Literal["CNY", "USD"] = "USD"
    offline: bool = False
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    offer_id: Optional[str] = ""
    username: Optional[str] = None


class RegisterCreateOfferRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    journey: Literal["200K", "500K", "2000K"] = "500K"
    currency: Literal["CNY", "USD"] = "USD"
    username: Optional[str] = None


class RegisterAmazonRedirectRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    offer_id: str = Field(..., min_length=1)
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    username: Optional[str] = None


class RegisterValidateSmsRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    offer_id: Optional[str] = ""
    username: Optional[str] = None


class RegisterSignupRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    email: str = Field(..., min_length=1, max_length=120)
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    journey: Literal["200K", "500K", "2000K"] = "500K"
    offline: bool = False
    offer_id: Optional[str] = ""
    verification_code: str = Field(..., min_length=1, max_length=20)
    username: Optional[str] = None


class RegisterSpAuthUrlRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    token: str = Field(..., min_length=1)
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    offline: bool = False
    username: Optional[str] = None


class RegisterSpAuthCallbackRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    token: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    selling_partner_id: str = Field(..., min_length=1)
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    username: Optional[str] = None


class RegisterSpUpdateOfferRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    selling_partner_id: str = Field(..., min_length=1)
    sp_status: Literal["SUCCESS", "FAIL"] = "SUCCESS"
    # 1=lender country mismatch, 2=existing credit approval,
    # 3=offer exists for partner combo, 4=others. Only used when sp_status=FAIL.
    failure_reason_index: Optional[Literal[1, 2, 3, 4]] = None
    username: Optional[str] = None


class Register3plLinkWaitRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    selling_partner_id: str = Field(..., min_length=1)
    offline: bool = True
    username: Optional[str] = None


class Register3plRedirectRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., min_length=8, max_length=20)
    username: Optional[str] = None


class MockBaseRequest(BaseModel):
    session_id: str
    application_unique_id: Optional[str] = None
    username: Optional[str] = None
    operation_name: Optional[str] = None


class UpstreamDebugRequest(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    url: str = Field(..., min_length=1, max_length=2048)
    headers: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    timeout_seconds: int = Field(60, ge=1, le=600)
    username: Optional[str] = None
    operation_name: Optional[str] = None


class LinkSp3plRequest(MockBaseRequest):
    pass


class UnderwrittenRequest(MockBaseRequest):
    amount: int = Field(..., gt=0)
    status: Literal["APPROVED", "REJECTED"]
    limit_application_unique_id: Optional[str] = None
    use_latest_submitted_limit_application: bool = False


class DowsureMerchantAccountLimit(BaseModel):
    merchantAccountId: str = Field(..., min_length=1)
    merchantAccountLimit: Optional[float] = Field(None, ge=0)


class UnderwrittenDowsureRequest(MockBaseRequest):
    status: Literal["APPROVED", "REJECTED"]
    merchant_accounts: list[DowsureMerchantAccountLimit] = Field(default_factory=list)


class DowsureCreditResultRequest(MockBaseRequest):
    application_code: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    credit_status: Literal["APPROVE", "REJECT"] = "APPROVE"


class DowsureEsignDrawdownResultRequest(MockBaseRequest):
    application_code: Optional[str] = None
    credit_contract_no: Optional[str] = None
    amount: float = Field(..., gt=0)
    processing_fee: float = Field(..., ge=0)


class DowsureRepaymentResultRequest(MockBaseRequest):
    application_code: Optional[str] = None
    loan_code: Optional[str] = None
    payment_principal: float = Field(..., ge=0)
    payment_interest: Optional[float] = Field(None, ge=0)
    payment_overdue_interest: float = Field(..., ge=0)
    deal_amount: Optional[float] = Field(None, ge=0)
    surplus_principal: Optional[float] = Field(None, ge=0)


class DowsureRetryCallbackRequest(MockBaseRequest):
    pass


class ApprovedOfferRequest(MockBaseRequest):
    amount: int = Field(..., gt=0)
    status: Literal["APPROVED", "RETURNED", "REJECTED"]
    rejection_reason: Optional[Literal["fraud", "others"]] = None
    failure_reason_index: Optional[int] = Field(None, ge=1, le=7)


class PspStartRequest(MockBaseRequest):
    status: Literal["PROCESSING", "FAIL", "INITIAL"]
    merchant_account_id: Optional[str] = None


class PspCompletedRequest(MockBaseRequest):
    status: Literal["SUCCESS", "FAIL", "INITIAL"]
    merchant_account_id: Optional[str] = None


class StartReassessmentRequest(MockBaseRequest):
    business_context: Literal["REASSESSMENT"] = "REASSESSMENT"
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"


class EsignRequest(MockBaseRequest):
    signed_amount: int = Field(..., gt=0)
    status: Literal["SUCCESS", "FAIL"]


class DrawdownRequest(MockBaseRequest):
    amount: float = Field(..., gt=0)
    status: Literal["APPROVED", "REJECTED"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=5)


class RepaymentStartRequest(MockBaseRequest):
    principal_amount: float = Field(..., gt=0)
    outstanding_amount: Optional[float] = Field(None, ge=0)
    loan_code: Optional[str] = None


class RepaymentRequest(MockBaseRequest):
    principal_amount: float = Field(..., gt=0)
    outstanding_amount: Optional[float] = Field(None, ge=0)
    status: Literal["Success", "Failure"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=2)
    loan_code: Optional[str] = None


class MultiShopBindingRequest(MockBaseRequest):
    state: str = Field(..., min_length=1)


class SpStatusUpdateRequest(MockBaseRequest):
    platform_seller_id: Optional[str] = None
    status: Literal["SUCCESS", "FAIL"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=4)


class MultiShop3plRedirectRequest(MockBaseRequest):
    pass


class CreateApplicationContextRequest(MockBaseRequest):
    journey: Optional[Literal["200K", "500K", "2000K"]] = None
    currency: Optional[Literal["CNY", "USD"]] = None
    funder_resource: Optional[Literal["FUNDPARK", "HSBC", "DOWSURE"]] = None
    tier_code: Optional[int] = Field(None, ge=1)
    offer_id: Optional[str] = None


class FpApplicationStepRequest(MockBaseRequest):
    journey: Optional[Literal["200K", "500K", "2000K"]] = None
    currency: Optional[Literal["CNY", "USD"]] = None
    funder_resource: Optional[Literal["FUNDPARK", "HSBC", "DOWSURE"]] = None
    nameCn: Optional[str] = None
    addressDetail: Optional[str] = None
    use_latest_submitted_application: bool = False


class ShopPerformanceUpdateRequest(MockBaseRequest):
    offer_id: Optional[str] = None


class SystemEventRequest(MockBaseRequest):
    event_type: Literal[
        "EXCEPTION-APPLICATION-CREATION",
        "INDICATIVE-OFFER",
        "IN-PROCESS",
        "ERROR",
        "ETB-customer",
    ]
    application_unique_id: Optional[str] = None
    error_code: Optional[Literal["B-6003", "B-6005"]] = None


class BossApplicationStatusRequest(MockBaseRequest):
    approved_date: str = "2026-06-01"
    approved_limit: str = "10000.00"
    interest_type: str = "Float"
    rate: str = "3.0"
    tenor: int = 120
    application_status: str = "APPROVED"
    update_by: str = "boss"
    psp_status: str = "Init"
    psp_aggregate_status: str = "NORMAL"
    currency: Literal["CNY", "USD"] = "USD"
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "HSBC"
    event_type: str = "NTB-customer"


class ApplicationAbandonRequest(MockBaseRequest):
    abandon_reason: Literal[
        "SellerCancelled",
        "OfferExpired",
        "ApplicationInfoNotSubmitted",
        "LenderOfferNotReturned",
    ]


class PspHsbcStartRequest(MockBaseRequest):
    merchant_account_id: Optional[str] = None


class PspHsbcCompletedRequest(MockBaseRequest):
    result: Literal["SUCCESS", "FAIL"]
    merchant_account_id: Optional[str] = None


class PspHsbcCompleteAllRequest(MockBaseRequest):
    result: Literal["SUCCESS", "FAIL"] = "SUCCESS"
    max_iterations: int = Field(20, ge=1, le=100)


class AiChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str


class AiChatContext(BaseModel):
    active_session_id: Optional[str] = None
    session: Optional[dict] = None
    selected_env: Optional[str] = None
    selected_register_env: Optional[str] = None
    selected_currency: Optional[str] = None
    preferred_currency: Optional[str] = None
    selected_journey: Optional[str] = None
    recent_logs: list[dict] = Field(default_factory=list)
    recent_activities: list[dict] = Field(default_factory=list)


class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[AiChatMessage] = Field(default_factory=list)
    context: AiChatContext = Field(default_factory=AiChatContext)
    model: Optional[str] = None
    reasoning_effort: Optional[Literal["low", "medium", "high", "extreme"]] = None


class PromptTemplateCreateRequest(BaseModel):
    username: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    logic_type: Literal["sql", "http", "python"] = "sql"
    logic: str = Field(..., min_length=1)
    example_prompt: str = Field(default="", max_length=2000)
    is_disabled: bool = False
    locked_env: Optional[str] = Field(default=None, max_length=32)


class PromptTemplateUpdateRequest(BaseModel):
    username: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    logic_type: Optional[Literal["sql", "http", "python"]] = None
    logic: Optional[str] = Field(None, min_length=1)
    example_prompt: Optional[str] = Field(None, max_length=2000)
    is_disabled: Optional[bool] = None
    locked_env: Optional[str] = Field(None, max_length=32)


class PromptTemplateToggleRequest(BaseModel):
    username: str = Field(..., min_length=1)
    is_disabled: bool


class PromptTemplateDeleteRequest(BaseModel):
    username: str = Field(..., min_length=1)


class PromptTemplateExecuteRequest(BaseModel):
    username: str = Field(..., min_length=1)
    user_input: str = Field(..., min_length=1)
    env: Optional[str] = None
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Admin: user management
# ---------------------------------------------------------------------------

class AdminUserUpdateRequest(BaseModel):
    """Admin-only: rename account, reset password, edit notes."""
    admin_username: str = Field(..., min_length=1)
    new_username: Optional[str] = Field(None, min_length=1, max_length=80)
    new_password: Optional[str] = Field(None, min_length=1, max_length=200)
    notes: Optional[str] = Field(None, max_length=1000)


class AdminUserDeleteRequest(BaseModel):
    admin_username: str = Field(..., min_length=1)


class AdminUserReviewRequest(BaseModel):
    """Admin-only: approve or reject a pending registration."""
    admin_username: str = Field(..., min_length=1)
    note: Optional[str] = Field(None, max_length=500)
