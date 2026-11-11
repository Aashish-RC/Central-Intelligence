"""Tests for S3ObjectStore (L15 Features 15.15-15.18)."""

from __future__ import annotations

import pytest

from platform_infra.data.storage.object_store import (
    LifecyclePolicy,
    ObjectStorageError,
    S3ObjectStore,
)


def test_multipart_upload_tenant_encryption_and_lifecycle() -> None:
    store = S3ObjectStore(master_key=b"test-master-key-bytes-32-chars!!")

    upload_id = store.initiate_multipart_upload("artifacts", "big.bin", tenant_id="tenant-a")
    store.upload_part(upload_id, 2, b"-second-half")
    store.upload_part(upload_id, 1, b"first-half")
    obj = store.complete_multipart_upload(upload_id)

    assert obj.size_bytes == len(b"first-half-second-half")
    assert store.get_object("artifacts", "big.bin", tenant_id="tenant-a") == b"first-half-second-half"

    with pytest.raises(ObjectStorageError):
        store.get_object("artifacts", "big.bin", tenant_id="tenant-b")

    store.put_object("logs", "old.log", b"log", tenant_id="tenant-a", created_at=0.0)
    store.set_lifecycle_policy("logs", LifecyclePolicy(archive_after_days=7, expire_after_days=30))
    summary = store.apply_lifecycle(now=10 * 86400.0)
    assert summary == {"archived": 1, "expired": 0}
    summary2 = store.apply_lifecycle(now=35 * 86400.0)
    assert summary2 == {"archived": 0, "expired": 1}

