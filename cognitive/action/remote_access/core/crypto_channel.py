"""End-to-End Encrypted Channel using ChaCha20-Poly1305 and HKDF key derivation."""

from __future__ import annotations

import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305, AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from remote_access.core.models import EncryptedFrame


class E2EEncryptedChannel:
    """Provides authenticated end-to-end encryption for remote access frames using ChaCha20-Poly1305."""

    def __init__(self, shared_secret: bytes, cipher: str = "chacha20"):
        # Derive 32-byte key via HKDF-SHA256
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"pheonix-remote-access-v1",
            info=b"e2e-channel-key",
        )
        self._key = hkdf.derive(shared_secret)
        self.cipher_name = cipher.lower()
        if self.cipher_name == "aesgcm":
            self._cipher = AESGCM(self._key)
        else:
            self._cipher = ChaCha20Poly1305(self._key)

    def encrypt(self, payload: bytes, sender_id: str, recipient_id: str) -> EncryptedFrame:
        """Encrypts payload with 12-byte random nonce and authenticated additional data (AAD)."""
        nonce = os.urandom(12)
        aad = f"{sender_id}:{recipient_id}".encode("utf-8")
        ciphertext = self._cipher.encrypt(nonce, payload, aad)

        return EncryptedFrame(
            sender_id=sender_id,
            recipient_id=recipient_id,
            iv_nonce=nonce.hex(),
            ciphertext=ciphertext.hex(),
        )

    def decrypt(self, frame: EncryptedFrame) -> bytes:
        """Decrypts and authenticates frame using ChaCha20-Poly1305."""
        nonce = bytes.fromhex(frame.iv_nonce)
        ciphertext = bytes.fromhex(frame.ciphertext)
        aad = f"{frame.sender_id}:{frame.recipient_id}".encode("utf-8")

        try:
            return self._cipher.decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ValueError(f"Failed to decrypt frame: cryptographic authentication failed ({exc})")
