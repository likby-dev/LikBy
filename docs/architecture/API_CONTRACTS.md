# LikBy REST API Contracts & OpenAPI Specifications

All REST endpoints are mounted under the shared FastAPI instance (`src/likby/main.py`).

---

## 1. Health & Operations Endpoints

### 1.1 Liveness Probe
- **Path:** `GET /health/live`
- **Response:**
  ```json
  {
    "status": "alive",
    "timestamp": "2026-10-17T12:00:00Z"
  }
  ```

### 1.2 Readiness Probe
- **Path:** `GET /health/ready`
- **Response:**
  ```json
  {
    "status": "ready",
    "database": "connected",
    "storage": "accessible"
  }
  ```

---

## 2. Webhook & Payment Endpoints

### 2.1 Telegram Webhook
- **Path:** `POST /api/v1/telegram/webhook`
- **Header:** `X-Telegram-Bot-Api-Secret-Token: <secret>`
- **Body:** Standard Telegram `Update` object.
- **Status Codes:**
  - `200 OK`: Update ingested.
  - `401 Unauthorized`: Secret token mismatch.

### 2.2 Razorpay Webhook (Out-of-Telegram Purchases)
- **Path:** `POST /api/v1/payments/razorpay/webhook`
- **Header:** `X-Razorpay-Signature: <hmac_sha256>`
- **Body:** Razorpay order / payment payload.
- **Verification:** HMAC-SHA256 signature calculated over raw request body using `RAZORPAY_WEBHOOK_SECRET`.

---

## 3. Telegram Mini App Gaming API

### 3.1 Session State
- **Path:** `GET /api/v1/play/session/{session_id}`
- **Header:** `X-Telegram-Init-Data: <initData>`
- **Response:**
  ```json
  {
    "game_id": "connect_four",
    "turn": "player_x",
    "board": [[null, null, ...]],
    "status": "in_progress"
  }
  ```

### 3.2 Submit Move
- **Path:** `POST /api/v1/play/session/{session_id}/move`
- **Header:** `X-Telegram-Init-Data: <initData>`
- **Body:**
  ```json
  {
    "player_id": "usr_abc123",
    "action": "drop_column",
    "column": 3
  }
  ```
- **Response:** Updated game state with server-authoritative win/draw evaluation.
