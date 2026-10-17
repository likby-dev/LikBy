"""
likby.services.firebase_service
FastAPI backend service for Firebase Admin and Google Cloud Firestore.
Provides server-side admin capabilities and exposes safe client-side config for frontends.
"""

import os
from typing import Any, Dict, Optional
import firebase_admin
from firebase_admin import credentials, firestore, auth
import structlog

logger = structlog.get_logger(__name__)

# Public web app configuration (safe for frontend / Telegram Mini Apps)
FIREBASE_CLIENT_CONFIG: Dict[str, str] = {
    "apiKey": os.environ.get("FIREBASE_API_KEY", "AIzaSyCIL4zRW3mbuqkT6OPdUwc6i7Xas4Acd5c"),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", "likby-2026.firebaseapp.com"),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID", "likby-2026"),
    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET", "likby-2026.firebasestorage.app"),
    "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID", "830552724373"),
    "appId": os.environ.get("FIREBASE_APP_ID", "1:830552724373:web:0b6af5ee2210f21e4fdc9c"),
    "measurementId": os.environ.get("FIREBASE_MEASUREMENT_ID", "G-J1E2L7FMTZ"),
}


class FirebaseBackendService:
    """Singleton service managing Firebase Admin SDK and Firestore connections."""

    _instance: Optional["FirebaseBackendService"] = None

    def __init__(self, credentials_path: Optional[str] = None, project_id: Optional[str] = None) -> None:
        self._project_id = project_id or os.environ.get("FIREBASE_PROJECT_ID", "likby-2026")
        self._credentials_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "firebase-credentials.json")
        self._app: Optional[firebase_admin.App] = None
        self._db: Optional[Any] = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Firebase Admin with service account credentials."""
        try:
            # Check if default app already initialized
            if not firebase_admin._apps:
                if self._credentials_path and os.path.exists(self._credentials_path):
                    cred = credentials.Certificate(self._credentials_path)
                    self._app = firebase_admin.initialize_app(cred, {"projectId": self._project_id})
                    logger.info("Firebase Admin initialized with service account", project_id=self._project_id)
                else:
                    self._app = firebase_admin.initialize_app(options={"projectId": self._project_id})
                    logger.info("Firebase Admin initialized with default credentials", project_id=self._project_id)
            else:
                self._app = firebase_admin.get_app()

            self._db = firestore.client()
        except Exception as exc:
            logger.warning("Firebase Admin initialization deferred/failed", error=str(exc))
            self._app = None
            self._db = None

    @property
    def is_connected(self) -> bool:
        """Check if Firebase Admin is connected."""
        return self._app is not None and self._db is not None

    @property
    def db(self) -> Any:
        """Return Firestore client."""
        if not self._db:
            raise RuntimeError("Firestore is not initialized. Check service account credentials.")
        return self._db

    def get_client_config(self) -> Dict[str, str]:
        """Return safe public client configuration for web clients and Mini Apps."""
        return FIREBASE_CLIENT_CONFIG

    async def verify_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """Verify Firebase ID token sent from frontend."""
        if not self._app:
            return None
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as exc:
            logger.warning("Firebase token verification failed", error=str(exc))
            return None


_firebase_service: Optional[FirebaseBackendService] = None


def get_firebase_backend() -> FirebaseBackendService:
    """Dependency getter for FastAPI endpoints."""
    global _firebase_service
    if _firebase_service is None:
        _firebase_service = FirebaseBackendService()
    return _firebase_service
