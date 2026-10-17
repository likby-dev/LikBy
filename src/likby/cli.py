"""
likby.cli
Command-line interface utilities for LikBy administration and configuration checks.
"""

import argparse
import sys
from likby.config import get_settings


def check_config() -> int:
    """
    Validate application configuration safely without printing secrets.
    Returns 0 if valid, 1 if configuration errors exist.
    """
    try:
        settings = get_settings()
    except Exception as e:
        print(f"[FAIL] Configuration loading error: {e}", file=sys.stderr)
        return 1

    print("==================================================")
    print(f"LikBy Configuration Audit ({settings.environment.upper()})")
    print("==================================================")

    errors = []
    warnings = []

    # 1. Core & Server
    print(f"[*] Environment: {settings.environment}")
    print(f"[*] Debug: {settings.debug}")
    print(f"[*] Base URL: {settings.base_url}")
    print(f"[*] Timezone: {settings.timezone}")

    # 2. Telegram Bot
    bot_token = settings.bot_token.get_secret_value() if settings.bot_token else ""
    if bot_token and ":" in bot_token:
        print("[OK] Telegram Bot Token: [CONFIGURED]")
    else:
        errors.append("Invalid or missing TELEGRAM_BOT_TOKEN")

    print(f"[*] Bot Mode: {settings.bot_mode}")
    if settings.bot_mode == "webhook":
        sec_token = settings.webhook_secret_token.get_secret_value()
        if len(sec_token) < 16:
            errors.append("WEBHOOK_SECRET_TOKEN must be at least 16 characters in webhook mode")
        else:
            print("[OK] Webhook Secret Token: [CONFIGURED]")

    # 3. Database
    print(f"[*] Database Backend: {settings.database_backend}")
    if settings.database_backend == "postgres":
        db_url = settings.supabase_db_url or settings.database_url
        if not db_url or "sqlite" in db_url:
            errors.append("DATABASE_BACKEND='postgres' requires a valid SUPABASE_DB_URL or DATABASE_URL")
        else:
            print("[OK] Supabase PostgreSQL URL: [CONFIGURED]")
    elif settings.database_backend == "sqlite":
        print(f"[OK] Local SQLite URL: {settings.database_url}")

    # 4. Conversation Store (Firestore)
    if settings.firebase_project_id:
        print(f"[OK] Firestore Project ID: {settings.firebase_project_id}")
        print(f"[*] Firestore Database ID: {settings.firestore_database_id}")
    else:
        if settings.environment == "production":
            warnings.append("FIREBASE_PROJECT_ID is unset; conversation storage will fallback to relational/local adapter.")
        else:
            print("[*] Firestore Project ID: [UNCONFIGURED - Local In-Memory Fallback Active]")

    # 5. Media Storage (Cloudflare R2)
    print(f"[*] Storage Provider: {settings.storage_provider}")
    if settings.storage_provider == "r2":
        if not (settings.r2_access_key_id and settings.r2_secret_access_key and settings.r2_bucket_name):
            errors.append("STORAGE_PROVIDER='r2' requires R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME")
        else:
            print(f"[OK] Cloudflare R2 Bucket: {settings.r2_bucket_name} [CONFIGURED]")
    else:
        print(f"[OK] Storage: Local Filesystem ({settings.media_store_dir})")

    # 6. Mini App
    if settings.telegram_mini_app_url:
        print(f"[OK] Telegram Mini App URL: {settings.telegram_mini_app_url}")
    else:
        print("[*] Telegram Mini App URL: [UNCONFIGURED - Default relative /play]")

    print("--------------------------------------------------")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  [!] {w}")

    if errors:
        print("Errors:")
        for err in errors:
            print(f"  [X] {err}", file=sys.stderr)
        print("==================================================")
        print("[FAIL] Configuration check failed.", file=sys.stderr)
        return 1

    print("==================================================")
    print("[PASS] Configuration check succeeded.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="LikBy CLI management tool")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("check-config", help="Verify environment configuration without leaking secrets")

    args = parser.parse_args()
    if args.command == "check-config":
        sys.exit(check_config())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
