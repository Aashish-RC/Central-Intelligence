"""App-Level Identity Scoping, Rate Limiting & Isolation (Layer 12: IAM, Task 12.6).

Features:
- 12.26: App-level API keys for distinct application endpoints
- 12.27: Per-app rate limiting and burst controls
- 12.28: Per-app data isolation and namespace partitioning
- 12.29: Granular per-app capability and tool scoping
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.identity.app")


@dataclass
class AppScopeRecord:
    """Application entity registered within a tenant."""
    app_id: str
    name: str
    tenant_id: str
    api_key_hash: str
    capabilities: Set[str] = field(default_factory=lambda: {"chat:complete"})
    rate_limit_rpm: int = 60
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AppScopeManager:
    """Manages application boundaries, credentials, permissions, and request throttles."""

    def __init__(self):
        self._apps: Dict[str, AppScopeRecord] = {}  # app_id -> app
        self._key_index: Dict[str, str] = {}  # key_hash -> app_id
        self._request_windows: Dict[str, List[float]] = {}  # app_id -> timestamps

    def register_app(
        self,
        app_id: str,
        name: str,
        tenant_id: str = "default",
        capabilities: Optional[Set[str]] = None,
        rate_limit_rpm: int = 60,
    ) -> Tuple[str, AppScopeRecord]:
        """Registers application; returns (raw_api_key, app_record)."""
        raw_key = f"appkey_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        app = AppScopeRecord(
            app_id=app_id,
            name=name,
            tenant_id=tenant_id,
            api_key_hash=key_hash,
            capabilities=capabilities or {"chat:complete"},
            rate_limit_rpm=rate_limit_rpm,
        )
        self._apps[app_id] = app
        self._key_index[key_hash] = app_id
        return raw_key, app

    def authenticate_app_key(self, raw_key: str) -> AppScopeRecord:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        app_id = self._key_index.get(key_hash)
        if not app_id:
            raise PermissionError("Invalid application API key")

        app = self._apps[app_id]
        if not app.is_active:
            raise PermissionError("Application is suspended")

        return app

    def check_app_capability(self, app_id: str, capability: str) -> bool:
        """Verifies if application has granted capability (12.29)."""
        app = self._apps.get(app_id)
        if not app or not app.is_active:
            return False
        return capability in app.capabilities or "*" in app.capabilities

    def check_data_isolation(self, requester_app_id: str, target_app_id: str) -> bool:
        """Enforces application-level data isolation (12.28)."""
        return requester_app_id == target_app_id

    def check_rate_limit(self, app_id: str) -> bool:
        """Per-application sliding-window rate limiting (12.27)."""
        app = self._apps.get(app_id)
        if not app or not app.is_active:
            return False

        now = time.time()
        window_start = now - 60.0

        ts_list = self._request_windows.setdefault(app_id, [])
        ts_list = [ts for ts in ts_list if ts > window_start]
        self._request_windows[app_id] = ts_list

        if len(ts_list) >= app.rate_limit_rpm:
            return False

        ts_list.append(now)
        return True


# Default singleton
default_app_scope_manager = AppScopeManager()

