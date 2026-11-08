"""
Paired Device Registry and Session Authorization Governor.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional
from remote_access.core.models import DeviceRegistration, DeviceStatus


class PairedDeviceRegistry:
    """Stores paired device credentials and enforces access revocation."""

    def __init__(self):
        self._devices: Dict[str, DeviceRegistration] = {}

    def register(self, device: DeviceRegistration) -> None:
        self._devices[device.device_id] = device

    def get(self, device_id: str) -> Optional[DeviceRegistration]:
        return self._devices.get(device_id)

    def is_authorized(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        return device.status == DeviceStatus.ACTIVE

    def touch(self, device_id: str) -> None:
        device = self._devices.get(device_id)
        if device and device.status == DeviceStatus.ACTIVE:
            device.last_seen_at = time.time()

    def revoke(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        device.status = DeviceStatus.REVOKED
        return True

    def list_devices(self, status: Optional[DeviceStatus] = None) -> List[DeviceRegistration]:
        devices = list(self._devices.values())
        if status:
            devices = [d for d in devices if d.status == status]
        return sorted(devices, key=lambda d: d.paired_at, reverse=True)
