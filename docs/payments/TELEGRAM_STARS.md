# LikBy Telegram Stars Integration & Lifecycle

---

## 1. Lifecycle Events

```mermaid
sequenceDiagram
    autonumber
    actor User as Telegram User
    participant Bot as LikBy Bot
    participant TG as Telegram Payment Server

    User->>Bot: Tap "Upgrade to Premium (250 Stars)"
    Bot->>TG: sendInvoice(title, description, payload, currency="XTR", prices=[{amount: 250}])
    TG-->>User: Native Stars Payment Modal
    User->>TG: Confirms Payment
    TG->>Bot: pre_checkout_query(id, payload, total_amount)
    Bot->>Bot: Validate product & user eligibility
    Bot->>TG: answerPreCheckoutQuery(ok=True)
    TG->>Bot: successful_payment(telegram_payment_charge_id, provider_payment_charge_id)
    Bot->>Bot: Activate Subscription Entitlement & Record Ledger
    Bot-->>User: Receipt & Instant Premium Activation
```

---

## 2. Customer Support & Reconciliation
- The command `/paysupport` provides users with recent transaction IDs and an immediate link to customer support.
