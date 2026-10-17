"""
likby.services.payment_service
Orchestrates payment order lifecycles, provider adapters, signature verifications, and idempotent activations.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid
from likby.domain.entities.payment import (
    PaymentOrder,
    PaymentTransaction,
    WebhookEventLedger,
)
from likby.domain.entities.subscription import (
    PLAN_SPECS,
    SubscriptionEntitlement,
    SubscriptionTier,
)
from likby.domain.enums import (
    EntitlementSource,
    PaymentOrderStatus,
    PaymentProviderType,
    PaymentTransactionStatus,
    WebhookProcessingStatus,
)
from likby.repositories.interfaces import (
    PaymentOrderRepository,
    PaymentTransactionRepository,
    SubscriptionPlanRepository,
    WebhookLedgerRepository,
)
from likby.services.audit_service import AuditService
from likby.services.payment_provider import (
    PaymentProvider,
    RazorpayPaymentProvider,
    TelegramStarsPaymentProvider,
)
from likby.services.subscription_service import SubscriptionService


class PaymentService:
    """Core payment gateway service managing order lifecycle, verification, and transaction ledgers."""

    def __init__(
        self,
        order_repo: PaymentOrderRepository,
        transaction_repo: Optional[PaymentTransactionRepository] = None,
        plan_repo: Optional[SubscriptionPlanRepository] = None,
        webhook_ledger: Optional[WebhookLedgerRepository] = None,
        subscription_service: Optional[SubscriptionService] = None,
        audit_service: Optional[AuditService] = None,
        razorpay_provider: Optional[RazorpayPaymentProvider] = None,
        telegram_stars_provider: Optional[TelegramStarsPaymentProvider] = None,
        # Common aliases
        txn_repo: Optional[PaymentTransactionRepository] = None,
        webhook_ledger_repo: Optional[WebhookLedgerRepository] = None,
        stars_provider: Optional[TelegramStarsPaymentProvider] = None,
        user_repo: Optional[Any] = None,
    ) -> None:
        self._order_repo = order_repo
        self._txn_repo = transaction_repo or txn_repo
        self._plan_repo = plan_repo
        self._webhook_ledger = webhook_ledger or webhook_ledger_repo
        self._sub_service = subscription_service
        self._audit = audit_service
        self._razorpay = razorpay_provider
        self._stars = telegram_stars_provider or stars_provider

    def _get_provider(self, provider_type: PaymentProviderType) -> PaymentProvider:
        if provider_type == PaymentProviderType.RAZORPAY:
            return self._razorpay
        elif provider_type == PaymentProviderType.TELEGRAM_STARS:
            return self._stars
        raise ValueError(f"Unsupported payment provider: {provider_type}")

    async def create_checkout_order(
        self,
        user_id: str,
        plan_code: str,
        provider: PaymentProviderType,
        duration_days: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[PaymentOrder], Optional[dict]]:
        """
        Server-side authoritative order generation.
        Calculates exact price from server catalog and interfaces with the provider adapter.
        """
        code_upper = plan_code.upper()
        try:
            tier = SubscriptionTier(code_upper)
        except ValueError:
            return False, f"Invalid plan code: {plan_code}", None, None

        if tier == SubscriptionTier.BASE:
            return False, "LikBy Base is free and does not require checkout.", None, None

        spec = PLAN_SPECS[tier]
        idem_key = idempotency_key or f"idem_{user_id}_{code_upper}_{uuid.uuid4().hex[:8]}"

        # Check existing idempotency
        existing = await self._order_repo.get_by_idempotency_key(idem_key)
        if existing and existing.status == PaymentOrderStatus.CREATED:
            return True, "Order already created.", existing, None

        # Resolve duration and price
        if duration_days and duration_days == 90 and "optional_90d_inr_paise" in spec:
            duration_seconds = 7776000
            price_inr = spec["optional_90d_inr_paise"]
            price_stars = spec["optional_90d_stars"]
        else:
            duration_seconds = spec["duration_seconds"] or 2592000
            price_inr = spec["target_price_inr_paise"]
            price_stars = spec["stars_amount"]

        if provider == PaymentProviderType.RAZORPAY:
            amount = price_inr
            currency = "INR"
        else:
            amount = price_stars
            currency = "XTR"

        internal_order_id = f"LIKBY-{provider.value[:3]}-{uuid.uuid4().hex[:10].upper()}"
        adapter = self._get_provider(provider)

        success, provider_order_id, err = await adapter.create_order(
            internal_order_id=internal_order_id,
            amount_minor_units=amount,
            currency=currency,
            receipt=internal_order_id,
            notes={"user_id": user_id, "plan_code": code_upper},
        )

        if not success or not provider_order_id:
            return False, f"Provider error: {err or 'Could not create order'}", None, None

        order = PaymentOrder(
            id=f"ord_{uuid.uuid4().hex[:14]}",
            internal_order_id=internal_order_id,
            user_id=user_id,
            plan_id=f"plan_{code_upper.lower()}",
            provider=provider,
            provider_order_id=provider_order_id,
            amount_minor_units=amount,
            currency=currency,
            status=PaymentOrderStatus.CREATED,
            idempotency_key=idem_key,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        await self._order_repo.save(order)

        await self._audit.record(
            actor_id=user_id,
            event_type="PAYMENT_ORDER_CREATED",
            entity_type="PAYMENT_ORDER",
            entity_id=order.id,
            metadata={
                "internal_order_id": internal_order_id,
                "provider": provider.value,
                "amount": amount,
                "currency": currency,
            },
        )

        checkout_data = {
            "internal_order_id": internal_order_id,
            "provider_order_id": provider_order_id,
            "amount": amount,
            "currency": currency,
            "plan_display_name": spec["display_name"],
            "duration_seconds": duration_seconds,
        }

        return True, "Order generated successfully.", order, checkout_data

    async def verify_and_settle_razorpay_payment(
        self,
        internal_order_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Tuple[bool, str, Optional[PaymentTransaction]]:
        """
        Verify Razorpay HMAC-SHA256 signature and settle subscription entitlement idempotently.
        """
        order = await self._order_repo.get_by_internal_order_id(internal_order_id)
        if not order:
            return False, "Order reference not found.", None

        if order.provider != PaymentProviderType.RAZORPAY:
            return False, "Order provider mismatch.", None

        if order.provider_order_id and order.provider_order_id != razorpay_order_id:
            return False, "Razorpay order ID does not match expected order.", None

        # Verify signature
        if not self._razorpay.verify_payment_signature(
            provider_order_id=razorpay_order_id,
            provider_payment_id=razorpay_payment_id,
            signature=razorpay_signature,
        ):
            await self._audit.record(
                actor_id=order.user_id,
                event_type="PAYMENT_SIGNATURE_VERIFICATION_FAILED",
                entity_type="PAYMENT_ORDER",
                entity_id=order.id,
                metadata={"provider_payment_id": razorpay_payment_id},
            )
            return False, "Invalid cryptographic payment signature.", None

        # Idempotency check: if order is already paid, return settled without duplicate activation
        if order.status == PaymentOrderStatus.PAID:
            existing_txns = await self._txn_repo.get_by_order_id(order.id)
            return True, "Payment already settled and verified.", existing_txns[0] if existing_txns else None

        # Create captured transaction record
        now = datetime.now(timezone.utc)
        transaction = PaymentTransaction(
            id=f"txn_{uuid.uuid4().hex[:14]}",
            order_id=order.id,
            provider=PaymentProviderType.RAZORPAY,
            provider_payment_id=razorpay_payment_id,
            provider_order_id=razorpay_order_id,
            provider_signature_verified=True,
            amount_minor_units=order.amount_minor_units,
            currency=order.currency,
            payment_status=PaymentTransactionStatus.CAPTURED,
            captured_at=now,
            created_at=now,
        )
        await self._txn_repo.save(transaction)

        # Update order status
        order.status = PaymentOrderStatus.PAID
        await self._order_repo.save(order)

        # Determine target tier and duration from plan_id
        plan_code = order.plan_id.replace("plan_", "").upper()
        tier = SubscriptionTier(plan_code)
        spec = PLAN_SPECS[tier]
        duration_seconds = spec["duration_seconds"] or 2592000

        # Activate subscription entitlement
        await self._sub_service.activate_subscription(
            user_id=order.user_id,
            new_tier=tier,
            duration_seconds=duration_seconds,
            source=EntitlementSource.PURCHASE,
            source_transaction_id=transaction.id,
        )

        await self._audit.record(
            actor_id=order.user_id,
            event_type="PAYMENT_VERIFIED_CAPTURED",
            entity_type="PAYMENT_TRANSACTION",
            entity_id=transaction.id,
            metadata={
                "order_id": order.id,
                "amount": order.amount_minor_units,
                "currency": order.currency,
                "tier": tier.value,
            },
        )

        return True, "Payment verified and subscription activated successfully.", transaction

    async def settle_telegram_stars_payment(
        self,
        user_id: str,
        internal_order_id: str,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: Optional[str] = None,
        total_amount: int = 0,
    ) -> Tuple[bool, str, Optional[PaymentTransaction]]:
        """
        Settle in-bot Telegram Stars payment idempotently upon successful_payment update.
        """
        order = await self._order_repo.get_by_internal_order_id(internal_order_id)
        if not order:
            return False, "Order reference not found.", None

        if order.currency != "XTR":
            return False, "Currency mismatch for Stars payment.", None

        if total_amount > 0 and total_amount != order.amount_minor_units:
            return False, f"Amount mismatch: received {total_amount} Stars, expected {order.amount_minor_units}.", None

        # Idempotency check by provider_payment_id
        existing_txn = await self._txn_repo.get_by_provider_payment_id(telegram_payment_charge_id)
        if existing_txn:
            return True, "Payment charge already processed and settled.", existing_txn

        now = datetime.now(timezone.utc)
        transaction = PaymentTransaction(
            id=f"txn_{uuid.uuid4().hex[:14]}",
            order_id=order.id,
            provider=PaymentProviderType.TELEGRAM_STARS,
            provider_payment_id=telegram_payment_charge_id,
            provider_order_id=provider_payment_charge_id or order.provider_order_id,
            provider_signature_verified=True,
            amount_minor_units=order.amount_minor_units,
            currency="XTR",
            payment_status=PaymentTransactionStatus.CAPTURED,
            captured_at=now,
            created_at=now,
        )
        await self._txn_repo.save(transaction)

        order.status = PaymentOrderStatus.PAID
        await self._order_repo.save(order)

        # Activate entitlement
        plan_code = order.plan_id.replace("plan_", "").upper()
        tier = SubscriptionTier(plan_code)
        spec = PLAN_SPECS[tier]
        duration_seconds = spec["duration_seconds"] or 2592000

        await self._sub_service.activate_subscription(
            user_id=order.user_id,
            new_tier=tier,
            duration_seconds=duration_seconds,
            source=EntitlementSource.PURCHASE,
            source_transaction_id=transaction.id,
        )

        await self._audit.record(
            actor_id=user_id,
            event_type="STARS_PAYMENT_CAPTURED",
            entity_type="PAYMENT_TRANSACTION",
            entity_id=transaction.id,
            metadata={
                "order_id": order.id,
                "stars_amount": order.amount_minor_units,
                "tier": tier.value,
                "charge_id": telegram_payment_charge_id,
            },
        )

        return True, "Telegram Stars payment settled and subscription activated.", transaction

    async def process_razorpay_webhook(
        self,
        raw_body: bytes,
        signature: str,
    ) -> Tuple[bool, str]:
        """
        Idempotent Razorpay webhook ingestion with signature verification and deduplication.
        """
        if not self._razorpay.verify_webhook_signature(raw_body, signature):
            return False, "Invalid webhook HMAC signature."

        try:
            event_data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return False, "Malformed JSON payload in webhook."

        event_id = event_data.get("id") or f"evt_{hashlib.sha256(raw_body).hexdigest()[:16]}"
        event_type = event_data.get("event", "unknown")
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # Idempotent deduplication ledger
        now = datetime.now(timezone.utc)
        ledger_entry = WebhookEventLedger(
            id=f"whk_{uuid.uuid4().hex[:14]}",
            provider=PaymentProviderType.RAZORPAY,
            provider_event_id=event_id,
            event_type=event_type,
            signature_verified=True,
            processing_status=WebhookProcessingStatus.PROCESSED,
            payload_hash=payload_hash,
            received_at=now,
            processed_at=now,
        )

        is_new = await self._webhook_ledger.record_event(ledger_entry)
        if not is_new:
            return True, "Duplicate webhook event acknowledged."

        # Handle events: payment.captured, order.paid
        payload = event_data.get("payload", {})
        if event_type in ("payment.captured", "order.paid"):
            payment_entity = payload.get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")

            if order_id and payment_id:
                order = await self._order_repo.get_by_provider_order_id(
                    PaymentProviderType.RAZORPAY, order_id
                )
                if order and order.status != PaymentOrderStatus.PAID:
                    # Settle transaction
                    txn = PaymentTransaction(
                        id=f"txn_{uuid.uuid4().hex[:14]}",
                        order_id=order.id,
                        provider=PaymentProviderType.RAZORPAY,
                        provider_payment_id=payment_id,
                        provider_order_id=order_id,
                        provider_signature_verified=True,
                        amount_minor_units=order.amount_minor_units,
                        currency=order.currency,
                        payment_status=PaymentTransactionStatus.CAPTURED,
                        captured_at=now,
                        created_at=now,
                    )
                    await self._txn_repo.save(txn)
                    order.status = PaymentOrderStatus.PAID
                    await self._order_repo.save(order)

                    plan_code = order.plan_id.replace("plan_", "").upper()
                    tier = SubscriptionTier(plan_code)
                    duration_seconds = PLAN_SPECS[tier]["duration_seconds"] or 2592000
                    await self._sub_service.activate_subscription(
                        user_id=order.user_id,
                        new_tier=tier,
                        duration_seconds=duration_seconds,
                        source=EntitlementSource.PURCHASE,
                        source_transaction_id=txn.id,
                    )

        return True, "Webhook processed successfully."

    async def handle_razorpay_webhook(
        self,
        raw_body: bytes,
        signature_header: Optional[str],
    ) -> Dict[str, Any]:
        """
        Idempotent Razorpay webhook ingestion returning structured status.
        """
        if not signature_header:
            return {"status": "invalid_signature", "detail": "Missing signature header"}
        if not self._razorpay.verify_webhook_signature(raw_body, signature_header):
            return {"status": "invalid_signature", "detail": "Invalid signature"}

        try:
            event_data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return {"status": "error", "detail": "Malformed JSON"}

        event_id = event_data.get("id") or f"evt_{hashlib.sha256(raw_body).hexdigest()[:16]}"
        event_type = event_data.get("event", "unknown")
        payload_hash = hashlib.sha256(raw_body).hexdigest()
        now = datetime.now(timezone.utc)

        ledger_entry = WebhookEventLedger(
            id=f"whk_{uuid.uuid4().hex[:14]}",
            provider=PaymentProviderType.RAZORPAY,
            provider_event_id=event_id,
            event_type=event_type,
            signature_verified=True,
            processing_status=WebhookProcessingStatus.PROCESSED,
            payload_hash=payload_hash,
            received_at=now,
            processed_at=now,
        )
        is_new = await self._webhook_ledger.record_event(ledger_entry)
        if not is_new:
            return {"status": "duplicate_ignored", "event_id": event_id}

        payload = event_data.get("payload", {})
        if event_type in ("payment.captured", "order.paid"):
            payment_entity = payload.get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")

            if order_id and payment_id:
                order = await self._order_repo.get_by_provider_order_id(
                    PaymentProviderType.RAZORPAY, order_id
                )
                if order and order.status != PaymentOrderStatus.PAID:
                    txn = PaymentTransaction(
                        id=f"txn_{uuid.uuid4().hex[:14]}",
                        order_id=order.id,
                        provider=PaymentProviderType.RAZORPAY,
                        provider_payment_id=payment_id,
                        provider_order_id=order_id,
                        provider_signature_verified=True,
                        amount_minor_units=order.amount_minor_units,
                        currency=order.currency,
                        payment_status=PaymentTransactionStatus.CAPTURED,
                        captured_at=now,
                        created_at=now,
                    )
                    await self._txn_repo.save(txn)
                    order.status = PaymentOrderStatus.PAID
                    await self._order_repo.save(order)

                    plan_code = order.plan_id.replace("plan_", "").upper()
                    tier = SubscriptionTier(plan_code)
                    duration_seconds = PLAN_SPECS[tier]["duration_seconds"] or 2592000
                    await self._sub_service.activate_subscription(
                        user_id=order.user_id,
                        new_tier=tier,
                        duration_seconds=duration_seconds,
                        source=EntitlementSource.PURCHASE,
                        source_transaction_id=txn.id,
                    )

        return {"status": "processed", "event_id": event_id}

    async def create_web_razorpay_order(
        self,
        user_id: str,
        tier: SubscriptionTier,
    ) -> Optional[PaymentOrder]:
        """Convenience method to generate web Razorpay payment order."""
        ok, msg, order, _ = await self.create_checkout_order(
            user_id=user_id,
            plan_code=tier.value,
            provider=PaymentProviderType.RAZORPAY,
        )
        return order if ok else None

    async def verify_and_activate_razorpay_payment(
        self,
        internal_user_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Optional[SubscriptionEntitlement]:
        """Authoritatively verify payment signature and activate user entitlement."""
        order = await self._order_repo.get_by_provider_order_id(
            PaymentProviderType.RAZORPAY, razorpay_order_id
        )
        if not order:
            order = await self._order_repo.get_by_internal_order_id(razorpay_order_id)
        if not order or order.user_id != internal_user_id:
            return None

        ok, msg, txn = await self.verify_and_settle_razorpay_payment(
            internal_order_id=order.internal_order_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )
        if not ok:
            return None

        return await self._sub_service.get_or_create_entitlement(internal_user_id)

    async def create_telegram_stars_order(
        self,
        user_id: str,
        tier: SubscriptionTier,
    ) -> Tuple[PaymentOrder, dict]:
        """Create order and Telegram Stars invoice payload."""
        ok, msg, order, _ = await self.create_checkout_order(
            user_id=user_id,
            plan_code=tier.value,
            provider=PaymentProviderType.TELEGRAM_STARS,
        )
        spec = PLAN_SPECS[tier]
        invoice = {
            "title": spec["display_name"],
            "description": spec["description"],
            "payload": order.internal_order_id,
            "currency": "XTR",
            "prices": [{"label": spec["display_name"], "amount": order.amount_minor_units}],
        }
        return order, invoice

    async def validate_telegram_pre_checkout(
        self,
        invoice_payload: str,
        user_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Validate pre-checkout query payload."""
        order = await self._order_repo.get_by_internal_order_id(invoice_payload)
        if not order:
            return False, "Order not found."
        if order.user_id != user_id:
            return False, "User mismatch."
        return True, None

    async def process_telegram_successful_payment(
        self,
        internal_user_id: str,
        invoice_payload: str,
        telegram_payment_charge_id: str,
        total_amount: int,
    ) -> Optional[SubscriptionEntitlement]:
        """Process successful payment update from Telegram Bot API."""
        order = await self._order_repo.get_by_internal_order_id(invoice_payload)
        if not order or order.user_id != internal_user_id:
            return None

        ok, msg, txn = await self.settle_telegram_stars_payment(
            internal_order_id=invoice_payload,
            user_id=internal_user_id,
            telegram_payment_charge_id=telegram_payment_charge_id,
            total_amount=total_amount,
        )
        if not ok:
            return None
        return await self._sub_service.get_or_create_entitlement(internal_user_id)

    async def get_user_transaction_history(self, user_id: str) -> List[dict]:
        """Returns safe user payment transaction history for /payment_history."""
        orders = await self._order_repo.get_user_orders(user_id, limit=20)
        history = []
        for o in orders:
            txns = await self._txn_repo.get_by_order_id(o.id)
            plan_code = o.plan_id.replace("plan_", "").upper()
            tier = SubscriptionTier(plan_code)
            display_name = PLAN_SPECS.get(tier, {}).get("display_name", o.plan_id)

            history.append({
                "internal_order_id": o.internal_order_id,
                "plan_display_name": display_name,
                "provider": o.provider.value,
                "amount": o.amount_minor_units if o.currency == "XTR" else f"₹{o.amount_minor_units / 100:.2f}",
                "currency": o.currency,
                "status": o.status.value,
                "created_at": o.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                "transaction_count": len(txns),
            })
        return history
