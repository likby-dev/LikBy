"""
likby.api.payments
FastAPI router for subscription management, Razorpay web checkout, and webhook ingestion.
"""

from datetime import datetime
import hmac
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from likby.config import get_settings
from likby.domain.entities.user import User
from likby.domain.enums import FeatureKey, PaymentProviderType, SubscriptionTier
from likby.repositories.interfaces import (
    PaymentOrderRepository,
    PaymentTransactionRepository,
    SubscriptionPlanRepository,
    UserRepository,
)
from likby.services.payment_service import PaymentService
from likby.services.subscription_service import SubscriptionService
from likby.services.usage_service import UsageService

router = APIRouter(prefix="/api/v1", tags=["Payments & Subscriptions"])


# ============================================================================
# Request / Response Schemas
# ============================================================================

class CreateOrderRequest(BaseModel):
    plan_code: str = Field(..., description="Target tier: SPARK, PREMIUM, or DIAMOND")


class CreateOrderResponse(BaseModel):
    order_id: str
    razorpay_order_id: str
    amount: int
    currency: str
    plan_code: str
    key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    status: str
    tier: str
    expires_at: Optional[datetime]
    message: str


class PlanItemResponse(BaseModel):
    code: str
    display_name: str
    duration_days: Optional[int]
    prices: Dict[str, Any]
    limits: Dict[str, Any]


class MySubscriptionResponse(BaseModel):
    user_id: str
    tier: str
    tier_name: str
    status: str
    starts_at: Optional[datetime]
    expires_at: Optional[datetime]
    limits: Dict[str, Any]
    usage_today: Dict[str, int]


class PaymentHistoryItem(BaseModel):
    id: str
    provider: str
    amount: int
    currency: str
    status: str
    captured_at: Optional[datetime]
    created_at: datetime


# ============================================================================
# Authentication Dependency
# ============================================================================

async def get_authenticated_user(
    request: Request,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    """
    Derive the authenticated user from a verified identity.
    Accepts X-User-Id header or Bearer token (internal user ID).
    """
    user_id = x_user_id
    if not user_id and authorization and authorization.startswith("Bearer "):
        user_id = authorization.replace("Bearer ", "").strip()

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide X-User-Id or Authorization header.",
        )

    user_repo: UserRepository = request.app.state.user_repo
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user identity not found or inactive.",
        )
    return user


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/subscriptions/plans", response_model=List[PlanItemResponse])
async def get_subscription_plans(request: Request) -> List[PlanItemResponse]:
    """Retrieve the authoritative catalog of subscription plans and their limits."""
    plan_repo: SubscriptionPlanRepository = request.app.state.plan_repo
    plans = await plan_repo.list_active_plans()

    catalog = []
    for plan in plans:
        prices = await plan_repo.get_prices_for_plan(plan.id)
        prices_dict = {
            p.provider.value: {
                "amount": p.amount_minor_units,
                "currency": p.currency,
                "duration_seconds": p.duration_seconds,
            }
            for p in prices
        }
        config = getattr(plan, "entitlements_json", None) or getattr(plan, "entitlement_config", None) or {}
        plan_code_str = plan.code.value if hasattr(plan.code, "value") else str(plan.code)
        catalog.append(
            PlanItemResponse(
                code=plan_code_str,
                display_name=plan.display_name,
                duration_days=config.get("duration_days"),
                prices=prices_dict,
                limits=config.get("limits", {}),
            )
        )
    return catalog


@router.get("/subscriptions/me", response_model=MySubscriptionResponse)
async def get_my_subscription(
    request: Request,
    user: User = Depends(get_authenticated_user),
) -> MySubscriptionResponse:
    """Retrieve the authenticated user's current subscription tier, expiry, limits, and today's usage."""
    sub_service: SubscriptionService = request.app.state.subscription_service
    usage_service: UsageService = request.app.state.usage_service

    entitlement = await sub_service.get_user_entitlement(user.id)
    tier_spec = sub_service.get_tier_spec(entitlement.tier)

    # Gather usage today
    usage_keys = [
        FeatureKey.LIKES,
        FeatureKey.SEARCHES,
        FeatureKey.REQUESTS,
        FeatureKey.GAMES,
    ]
    usage_today = {}
    for key in usage_keys:
        used = await usage_service.get_used_count(user.id, key)
        usage_today[key.value] = used

    return MySubscriptionResponse(
        user_id=user.id,
        tier=entitlement.tier.value,
        tier_name=tier_spec["name"],
        status=entitlement.status.value,
        starts_at=entitlement.starts_at,
        expires_at=entitlement.expires_at,
        limits=tier_spec["limits"],
        usage_today=usage_today,
    )


@router.post("/payments/razorpay/orders", response_model=CreateOrderResponse)
async def create_razorpay_order(
    payload: CreateOrderRequest,
    request: Request,
    user: User = Depends(get_authenticated_user),
) -> CreateOrderResponse:
    """
    Create a server-authoritative Razorpay payment order for an eligible web checkout.
    Price and duration are derived strictly from the server catalog.
    """
    code_upper = payload.plan_code.strip().upper()
    try:
        tier = SubscriptionTier[code_upper]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription plan '{payload.plan_code}'. Must be SPARK, PREMIUM, or DIAMOND.",
        )

    if tier == SubscriptionTier.BASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LikBy Base is free and does not require a purchase order.",
        )

    payment_service: PaymentService = request.app.state.payment_service
    order = await payment_service.create_web_razorpay_order(user.id, tier)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate payment order with provider.",
        )

    settings = get_settings()
    key_id = settings.razorpay_key_id.get_secret_value() if settings.razorpay_key_id else ""

    return CreateOrderResponse(
        order_id=order.id,
        razorpay_order_id=order.provider_order_id or "",
        amount=order.amount_minor_units,
        currency=order.currency,
        plan_code=tier.value,
        key_id=key_id,
    )


@router.post("/payments/razorpay/verify", response_model=VerifyPaymentResponse)
async def verify_razorpay_payment(
    payload: VerifyPaymentRequest,
    request: Request,
    user: User = Depends(get_authenticated_user),
) -> VerifyPaymentResponse:
    """
    Verify the client-returned Razorpay payment details and signature server-side.
    Activates the paid entitlement atomically once verified.
    """
    payment_service: PaymentService = request.app.state.payment_service
    entitlement = await payment_service.verify_and_activate_razorpay_payment(
        internal_user_id=user.id,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )

    if not entitlement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment verification failed. Invalid signature, mismatched order, or uncaptured payment.",
        )

    return VerifyPaymentResponse(
        status="success",
        tier=entitlement.tier.value,
        expires_at=entitlement.expires_at,
        message=f"Subscription successfully activated: {entitlement.tier.value}!",
    )


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
) -> Response:
    """
    Authoritative Razorpay webhook listener.
    Validates HMAC-SHA256 signature from raw body and idempotently handles payment events.
    """
    raw_body = await request.body()
    payment_service: PaymentService = request.app.state.payment_service

    result = await payment_service.handle_razorpay_webhook(
        raw_body=raw_body,
        signature_header=x_razorpay_signature,
    )

    if result.get("status") == "invalid_signature":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        )

    return Response(
        content='{"status": "received"}',
        media_type="application/json",
        status_code=status.HTTP_200_OK,
    )


@router.get("/payments/history", response_model=List[PaymentHistoryItem])
async def get_payment_history(
    request: Request,
    user: User = Depends(get_authenticated_user),
) -> List[PaymentHistoryItem]:
    """Retrieve transaction history for the authenticated user."""
    txn_repo: PaymentTransactionRepository = request.app.state.txn_repo
    transactions = await txn_repo.list_by_user(user.id)

    return [
        PaymentHistoryItem(
            id=tx.id,
            provider=tx.provider.value,
            amount=tx.amount_minor_units,
            currency=tx.currency,
            status=tx.payment_status.value,
            captured_at=tx.captured_at,
            created_at=tx.created_at,
        )
        for tx in transactions
    ]
