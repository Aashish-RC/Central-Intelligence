"""On-Demand Auth Bridge: Idle-until-needed credential resolution and auth request queue."""

import threading
from typing import Dict, List, Optional
from ..core.interfaces import BaseOnDemandAuth
from ..core.models import AuthRequest, CredentialStatus, utc_now


class OnDemandAuthBridge(BaseOnDemandAuth):
    """Enforces the idle-until-needed rule: connectors ask for credentials strictly when used."""

    def __init__(self):
        self._lock = threading.Lock()
        self._credentials: Dict[str, str] = {}
        self._pending_requests: Dict[str, AuthRequest] = {}

    def has_credential(self, credential_name: str) -> bool:
        with self._lock:
            return credential_name in self._credentials and bool(self._credentials[credential_name])

    def request_credential(self, tool_name: str, credential_name: str) -> AuthRequest:
        with self._lock:
            # Check if there is already a pending request for this credential
            for req in self._pending_requests.values():
                if req.credential_name == credential_name and req.status == CredentialStatus.REQUESTED:
                    return req

            req = AuthRequest(
                tool_name=tool_name,
                credential_name=credential_name,
                status=CredentialStatus.REQUESTED,
                requested_at=utc_now(),
            )
            self._pending_requests[req.id] = req
            return req

    def provide_credential(self, credential_name: str, secret_value: str) -> bool:
        with self._lock:
            self._credentials[credential_name] = secret_value
            # Resolve any matching pending requests
            for req in self._pending_requests.values():
                if req.credential_name == credential_name:
                    req.status = CredentialStatus.ACTIVE
            return True

    def get_credential(self, credential_name: str) -> Optional[str]:
        with self._lock:
            return self._credentials.get(credential_name)

    def revoke_credential(self, credential_name: str) -> bool:
        with self._lock:
            if credential_name in self._credentials:
                del self._credentials[credential_name]
                return True
            return False

    def get_pending_requests(self) -> List[AuthRequest]:
        with self._lock:
            return [
                req
                for req in self._pending_requests.values()
                if req.status == CredentialStatus.REQUESTED
            ]
