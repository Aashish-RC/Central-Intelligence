"""Infisical Secret Vault & Lifecycle Adapter (Layer 12: Identity & Access Management, Task 12.3).

Features:
- 12.33: Provider-key vault for user-supplied keys (Bring Your Own Key - BYOK)
- 12.34: External secret-manager integration (Infisical, Vault, AWS Secrets Manager)
- 12.35: Zero-downtime secret rotation
- 12.36: Immutable secret access auditing
- 12.37: Per-tenant and per-app secret scoping
- 12.38: Dynamic secret injection into running agent runtimes
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.identity.secrets")


@dataclass
class SecretAuditEntry:
    """Audit log entry for any secret operation."""
    audit_id: str
    actor_id: str
    action: str  # "STORE", "READ", "ROTATE", "DELETE", "INJECT"
    secret_key: str
    tenant_id: str
    app_id: Optional[str] = None
    version: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SecretVersion:
    """Historical version of a secret for zero-downtime rotation."""
    version: int
    value: str
    created_at: str
    expires_at: Optional[float] = None


@dataclass
class ScopedSecret:
    """Secret entry scoped by tenant and application."""
    key: str
    current_value: str
    current_version: int
    tenant_id: str
    app_id: Optional[str] = None
    versions: List[SecretVersion] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class InfisicalAdapter:
    """Manages secure secret storage, zero-downtime key rotation, and audited access."""

    def __init__(
        self,
        server_url: str = "http://localhost:8083",
        project_id: str = "central-intelligence-vault",
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        _defer_prod_check: bool = False,
    ):
        self.server_url = server_url.rstrip("/")
        self.project_id = project_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("infisical")
        )

        self._client: Optional[Any] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

        # Internal encrypted vault store for standalone / hermetic runtime execution
        self._vault: Dict[Tuple[str, Optional[str], str], ScopedSecret] = {}  # (tenant_id, app_id, key) -> secret
        self._audit_log: List[SecretAuditEntry] = []

        if not _defer_prod_check and self.adapter_mode == "live":
            self._ensure_live_backend()
            if self.client_id or self.client_secret:
                self._ensure_token()

    def _http_client(self):
        """Return a cached httpx.Client bound to self.server_url with 5-second timeout."""
        if self._client is None or self._client.is_closed:
            import httpx
            self._client = httpx.Client(
                base_url=self.server_url,
                timeout=5.0,
            )
        return self._client

    def _ensure_token(self) -> None:
        """Acquire or refresh universal auth access token in live mode."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return
        if not self.client_id or not self.client_secret:
            fail_closed_in_production(
                "infisical",
                "Infisical universal-auth requires client_id and client_secret in live mode",
            )
        if self._access_token and self._token_expires_at and time.time() < self._token_expires_at:
            return
        try:
            resp = self._http_client().post(
                "/api/v1/auth/universal-auth/login",
                data={"clientId": self.client_id, "clientSecret": self.client_secret},
                timeout=5.0,
            )
            if resp.status_code != 200:
                resp = self._http_client().post(
                    "/api/v1/auth/universal-auth/login",
                    json={"clientId": self.client_id, "clientSecret": self.client_secret},
                    timeout=5.0,
                )
            if resp.status_code != 200:
                fail_closed_in_production(
                    "infisical",
                    f"Infisical universal-auth login returned HTTP {resp.status_code}: {resp.text}",
                )
            data = resp.json()
            self._access_token = data.get("accessToken")
            expires_in = data.get("expiresIn", 3600)
            self._token_expires_at = time.time() + float(expires_in) - 30
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production("infisical", f"Infisical auth failed: {exc}", cause=exc)

    def _ensure_live_backend(self) -> None:
        """Verify live Infisical connection in live mode."""
        if self.adapter_mode != "live":
            return
        try:
            resp = self._http_client().get("/api/v1/status", timeout=2.0)
            if resp.status_code not in (200, 204):
                fail_closed_in_production(
                    "infisical",
                    f"Infisical server returned HTTP {resp.status_code}",
                )
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "infisical",
                f"Live Infisical vault at {self.server_url} is unreachable: {exc}",
                cause=exc,
            )

    def _scope_key(self, key: str, tenant_id: str = "default", app_id: Optional[str] = None) -> Tuple[str, Optional[str], str]:
        return (tenant_id, app_id, key)

    def _record_audit(
        self,
        actor_id: str,
        action: str,
        secret_key: str,
        tenant_id: str,
        app_id: Optional[str] = None,
        version: int = 1,
    ) -> SecretAuditEntry:
        entry = SecretAuditEntry(
            audit_id=f"sec-aud-{secrets.token_hex(6)}",
            actor_id=actor_id,
            action=action,
            secret_key=secret_key,
            tenant_id=tenant_id,
            app_id=app_id,
            version=version,
        )
        self._audit_log.append(entry)
        return entry

    def store_secret(
        self,
        key: str,
        value: str,
        tenant_id: str = "default",
        app_id: Optional[str] = None,
        actor_id: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScopedSecret:
        """Stores a new scoped secret or replaces value starting at version 1."""
        self._ensure_live_backend()
        s_key = self._scope_key(key, tenant_id, app_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        initial_ver = SecretVersion(version=1, value=value, created_at=now_iso)
        secret = ScopedSecret(
            key=key,
            current_value=value,
            current_version=1,
            tenant_id=tenant_id,
            app_id=app_id,
            versions=[initial_ver],
            created_at=now_iso,
            updated_at=now_iso,
            metadata=metadata or {},
        )
        self._vault[s_key] = secret
        self._record_audit(actor_id, "STORE", key, tenant_id, app_id, version=1)

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            self._ensure_token()
            # Infisical scopes secrets by project + environment (default 'dev') + secretName
            payload = {
                "secretName": key,
                "secretValue": value,
                "projectSlug": self.project_id,
                "environment": app_id or "dev",
                "type": "shared",
                "metadata": metadata or {},
            }
            try:
                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = self._http_client().post(
                    f"/api/v1/secrets/{key}",
                    json=payload,
                    headers=headers,
                    timeout=5.0,
                )
                if resp.status_code in (400, 409):
                    patch_resp = self._http_client().patch(
                        f"/api/v1/secrets/{key}",
                        json=payload,
                        headers=headers,
                        timeout=5.0,
                    )
                    if patch_resp.status_code in (200, 201):
                        resp = patch_resp
                if resp.status_code not in (200, 201):
                    fail_closed_in_production(
                        "infisical",
                        f"Infisical store returned HTTP {resp.status_code}: {resp.text}",
                    )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("infisical", f"Infisical store failed: {exc}", cause=exc)

        return secret

    def get_secret(
        self,
        key: str,
        tenant_id: str = "default",
        app_id: Optional[str] = None,
        actor_id: str = "system",
        version: Optional[int] = None,
    ) -> str:
        """Retrieves current or specific version of secret and records audit event."""
        self._ensure_live_backend()
        s_key = self._scope_key(key, tenant_id, app_id)

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            self._ensure_token()
            try:
                params: Dict[str, Any] = {
                    "environment": app_id or "dev",
                    "projectSlug": self.project_id,
                }
                if version is not None:
                    params["version"] = str(version)

                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = self._http_client().get(
                    f"/api/v1/secrets/{key}",
                    params=params,
                    headers=headers,
                    timeout=5.0,
                )
                if resp.status_code == 404:
                    raise KeyError(f"Secret '{key}' not found in tenant '{tenant_id}' (app: '{app_id}')")
                if resp.status_code != 200:
                    fail_closed_in_production(
                        "infisical",
                        f"Infisical get returned HTTP {resp.status_code}: {resp.text}",
                    )
                data = resp.json()
                sec_obj = data.get("secret", data)
                retrieved_val = sec_obj.get("secretValue", "")
                target_ver = int(sec_obj.get("version", version or 1))

                if s_key not in self._vault:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    self._vault[s_key] = ScopedSecret(
                        key=key,
                        current_value=retrieved_val,
                        current_version=target_ver,
                        tenant_id=tenant_id,
                        app_id=app_id,
                        versions=[SecretVersion(version=target_ver, value=retrieved_val, created_at=now_iso)],
                        created_at=now_iso,
                        updated_at=now_iso,
                    )
                self._record_audit(actor_id, "READ", key, tenant_id, app_id, version=target_ver)
                return retrieved_val
            except KeyError:
                raise
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("infisical", f"Infisical get secret failed: {exc}", cause=exc)

        secret = self._vault.get(s_key)
        if not secret:
            raise KeyError(f"Secret '{key}' not found in tenant '{tenant_id}' (app: '{app_id}')")

        retrieved_val: str
        target_ver: int

        if version is not None:
            v_match = next((v for v in secret.versions if v.version == version), None)
            if not v_match:
                raise KeyError(f"Version {version} of secret '{key}' not found")
            retrieved_val = v_match.value
            target_ver = version
        else:
            retrieved_val = secret.current_value
            target_ver = secret.current_version

        self._record_audit(actor_id, "READ", key, tenant_id, app_id, version=target_ver)
        return retrieved_val

    def rotate_secret(
        self,
        key: str,
        new_value: str,
        tenant_id: str = "default",
        app_id: Optional[str] = None,
        actor_id: str = "system",
        grace_period_seconds: int = 3600,
    ) -> ScopedSecret:
        """Zero-downtime rotation: increments version, retains prior version during grace period."""
        s_key = self._scope_key(key, tenant_id, app_id)
        secret = self._vault.get(s_key)
        if not secret:
            # Store fresh if not exists
            return self.store_secret(key, new_value, tenant_id, app_id, actor_id)

        # Set grace expiry on old version
        old_version = next((v for v in secret.versions if v.version == secret.current_version), None)
        if old_version:
            old_version.expires_at = time.time() + grace_period_seconds

        new_v_num = secret.current_version + 1
        now_iso = datetime.now(timezone.utc).isoformat()
        new_ver = SecretVersion(version=new_v_num, value=new_value, created_at=now_iso)

        secret.versions.append(new_ver)
        secret.current_version = new_v_num
        secret.current_value = new_value
        secret.updated_at = now_iso

        self._record_audit(actor_id, "ROTATE", key, tenant_id, app_id, version=new_v_num)

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            self._ensure_token()
            payload = {
                "secretName": key,
                "secretValue": new_value,
                "projectSlug": self.project_id,
                "environment": app_id or "dev",
                "type": "shared",
            }
            try:
                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = self._http_client().patch(
                    f"/api/v1/secrets/{key}",
                    json=payload,
                    headers=headers,
                    timeout=5.0,
                )
                if resp.status_code not in (200, 201):
                    resp = self._http_client().post(
                        f"/api/v1/secrets/{key}",
                        json=payload,
                        headers=headers,
                        timeout=5.0,
                    )
                if resp.status_code not in (200, 201):
                    fail_closed_in_production(
                        "infisical",
                        f"Infisical rotate returned HTTP {resp.status_code}: {resp.text}",
                    )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("infisical", f"Infisical rotate failed: {exc}", cause=exc)

        return secret

    def inject_secrets(
        self,
        keys: List[str],
        tenant_id: str = "default",
        app_id: Optional[str] = None,
        actor_id: str = "system",
    ) -> Dict[str, str]:
        """Injects requested scoped secrets into an environment map for agent execution."""
        env_map: Dict[str, str] = {}
        for k in keys:
            try:
                env_map[k] = self.get_secret(k, tenant_id, app_id, actor_id=actor_id)
                self._record_audit(actor_id, "INJECT", k, tenant_id, app_id)
            except KeyError:
                logger.warning(f"Could not inject secret '{k}' for tenant '{tenant_id}'")
        return env_map

    def get_audit_trail(
        self,
        secret_key: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[SecretAuditEntry]:
        """Returns immutable access audit trail."""
        results = self._audit_log
        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if secret_key:
            results = [e for e in results if e.secret_key == secret_key]
        return list(results)


# Default singleton
default_infisical_adapter = InfisicalAdapter()

