# 34 — Web & Mini App Future

## Purpose

Define the future architectural roadmap for expanding Tikible from a pure Telegram bot into Telegram Mini Apps (TMA) and an independent standalone web platform.

## Scope

Covers Telegram WebApp `initData` authentication, WebSocket chat relay protocols, rich interactive Mini App experiences, and cross-platform interoperability.

---

## Architectural Evolution Roadmap

```mermaid
graph TD
    subgraph Phase 1: MVP (Current)
        TGClient[Telegram Mobile/Desktop Client]
        BotAdapter[aiogram 3.x Adapter]
        Core[FastAPI Backend Core]
        TGClient -->|Telegram Updates| BotAdapter
        BotAdapter --> Core
    end

    subgraph Phase 2: Telegram Mini App (TMA)
        TMAWeb[Mini App SPA<br/>React + Tailwind + Vite]
        InitAuth[Telegram initData HMAC Verification]
        TGClient -->|Opens WebApp inside Telegram| TMAWeb
        TMAWeb -->|REST / WebSocket| InitAuth
        InitAuth --> Core
    end

    subgraph Phase 3: Standalone Web App
        WebBrowser[Desktop / Mobile Browser]
        WebAuth[Passkey / Anonymous Session Auth]
        WSRelay[FastAPI WebSocket Chat Relay]
        WebBrowser --> WebAuth
        WebBrowser -->|E2EE WebSockets| WSRelay
        WSRelay --> Core
    end
```

---

## Telegram Mini App (TMA) Integration

Telegram Mini Apps run inside an in-app WebView within Telegram mobile and desktop clients, giving access to the full modern web stack (HTML5 Canvas, WebGL, animations, tactile gestures).

### 1. Cryptographic Authentication (`initData` Verification)

When the Mini App opens, Telegram provides an `initData` query string. The backend verifies that the data was signed by Telegram using the bot token secret:

```python
# src/tikible/security/telegram_webapp_auth.py
import hmac
import hashlib
from urllib.parse import parse_qsl

def verify_telegram_webapp_data(init_data_raw: str, bot_token: str) -> bool:
    """
    Validates initData received from Telegram Mini App.
    Follows official Telegram cryptographic specification:
    1. Parse query string into key-value pairs.
    2. Extract and remove 'hash'.
    3. Sort remaining keys alphabetically.
    4. Create data_check_string.
    5. Compute secret_key = HMAC_SHA256("WebAppData", bot_token).
    6. Verify HMAC_SHA256(secret_key, data_check_string) == hash.
    """
    parsed_data = dict(parse_qsl(init_data_raw))
    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        return False

    # Build data-check-string
    items = sorted([f"{k}={v}" for k, v in parsed_data.items()])
    data_check_string = "\n".join(items)

    # Compute secret key
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256
    ).digest()

    # Calculate expected hash
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_hash, received_hash)
```

### 2. High-Value Mini App Use Cases
- **Interactive Profile Builder**: Tag cloud selection, bio preview, and age-bracket sliders.
- **Match Radar**: Animated circular radar visualizer showing active peers in real-time.
- **Rich Multiplayer Games**: Turn-based board games (Connect Four, Battleship, Chess, Trivia) with zero Telegram message spam.

---

## Standalone Web Client Architecture

Expanding outside Telegram removes dependency on Telegram servers and opens global accessibility:

### 1. WebSocket Real-Time Chat Relay Protocol

```json
// Client -> Server: Message Send
{
  "type": "chat.message",
  "session_id": "ses_5e6f7g8h",
  "payload": {
    "text": "Hello! How is your day going?"
  }
}

// Server -> Recipient: Message Delivered
{
  "type": "chat.message_received",
  "session_id": "ses_5e6f7g8h",
  "sender_alias": "Alex",
  "payload": {
    "text": "Hello! How is your day going?"
  },
  "timestamp": 1776268800
}
```

### 2. Cross-Client Interoperability

Tikible's clean domain layer decouples messaging transport from core routing. 
- A user on the **Telegram Bot** can chat seamlessly with a user on the **Web Client**.
- The `ChatRelayService` determines the transport channel for each participant:
  - If `recipient.client_type == 'telegram'`: calls Telegram Bot API `sendMessage`.
  - If `recipient.client_type == 'web'`: broadcasts to the user's active WebSocket connection.

---

## End-to-End Encryption (E2EE) Roadmap for Web

While Telegram Bot chats cannot be client-side E2EE (the Bot API gateway requires plaintext messages), the standalone web and Mini App clients can support Signal Protocol / Web Crypto API:
- Each client generates an X25519 identity key and ephemeral pre-keys.
- The server acts solely as a blind ciphertext forwarder.
- The server never possesses private decryption keys.
