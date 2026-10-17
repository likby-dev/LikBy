"""
tests/unit/test_payment_verification.py
Unit tests for Razorpay HMAC-SHA256 signature verification, tamper resistance, idempotency, webhook deduplication, and Telegram Stars checkout.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import pytest
from pydantic import SecretStr

from likby.domain.entities.payment import PaymentOrder
from likby.domain.entities.user import User
from likby.domain.enums import (
    EntitlementSource,
    EntitlementStatus,
    PaymentOrderStatus,
    PaymentProviderType,
    PaymentTransactionStatus,
    SubscriptionTier,
)
from likby.repositories.sqlite.database import init_sqlite_db
from likby.repositories.sqlite.audit_event_repository import SqliteAuditEventRepository
from likby.repositories.sqlite.payment_order_repository import SqlitePaymentOrderRepository
from likby.repositories.sqlite.payment_transaction_repository import SqlitePaymentTransactionRepository
from likby.repositories.sqlite.subscription_plan_repository import SqliteSubscriptionPlanRepository
from likby.repositories.sqlite.subscription_repository import SqliteSubscriptionRepository
from likby.repositories.sqlite.user_repository import SqliteUserRepository
from likby.repositories.sqlite.webhook_ledger_repository import SqliteWebhookLedgerRepository
from likby.services.audit_service import AuditService
from likby.services.payment_provider import RazorpayPaymentProvider, TelegramStarsPaymentProvider
from likby.services.payment_service import PaymentService
from likby.services.subscription_service import SubscriptionService


@pytest.fixture
def mock_keys():
    return {
        "key_id": "rzp_test_mockKeyId123",
        "key_secret": SecretStr("super_secret_key_12345"),
        "webhook_secret": SecretStr("webhook_secret_67890"),
    }


def compute_razorpay_signature(order_id: str, payment_id: str, secret: str) -> str:
    message = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_razorpay_valid_signature_verification(mock_keys):
    """Verify HMAC-SHA256 signature calculation and verification."""
    provider = RazorpayPaymentProvider(
        key_id=mock_keys["key_id"],
        key_secret=mock_keys["key_secret"],
        webhook_secret=mock_keys["webhook_secret"],
    )

    order_id = "order_DBJOWzybf0sJbb"
    payment_id = "pay_29QQoUBi66xm2f"
    valid_sig = compute_razorpay_signature(order_id, payment_id, mock_keys["key_secret"].get_secret_value())

    # 1. Valid signature succeeds
    is_valid = await provider.verify_payment(
        provider_order_id=order_id,
        provider_payment_id=payment_id,
        provider_signature=valid_sig,
    )
    assert is_valid is True

    # 2. Tampered signature fails
    tampered_sig = valid_sig[:-4] + "ffff"
    is_invalid = await provider.verify_payment(
        provider_order_id=order_id,
        provider_payment_id=payment_id,
        provider_signature=tampered_sig,
    )
    assert is_invalid is False

    # 3. Altered order ID fails
    is_order_altered = await provider.verify_payment(
        provider_order_id="order_ALTERED000000",
        provider_payment_id=payment_id,
        provider_signature=valid_sig,
    )
    assert is_order_altered is False

    # 4. Altered payment ID fails
    is_payment_altered = await provider.verify_payment(
        provider_order_id=order_id,
        provider_payment_id="pay_ALTERED000000",
        provider_signature=valid_sig,
    )
    assert is_payment_altered is False


@pytest.mark.asyncio
async def test_payment_service_authoritative_activation_and_idempotency(mock_keys):
    """
    Test end-to-end payment verification:
    - Verifies order details from DB.
    - Captures payment and updates order to PAID.
    - Activates entitlement with correct tier.
    - Re-submitting the exact same payment is idempotent and does not create duplicate activations.
    """
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    order_repo = SqlitePaymentOrderRepository(conn)
    txn_repo = SqlitePaymentTransactionRepository(conn)
    plan_repo = SqliteSubscriptionPlanRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    webhook_repo = SqliteWebhookLedgerRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    audit_service = AuditService(audit_repo)

    # Seed test users
    await user_repo.save(User(id="usr_buyer_1", telegram_id=88111))
    await user_repo.save(User(id="usr_attacker_999", telegram_id=88999))

    razorpay_provider = RazorpayPaymentProvider(
        key_id=mock_keys["key_id"],
        key_secret=mock_keys["key_secret"],
        webhook_secret=mock_keys["webhook_secret"],
    )

    payment_service = PaymentService(
        order_repo=order_repo,
        transaction_repo=txn_repo,
        plan_repo=plan_repo,
        webhook_ledger=webhook_repo,
        subscription_service=sub_service,
        audit_service=audit_service,
        razorpay_provider=razorpay_provider,
        telegram_stars_provider=None,
    )

    # 1. Create a server-authoritative order for LikBy Premium (₹79)
    plans = await plan_repo.list_active_plans()
    prem_plan = next(p for p in plans if p.code == SubscriptionTier.PREMIUM)

    order = PaymentOrder(
        id="ord_test_001",
        internal_order_id="ord_test_001",
        user_id="usr_buyer_1",
        plan_id=prem_plan.id,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id="order_rzp_mock_111",
        amount_minor_units=7900,
        currency="INR",
        status=PaymentOrderStatus.CREATED,
    )
    await order_repo.save(order)

    payment_id = "pay_rzp_mock_222"
    valid_sig = compute_razorpay_signature(order.provider_order_id, payment_id, mock_keys["key_secret"].get_secret_value())

    # 2. Wrong user attempts verification -> Must be rejected
    mismatch_ent = await payment_service.verify_and_activate_razorpay_payment(
        internal_user_id="usr_attacker_999",
        razorpay_order_id=order.provider_order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=valid_sig,
    )
    assert mismatch_ent is None

    # 3. Legitimate user verifies payment -> Must succeed and activate
    ent = await payment_service.verify_and_activate_razorpay_payment(
        internal_user_id="usr_buyer_1",
        razorpay_order_id=order.provider_order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=valid_sig,
    )
    assert ent is not None
    assert ent.tier == SubscriptionTier.PREMIUM
    assert ent.is_active is True

    # Check order was transitioned to PAID
    refreshed_order = await order_repo.get_by_id(order.id)
    assert refreshed_order.status == PaymentOrderStatus.PAID

    # 4. Duplicate verification call -> Idempotent, returns existing entitlement
    dup_ent = await payment_service.verify_and_activate_razorpay_payment(
        internal_user_id="usr_buyer_1",
        razorpay_order_id=order.provider_order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=valid_sig,
    )
    assert dup_ent is not None
    assert dup_ent.user_id == ent.user_id

    # Check only 1 transaction recorded in DB for this order
    recorded_txns = await txn_repo.get_by_order_id(order.id)
    assert len(recorded_txns) == 1
    assert recorded_txns[0].provider_payment_id == payment_id

    await conn.close()


@pytest.mark.asyncio
async def test_razorpay_webhook_signature_and_idempotency(mock_keys):
    """Verify webhook HMAC signature verification and deduplication ledger."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    order_repo = SqlitePaymentOrderRepository(conn)
    txn_repo = SqlitePaymentTransactionRepository(conn)
    plan_repo = SqliteSubscriptionPlanRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    webhook_repo = SqliteWebhookLedgerRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    audit_service = AuditService(audit_repo)

    # Seed test user
    await user_repo.save(User(id="usr_hook_target", telegram_id=88222))

    razorpay_provider = RazorpayPaymentProvider(
        key_id=mock_keys["key_id"],
        key_secret=mock_keys["key_secret"],
        webhook_secret=mock_keys["webhook_secret"],
    )

    payment_service = PaymentService(
        order_repo=order_repo,
        transaction_repo=txn_repo,
        plan_repo=plan_repo,
        webhook_ledger=webhook_repo,
        subscription_service=sub_service,
        audit_service=audit_service,
        razorpay_provider=razorpay_provider,
        telegram_stars_provider=None,
    )

    # 1. Prepare raw webhook payload
    webhook_data = {
        "event": "payment.captured",
        "entity": "event",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_hook_987",
                    "order_id": "order_hook_123",
                    "status": "captured",
                    "amount": 1900,
                    "currency": "INR",
                }
            }
        },
    }
    raw_body = json.dumps(webhook_data).encode("utf-8")

    # Compute valid webhook signature
    valid_hook_sig = hmac.new(
        mock_keys["webhook_secret"].get_secret_value().encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    # 2. Invalid webhook signature rejected
    res_bad = await payment_service.handle_razorpay_webhook(
        raw_body=raw_body,
        signature_header="invalid_hex_signature",
    )
    assert res_bad["status"] == "invalid_signature"

    # 3. Create matching order in DB
    plans = await plan_repo.list_active_plans()
    spark_plan = next(p for p in plans if p.code == SubscriptionTier.SPARK)
    order = PaymentOrder(
        id="ord_hook_001",
        internal_order_id="ord_hook_001",
        user_id="usr_hook_target",
        plan_id=spark_plan.id,
        provider=PaymentProviderType.RAZORPAY,
        provider_order_id="order_hook_123",
        amount_minor_units=1900,
        currency="INR",
        status=PaymentOrderStatus.CREATED,
    )
    await order_repo.save(order)

    # 4. Valid webhook accepted and processed
    res_ok = await payment_service.handle_razorpay_webhook(
        raw_body=raw_body,
        signature_header=valid_hook_sig,
    )
    assert res_ok["status"] == "processed"

    # Verify user now has active Spark entitlement
    ent = await sub_service.get_user_entitlement("usr_hook_target")
    assert ent.tier == SubscriptionTier.SPARK

    # 5. Duplicate webhook -> Idempotently recognized
    res_dup = await payment_service.handle_razorpay_webhook(
        raw_body=raw_body,
        signature_header=valid_hook_sig,
    )
    assert res_dup["status"] == "duplicate_ignored"

    await conn.close()


@pytest.mark.asyncio
async def test_telegram_stars_checkout_and_settlement():
    """Verify Telegram Stars invoice creation and successful payment activation."""
    conn = await init_sqlite_db(":memory:")
    user_repo = SqliteUserRepository(conn)
    order_repo = SqlitePaymentOrderRepository(conn)
    txn_repo = SqlitePaymentTransactionRepository(conn)
    plan_repo = SqliteSubscriptionPlanRepository(conn)
    sub_repo = SqliteSubscriptionRepository(conn)
    webhook_repo = SqliteWebhookLedgerRepository(conn)
    audit_repo = SqliteAuditEventRepository(conn)

    sub_service = SubscriptionService(sub_repo)
    audit_service = AuditService(audit_repo)
    stars_provider = TelegramStarsPaymentProvider(bot=None)

    # Seed test user
    await user_repo.save(User(id="usr_stars_fan", telegram_id=88333))

    payment_service = PaymentService(
        order_repo=order_repo,
        transaction_repo=txn_repo,
        plan_repo=plan_repo,
        webhook_ledger=webhook_repo,
        subscription_service=sub_service,
        audit_service=audit_service,
        razorpay_provider=None,
        telegram_stars_provider=stars_provider,
    )

    # 1. Create order for LikBy Spark in Stars (XTR)
    order, invoice_data = await payment_service.create_telegram_stars_order(
        user_id="usr_stars_fan",
        tier=SubscriptionTier.SPARK,
    )
    assert order.currency == "XTR"
    assert invoice_data["currency"] == "XTR"
    assert invoice_data["prices"][0]["amount"] == 15  # 15 Stars for Spark

    # 2. Pre-checkout query validation
    valid_payload = invoice_data["payload"]
    is_valid, err = await payment_service.validate_telegram_pre_checkout(valid_payload, "usr_stars_fan")
    assert is_valid is True
    assert err is None

    # Invalid pre-checkout query payload
    is_bad, bad_err = await payment_service.validate_telegram_pre_checkout("tampered_payload", "usr_stars_fan")
    assert is_bad is False
    assert bad_err is not None

    # 3. Successful payment update settlement
    charge_id = "tg_charge_xyz_999"
    ent = await payment_service.process_telegram_successful_payment(
        internal_user_id="usr_stars_fan",
        invoice_payload=valid_payload,
        telegram_payment_charge_id=charge_id,
        total_amount=15,
    )
    assert ent is not None
    assert ent.tier == SubscriptionTier.SPARK
    assert ent.is_active is True

    # 4. Duplicate successful payment is idempotent
    dup_ent = await payment_service.process_telegram_successful_payment(
        internal_user_id="usr_stars_fan",
        invoice_payload=valid_payload,
        telegram_payment_charge_id=charge_id,
        total_amount=15,
    )
    assert dup_ent is not None
    assert dup_ent.user_id == ent.user_id

    # Verify only 1 transaction recorded
    txns = await txn_repo.get_by_order_id(order.id)
    assert len(txns) == 1
    assert txns[0].provider_payment_id == charge_id

    await conn.close()
