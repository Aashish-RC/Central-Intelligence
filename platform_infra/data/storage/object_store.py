"""S3-Compatible Object Storage with Multipart Upload, Lifecycle Policies, and Per-Tenant Encryption (L15 Features 15.15-15.18)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from control.safety.production_guard import is_insecure_secret, is_production, require_live_adapter


class ObjectStorageError(RuntimeError):
    """Raised on invalid multipart state, lifecycle expiry, or decryption failure."""


@dataclass
class LifecyclePolicy:
    """Bucket/object retention policy (15.17)."""

    archive_after_days: Optional[int] = None
    expire_after_days: Optional[int] = None


@dataclass
class StoredObject:
    """Encrypted stored object metadata and payload."""

    bucket: str
    key: str
    tenant_id: str
    size_bytes: int
    sha256: str
    nonce: bytes
    ciphertext: bytes
    storage_class: str = "STANDARD"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class MultipartUploadSession:
    """Active multipart upload buffer."""

    upload_id: str
    bucket: str
    key: str
    tenant_id: str
    parts: Dict[int, bytes] = field(default_factory=dict)


class S3ObjectStore:
    """S3-compatible object store supporting multipart uploads, lifecycle rules, and tenant AEAD encryption."""

    def __init__(
        self,
        master_key: Optional[bytes] = None,
        endpoint_url: Optional[str] = None,
        adapter_mode: Optional[str] = None,
    ) -> None:
        self.endpoint_url = endpoint_url or os.getenv("OBJECT_STORE_ENDPOINT")
        has_live = bool(self.endpoint_url)
        if adapter_mode is not None:
            mode = adapter_mode.strip().lower()
            if is_production() and mode != "live":
                require_live_adapter("OBJECT_STORE")
            self.adapter_mode = mode
        elif has_live:
            self.adapter_mode = require_live_adapter(
                "OBJECT_STORE",
                require_credentials={"OBJECT_STORE_ENDPOINT": self.endpoint_url},
            )
        else:
            self.adapter_mode = require_live_adapter("OBJECT_STORE")
        env_secret = os.getenv("OBJECT_STORE_MASTER_KEY", "")
        if master_key is not None:
            raw_secret = master_key
        elif env_secret:
            if is_production() and is_insecure_secret(env_secret):
                raise ObjectStorageError("Insecure OBJECT_STORE_MASTER_KEY in production")
            raw_secret = env_secret.encode("utf-8")
        else:
            if is_production():
                raise ObjectStorageError(
                    "OBJECT_STORE_MASTER_KEY or explicit master_key is required in production"
                )
            raw_secret = os.urandom(32)
        self._master_key = hashlib.sha256(raw_secret).digest()
        self._objects: Dict[tuple[str, str], StoredObject] = {}
        self._uploads: Dict[str, MultipartUploadSession] = {}
        self._policies: Dict[str, LifecyclePolicy] = {}

    def _derive_tenant_key(self, tenant_id: str) -> bytes:
        return hmac.new(self._master_key, f"tenant:{tenant_id}".encode("utf-8"), hashlib.sha256).digest()

    def _encrypt(self, tenant_id: str, aad: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        aead = ChaCha20Poly1305(self._derive_tenant_key(tenant_id))
        return nonce, aead.encrypt(nonce, plaintext, aad)

    def _decrypt(self, tenant_id: str, aad: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
        aead = ChaCha20Poly1305(self._derive_tenant_key(tenant_id))
        try:
            return aead.decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ObjectStorageError("Decryption failed: tenant key mismatch or corrupted object") from exc

    def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        tenant_id: str,
        metadata: Optional[Dict[str, str]] = None,
        created_at: Optional[float] = None,
    ) -> StoredObject:
        aad = f"{tenant_id}:{bucket}/{key}".encode("utf-8")
        nonce, ciphertext = self._encrypt(tenant_id, aad, data)
        obj = StoredObject(
            bucket=bucket,
            key=key,
            tenant_id=tenant_id,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            nonce=nonce,
            ciphertext=ciphertext,
            created_at=time.time() if created_at is None else created_at,
            metadata=dict(metadata or {}),
        )
        self._objects[(bucket, key)] = obj
        return obj

    def get_object(self, bucket: str, key: str, tenant_id: str) -> bytes:
        obj = self._objects.get((bucket, key))
        if obj is None:
            raise KeyError(f"Object not found: s3://{bucket}/{key}")
        if obj.tenant_id != tenant_id:
            raise ObjectStorageError(
                f"Tenant '{tenant_id}' cannot decrypt object owned by '{obj.tenant_id}'"
            )
        aad = f"{tenant_id}:{bucket}/{key}".encode("utf-8")
        return self._decrypt(tenant_id, aad, obj.nonce, obj.ciphertext)

    def initiate_multipart_upload(self, bucket: str, key: str, tenant_id: str) -> str:
        upload_id = f"mpu-{uuid.uuid4().hex[:12]}"
        self._uploads[upload_id] = MultipartUploadSession(
            upload_id=upload_id,
            bucket=bucket,
            key=key,
            tenant_id=tenant_id,
        )
        return upload_id

    def upload_part(self, upload_id: str, part_number: int, chunk: bytes) -> None:
        session = self._uploads.get(upload_id)
        if session is None:
            raise ObjectStorageError(f"Unknown multipart upload '{upload_id}'")
        if part_number < 1:
            raise ValueError("part_number must be >= 1")
        session.parts[part_number] = chunk

    def complete_multipart_upload(self, upload_id: str) -> StoredObject:
        session = self._uploads.pop(upload_id, None)
        if session is None:
            raise ObjectStorageError(f"Unknown multipart upload '{upload_id}'")
        assembled = b"".join(session.parts[p] for p in sorted(session.parts))
        return self.put_object(session.bucket, session.key, assembled, session.tenant_id)

    def set_lifecycle_policy(self, bucket: str, policy: LifecyclePolicy) -> None:
        self._policies[bucket] = policy

    def apply_lifecycle(self, now: Optional[float] = None) -> Dict[str, int]:
        """Archive or expire objects according to configured bucket lifecycle rules."""
        cur = time.time() if now is None else now
        archived = 0
        expired = 0
        to_delete: List[tuple[str, str]] = []
        for k, obj in self._objects.items():
            policy = self._policies.get(obj.bucket)
            if not policy:
                continue
            age_days = (cur - obj.created_at) / 86400.0
            if policy.expire_after_days is not None and age_days >= policy.expire_after_days:
                to_delete.append(k)
            elif (
                policy.archive_after_days is not None
                and age_days >= policy.archive_after_days
                and obj.storage_class != "ARCHIVE"
            ):
                obj.storage_class = "ARCHIVE"
                archived += 1
        for k in to_delete:
            del self._objects[k]
            expired += 1
        return {"archived": archived, "expired": expired}

