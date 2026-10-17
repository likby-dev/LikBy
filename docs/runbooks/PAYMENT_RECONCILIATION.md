# Runbook: Payment Reconciliation

1. For Telegram Stars: inspect Telegram transaction ID via `/paysupport` logs.
2. For Razorpay: query Razorpay Payments API with `order_id` to verify capture status.
3. Use administrative CLI `python scripts/maintenance/reconcile_payment.py --payment-id <ID>` to manually activate entitlement if webhook dropped.
