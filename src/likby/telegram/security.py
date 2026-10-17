"""
likby.telegram.security
Official Telegram Mini App initData validation using HMAC-SHA256 signature verification.
Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, unquote


def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates Telegram WebApp initData against the bot token.
    Returns parsed dictionary (including 'user') if signature is valid, or None if invalid.
    """
    if not init_data or not bot_token:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")

        # Sort remaining keys alphabetically and format as key=value\n
        data_check_string = "\n".join(
            f"{key}={parsed_data[key]}" for key in sorted(parsed_data.keys())
        )

        # 1. secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        # 2. calculated_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        # Parse user JSON if present
        if "user" in parsed_data:
            try:
                parsed_data["user"] = json.loads(unquote(parsed_data["user"]))
            except Exception:
                pass

        return parsed_data
    except Exception:
        return None
