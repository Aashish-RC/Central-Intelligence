"""
Hyperswitch Universal Payment Router Adapter (Layer 13: Feature 13.13).

Provides quarantined REST integration with Juspay Hyperswitch (Apache-2.0):
- Routes payments across Stripe, PayPal, Adyen, and global card processors.
- Handles payment intents, confirmations, and refunds.
- Webhook signature validation (HMAC-SHA256) & replay protection.
- Thread-safe concurrency control & durable SQLite/ACID idempotency.
- Seamlessly settles Lago subscription invoices by linking payment receipts to invoice IDs.
- Provides robust hermetic in-memory fallback for offline and continuous testing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from uuid import uuid4

import httpx

from control.billing.models import BillingInvoice
from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.billing.payments.hyperswitch")


class PaymentStatus(str, Enum):
    SUCCEEDED = "succeeded"
    REQUIRES_CUSTOMER_ACTION = "requires_customer_action"
    PROCESSING = "processing"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    CARD = "card"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"


@dataclass
class PaymentIntent:
    """Standardized representation of a payment transaction routed through Hyperswitch."""
    payment_id: str
    amount_cents: int
    currency: str = "USD"
    customer_id: str = "cust_default"
    status: PaymentStatus = PaymentStatus.SUCCEEDED
    payment_method: PaymentMethod = PaymentMethod.CARD
    gateway: str = "stripe"  # 'stripe', 'paypal', 'adyen', etc.
    invoice_id: Optional[str] = None
    client_secret: str = field(default_factory=lambda: f"hs_sec_{secrets.token_urlsafe(16)}")
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    refunded_cents: int = 0
    idempotency_key: Optional[str] = None


@dataclass
class RefundRecord:
    """Standardized representation of a payment refund."""
    refund_id: str
    payment_id: str
    amount_cents: int
    reason: str
    status: str = "succeeded"
    created_at: float = field(default_factory=time.time)


class HyperswitchAdapter:
    """
    Quarantined REST adapter for Hyperswitch universal payment gateway router.
    Features durable ACID idempotency, replay-resistant webhook verification,
    and thread-safe payment/refund concurrency.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        lago_adapter: Optional[Any] = None,
        _defer_prod_check: bool = False,
        db_path: Optional[str] = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or "hs_test_key_central_intelligence"
        self.webhook_secret = webhook_secret or os.getenv("HYPERSWITCH_WEBHOOK_SECRET", "hs_whsec_central_intelligence")
        self._lago = lago_adapter
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("hyperswitch")
        )
        self.db_path = db_path or os.getenv("HYPERSWITCH_DB_PATH")

        self._lock = threading.RLock()
        self._payments: Dict[str, PaymentIntent] = {}
        self._refunds: Dict[str, RefundRecord] = {}
        self._idempotency_records: Dict[str, PaymentIntent] = {}
        self._processed_events: Set[str] = set()

        if self.db_path:
            self._init_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        if not self.db_path:
            raise RuntimeError("Database path not configured")
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self) -> None:
        """Initializes durable SQLite schema and hydrates memory cache."""
        with self._lock:
            if self.db_path and self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS payment_intents (
                        payment_id TEXT PRIMARY KEY,
                        amount_cents INTEGER NOT NULL,
                        currency TEXT NOT NULL,
                        customer_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payment_method TEXT NOT NULL,
                        gateway TEXT NOT NULL,
                        invoice_id TEXT,
                        client_secret TEXT,
                        created_at REAL NOT NULL,
                        metadata TEXT,
                        refunded_cents INTEGER DEFAULT 0,
                        idempotency_key TEXT UNIQUE
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS refund_records (
                        refund_id TEXT PRIMARY KEY,
                        payment_id TEXT NOT NULL,
                        amount_cents INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS webhook_events (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT,
                        payment_id TEXT,
                        status TEXT,
                        processed_at REAL NOT NULL
                    )
                """)
                conn.commit()

                # Hydrate in-memory indexes from SQLite
                cur = conn.execute("SELECT * FROM payment_intents")
                for r in cur.fetchall():
                    meta = json.loads(r["metadata"]) if r["metadata"] else {}
                    p = PaymentIntent(
                        payment_id=r["payment_id"],
                        amount_cents=r["amount_cents"],
                        currency=r["currency"],
                        customer_id=r["customer_id"],
                        status=PaymentStatus(r["status"]),
                        payment_method=PaymentMethod(r["payment_method"]),
                        gateway=r["gateway"],
                        invoice_id=r["invoice_id"],
                        client_secret=r["client_secret"] or "",
                        created_at=r["created_at"],
                        metadata=meta,
                        refunded_cents=r["refunded_cents"],
                        idempotency_key=r["idempotency_key"],
                    )
                    self._payments[p.payment_id] = p
                    if p.idempotency_key:
                        self._idempotency_records[p.idempotency_key] = p

                cur = conn.execute("SELECT * FROM refund_records")
                for r in cur.fetchall():
                    rf = RefundRecord(
                        refund_id=r["refund_id"],
                        payment_id=r["payment_id"],
                        amount_cents=r["amount_cents"],
                        reason=r["reason"],
                        status=r["status"],
                        created_at=r["created_at"],
                    )
                    self._refunds[rf.refund_id] = rf

                cur = conn.execute("SELECT event_id FROM webhook_events")
                for r in cur.fetchall():
                    self._processed_events.add(r["event_id"])

    def _persist_payment(self, intent: PaymentIntent) -> None:
        if not self.db_path:
            return
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO payment_intents (
                    payment_id, amount_cents, currency, customer_id, status,
                    payment_method, gateway, invoice_id, client_secret,
                    created_at, metadata, refunded_cents, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(payment_id) DO UPDATE SET
                    status=excluded.status,
                    refunded_cents=excluded.refunded_cents,
                    metadata=excluded.metadata
            """, (
                intent.payment_id,
                intent.amount_cents,
                intent.currency,
                intent.customer_id,
                intent.status.value,
                intent.payment_method.value,
                intent.gateway,
                intent.invoice_id,
                intent.client_secret,
                intent.created_at,
                json.dumps(intent.metadata),
                intent.refunded_cents,
                intent.idempotency_key,
            ))
            conn.commit()

    def _persist_refund(self, record: RefundRecord) -> None:
        if not self.db_path:
            return
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO refund_records (
                    refund_id, payment_id, amount_cents, reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.refund_id,
                record.payment_id,
                record.amount_cents,
                record.reason,
                record.status,
                record.created_at,
            ))
            conn.commit()

    def _persist_webhook_event(self, event_id: str, event_type: str, payment_id: str, status: str) -> None:
        if not self.db_path:
            return
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO webhook_events (
                    event_id, event_type, payment_id, status, processed_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (event_id, event_type, payment_id, status, time.time()))
            conn.commit()

    def _get_lago(self) -> Any:
        if self._lago is None:
            try:
                from control.billing.engine.lago_adapter import default_lago_adapter
                self._lago = default_lago_adapter
            except ImportError:
                pass
        return self._lago

    def create_payment(
        self,
        amount_cents: int,
        currency: str = "USD",
        customer_id: str = "cust_default",
        invoice_id: Optional[str] = None,
        gateway: str = "stripe",
        payment_method: PaymentMethod = PaymentMethod.CARD,
        confirm: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> PaymentIntent:
        """
        Creates and processes a payment intent routed through Hyperswitch (Feature 13.13).
        Thread-safe and durable: if idempotency_key is provided, returns existing intent across restarts.
        """
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_records:
                logger.info("Idempotent payment match for key '%s'; returning existing payment intent", idempotency_key)
                return self._idempotency_records[idempotency_key]

            payment_id = f"pay_{secrets.token_hex(8)}"
            is_live = (self.adapter_mode == "live")

            intent = PaymentIntent(
                payment_id=payment_id,
                amount_cents=amount_cents,
                currency=currency.upper(),
                customer_id=customer_id,
                status=PaymentStatus.PROCESSING,
                payment_method=payment_method,
                gateway=gateway,
                invoice_id=invoice_id,
                metadata=metadata or {},
                idempotency_key=idempotency_key,
            )

            if is_live:
                try:
                    headers = {"api-key": self.api_key, "Content-Type": "application/json"}
                    if idempotency_key:
                        headers["idempotency-key"] = idempotency_key

                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(
                            f"{self.api_url}/payments",
                            headers=headers,
                            json={
                                "amount": amount_cents,
                                "currency": currency.upper(),
                                "customer_id": customer_id,
                                "confirm": confirm,
                                "capture_method": "automatic",
                                "metadata": {"invoice_id": invoice_id, "gateway": gateway},
                            },
                        )

                    if resp.status_code not in (200, 201):
                        intent.status = PaymentStatus.FAILED
                        self._payments[intent.payment_id] = intent
                        if idempotency_key:
                            self._idempotency_records[idempotency_key] = intent
                        self._persist_payment(intent)
                        raise ProductionSafetyError(
                            f"hyperswitch adapter payment API returned HTTP {resp.status_code}: {resp.text}"
                        )

                    try:
                        data = resp.json()
                    except Exception as json_err:
                        intent.status = PaymentStatus.FAILED
                        self._payments[intent.payment_id] = intent
                        if idempotency_key:
                            self._idempotency_records[idempotency_key] = intent
                        self._persist_payment(intent)
                        raise ProductionSafetyError(
                            "hyperswitch adapter returned malformed non-JSON response"
                        ) from json_err

                    intent.payment_id = data.get("payment_id", payment_id)
                    intent.client_secret = data.get("client_secret", intent.client_secret)

                    raw_status = str(data.get("status", "")).strip().lower()
                    if raw_status == "succeeded":
                        intent.status = PaymentStatus.SUCCEEDED
                    elif raw_status in ("requires_customer_action", "processing"):
                        intent.status = PaymentStatus.PROCESSING
                    elif raw_status == "cancelled":
                        intent.status = PaymentStatus.CANCELLED
                    else:
                        intent.status = PaymentStatus.FAILED

                    if intent.status != PaymentStatus.SUCCEEDED:
                        self._payments[intent.payment_id] = intent
                        if idempotency_key:
                            self._idempotency_records[idempotency_key] = intent
                        self._persist_payment(intent)
                        logger.warning(
                            "Hyperswitch live payment %s was not successful (status: %s)",
                            intent.payment_id,
                            intent.status.value,
                        )
                        return intent

                except ProductionSafetyError:
                    raise
                except Exception as exc:
                    intent.status = PaymentStatus.FAILED
                    self._payments[intent.payment_id] = intent
                    if idempotency_key:
                        self._idempotency_records[idempotency_key] = intent
                    self._persist_payment(intent)
                    raise ProductionSafetyError(
                        f"hyperswitch adapter live payment execution failed: {exc}"
                    ) from exc
            else:
                # Hermetic simulation
                intent.status = PaymentStatus.SUCCEEDED if confirm else PaymentStatus.PROCESSING

            self._payments[intent.payment_id] = intent
            if idempotency_key:
                self._idempotency_records[idempotency_key] = intent
            self._persist_payment(intent)

            if invoice_id and intent.status == PaymentStatus.SUCCEEDED:
                self._settle_lago_invoice(invoice_id, intent)

            logger.info(
                "Hyperswitch processed payment %s for $%.2f via %s (Invoice: %s, Status: %s)",
                intent.payment_id,
                intent.amount_cents / 100.0,
                gateway,
                invoice_id,
                intent.status.value,
            )
            return intent

    def process_invoice_payment(
        self,
        invoice: BillingInvoice,
        gateway: str = "stripe",
        payment_method: PaymentMethod = PaymentMethod.CARD,
    ) -> PaymentIntent:
        """
        Processes a payment specifically for a Lago BillingInvoice.
        Marks the invoice as paid upon successful execution.
        """
        intent = self.create_payment(
            amount_cents=invoice.amount_cents,
            currency=invoice.currency,
            customer_id=invoice.customer_id,
            invoice_id=invoice.invoice_id,
            gateway=gateway,
            payment_method=payment_method,
            confirm=True,
            metadata={"tenant_id": invoice.tenant_id},
        )
        if intent.status == PaymentStatus.SUCCEEDED:
            invoice.status = "paid"
            invoice.paid_at = datetime.now(timezone.utc).isoformat()

        return intent

    def _settle_lago_invoice(self, invoice_id: str, payment: PaymentIntent) -> None:
        """Updates invoice status in Lago adapter if present."""
        lago = self._get_lago()
        if lago and hasattr(lago, "_invoices"):
            for inv in lago._invoices:
                if inv.invoice_id == invoice_id:
                    inv.status = "paid"
                    inv.paid_at = datetime.now(timezone.utc).isoformat()
                    break

    def get_payment(self, payment_id: str) -> PaymentIntent:
        """Retrieves payment details by ID."""
        with self._lock:
            if payment_id not in self._payments:
                raise KeyError(f"Payment '{payment_id}' not found")
            return self._payments[payment_id]

    def refund_payment(
        self,
        payment_id: str,
        amount_cents: Optional[int] = None,
        reason: str = "customer_request",
    ) -> RefundRecord:
        """
        Executes a full or partial refund on a previously succeeded payment intent.
        Thread-safe: guarantees non-over-refunding under concurrency.
        """
        with self._lock:
            payment = self.get_payment(payment_id)
            refund_amount = amount_cents if amount_cents is not None else payment.amount_cents

            if refund_amount <= 0:
                raise ValueError(f"Refund amount must be positive, got {refund_amount}")

            remaining_refundable = payment.amount_cents - payment.refunded_cents
            if refund_amount > remaining_refundable:
                raise ValueError(
                    f"Refund amount {refund_amount} exceeds refundable balance {remaining_refundable}."
                )

            refund_id = f"rf_{secrets.token_hex(8)}"
            record = RefundRecord(
                refund_id=refund_id,
                payment_id=payment_id,
                amount_cents=refund_amount,
                reason=reason,
                status="succeeded",
            )

            is_live = (self.adapter_mode == "live" and os.getenv("CI_TEST_MODE") != "1")
            if is_live:
                try:
                    headers = {"api-key": self.api_key, "Content-Type": "application/json"}
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(
                            f"{self.api_url}/refunds",
                            headers=headers,
                            json={
                                "payment_id": payment_id,
                                "amount": refund_amount,
                                "reason": reason,
                            },
                        )
                    if resp.status_code not in (200, 201):
                        record.status = "failed"
                        self._refunds[refund_id] = record
                        self._persist_refund(record)
                        raise ProductionSafetyError(
                            f"hyperswitch adapter refund API returned HTTP {resp.status_code}: {resp.text}"
                        )
                except ProductionSafetyError:
                    raise
                except Exception as exc:
                    record.status = "failed"
                    self._refunds[refund_id] = record
                    self._persist_refund(record)
                    raise ProductionSafetyError(f"hyperswitch refund execution failed: {exc}") from exc

            payment.refunded_cents += refund_amount
            if payment.refunded_cents >= payment.amount_cents:
                payment.status = PaymentStatus.REFUNDED

            self._refunds[refund_id] = record
            self._persist_payment(payment)
            self._persist_refund(record)

            logger.info("Hyperswitch refunded %s for payment %s ($%.2f)", refund_id, payment_id, refund_amount / 100.0)
            return record

    def sync_payment_status(self, payment_id: str) -> PaymentIntent:
        """
        Queries remote Hyperswitch gateway to reconcile and synchronize status of a single payment (DEF-04).
        If remote state differs from local state, durable storage and caches are updated.
        """
        with self._lock:
            intent = self.get_payment(payment_id)
            is_live = (self.adapter_mode == "live" and os.getenv("CI_TEST_MODE") != "1")

            remote_status_str = None
            remote_refunded_cents = None
            if is_live:
                try:
                    headers = {"api-key": self.api_key, "Content-Type": "application/json"}
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get(f"{self.api_url}/payments/{payment_id}", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        remote_status_str = data.get("status")
                        remote_refunded_cents = data.get("amount_refunded") or data.get("refunded_cents")
                    elif resp.status_code == 404:
                        logger.warning("Payment %s not found on remote gateway", payment_id)
                    else:
                        raise ProductionSafetyError(
                            f"Remote payment query failed with HTTP {resp.status_code}: {resp.text}"
                        )
                except ProductionSafetyError:
                    raise
                except Exception as exc:
                    raise ProductionSafetyError(f"Remote payment query connection failed: {exc}") from exc
            else:
                # In simulated mode, if payment is pending/processing, resolve to succeeded
                if intent.status in (PaymentStatus.PROCESSING, PaymentStatus.REQUIRES_CUSTOMER_ACTION):
                    remote_status_str = PaymentStatus.SUCCEEDED.value

            if remote_status_str:
                new_status = PaymentStatus(remote_status_str)
                if new_status != intent.status:
                    logger.info("Reconciled payment %s status: %s -> %s", payment_id, intent.status.value, new_status.value)
                    was_succeeded = (intent.status == PaymentStatus.SUCCEEDED)
                    intent.status = new_status
                    if new_status == PaymentStatus.SUCCEEDED and intent.invoice_id and not was_succeeded:
                        self._settle_lago_invoice(intent.invoice_id, intent)
                if remote_refunded_cents is not None and remote_refunded_cents > intent.refunded_cents:
                    intent.refunded_cents = remote_refunded_cents

                self._persist_payment(intent)

            return intent

    def reconcile_remote_settlements(
        self,
        payment_ids: Optional[List[str]] = None,
        include_completed: bool = False,
    ) -> Dict[str, Any]:
        """
        Reconciles local payment records with the remote Hyperswitch payment gateway (Feature 13.13 / DEF-04).
        - Queries remote gateway for latest payment/settlement state.
        - Detects status discrepancies (e.g. processing -> succeeded or processing -> failed).
        - Safely updates durable SQLite ledger and memory cache.
        - Triggers downstream Lago invoice settlement on newly confirmed successes.
        - Resolves entitlement drift and returns structured reconciliation audit report.
        """
        with self._lock:
            targets = payment_ids if payment_ids is not None else list(self._payments.keys())
            reconciled = 0
            divergences = 0
            settled_invoices: List[str] = []
            discrepancies: List[Dict[str, Any]] = []

            for pid in targets:
                intent = self._payments.get(pid)
                if not intent:
                    continue
                # Skip already completed transactions unless explicitly requested
                if not include_completed and intent.status not in (PaymentStatus.PROCESSING, PaymentStatus.REQUIRES_CUSTOMER_ACTION) and payment_ids is None:
                    continue

                old_status = intent.status.value
                synced = self.sync_payment_status(pid)
                reconciled += 1
                if synced.status.value != old_status:
                    divergences += 1
                    discrepancies.append({
                        "payment_id": pid,
                        "old_status": old_status,
                        "new_status": synced.status.value,
                        "invoice_id": synced.invoice_id,
                    })
                    if synced.status == PaymentStatus.SUCCEEDED and synced.invoice_id:
                        settled_invoices.append(synced.invoice_id)

            return {
                "total_checked": reconciled,
                "divergences_resolved": divergences,
                "settled_invoices": settled_invoices,
                "discrepancies": discrepancies,
                "timestamp": time.time(),
            }

    def compute_webhook_signature(
        self,
        payload_bytes: bytes,
        secret: Optional[str] = None,
        timestamp: Optional[Union[str, float, int]] = None,
    ) -> str:
        """Computes HMAC-SHA256 signature for webhook payloads."""
        key = (secret or self.webhook_secret).encode("utf-8")
        if timestamp is not None:
            data = f"t={timestamp}.".encode("utf-8") + payload_bytes
            mac = hmac.new(key, data, hashlib.sha256).hexdigest()
            return f"t={timestamp},v1={mac}"
        else:
            return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature: str,
        secret: Optional[str] = None,
        tolerance_seconds: float = 300.0,
    ) -> bool:
        """
        Validates HMAC-SHA256 signature and replay tolerance.
        Supports both raw hex digest and structured `t=<timestamp>,v1=<digest>` formats.
        """
        key = (secret or self.webhook_secret).encode("utf-8")
        sig = signature.strip()

        if sig.startswith("t=") and ",v1=" in sig:
            parts = sig.split(",", 1)
            t_part = parts[0].replace("t=", "").strip()
            v1_part = parts[1].replace("v1=", "").strip()

            try:
                ts = float(t_part)
            except ValueError:
                raise ValueError("Malformed timestamp in webhook signature header")

            now = time.time()
            if abs(now - ts) > tolerance_seconds:
                raise ValueError(
                    f"Webhook timestamp expired or out of tolerance ({abs(now - ts):.1f}s > {tolerance_seconds}s)"
                )

            data = f"t={t_part}.".encode("utf-8") + payload_bytes
            expected_mac = hmac.new(key, data, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_mac, v1_part)
        else:
            expected_mac = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_mac, sig)

    def handle_webhook(
        self,
        payload: Union[Dict[str, Any], str, bytes],
        signature: Optional[str] = None,
        raw_body: Optional[bytes] = None,
        enforce_signature: bool = False,
        tolerance_seconds: float = 300.0,
    ) -> Dict[str, Any]:
        """
        Processes asynchronous settlement webhooks from Hyperswitch (Feature 13.13).
        Validates HMAC signature, prevents replay attacks, updates payment intent status,
        and safely settles linked Lago subscription invoices without double processing.
        """
        if isinstance(payload, bytes):
            payload_bytes = payload
            data = json.loads(payload.decode("utf-8"))
        elif isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = payload
            payload_bytes = raw_body or json.dumps(payload, sort_keys=True).encode("utf-8")
        else:
            raise TypeError("Unsupported payload type; must be dict, str, or bytes")

        # 1. Webhook Signature Verification
        if signature or enforce_signature:
            if not signature:
                raise ValueError("Webhook signature is required but missing")
            if not self.verify_webhook_signature(payload_bytes, signature, tolerance_seconds=tolerance_seconds):
                raise ValueError("Invalid webhook signature: HMAC-SHA256 mismatch")

        # 2. Extract Event Metadata & Replay Protection
        event_type = data.get("type") or data.get("event") or ""
        event_id = data.get("event_id") or data.get("id") or ""
        content = data.get("content") or data.get("data", {})
        payment_id = content.get("payment_id") or content.get("id") or ""

        if not payment_id:
            raise ValueError("Webhook payload missing payment_id")

        with self._lock:
            # Replay check
            if event_id and event_id in self._processed_events:
                logger.warning("Duplicate webhook event '%s' ignored (replay protection)", event_id)
                curr_status = self._payments[payment_id].status.value if payment_id in self._payments else "unknown"
                return {
                    "settled": True,
                    "duplicate": True,
                    "payment_id": payment_id,
                    "status": curr_status,
                    "invoice_settled": False,
                }

            intent = self._payments.get(payment_id)
            if not intent:
                amount_cents = int(content.get("amount", 0))
                currency = content.get("currency", "USD")
                cust_id = content.get("customer_id", "cust_default")
                inv_id = content.get("metadata", {}).get("invoice_id")
                intent = PaymentIntent(
                    payment_id=payment_id,
                    amount_cents=amount_cents,
                    currency=currency,
                    customer_id=cust_id,
                    invoice_id=inv_id,
                    status=PaymentStatus.PROCESSING,
                )
                self._payments[payment_id] = intent

            invoice_settled = False
            if event_type in ("payment_intent.succeeded", "payment.succeeded"):
                was_succeeded = (intent.status == PaymentStatus.SUCCEEDED)
                intent.status = PaymentStatus.SUCCEEDED
                if intent.invoice_id and not was_succeeded:
                    self._settle_lago_invoice(intent.invoice_id, intent)
                    invoice_settled = True
            elif event_type in ("payment_intent.failed", "payment.failed"):
                intent.status = PaymentStatus.FAILED
            elif event_type in ("payment_intent.cancelled", "payment.cancelled"):
                intent.status = PaymentStatus.CANCELLED
            elif event_type in ("refund.succeeded", "refund_intent.succeeded"):
                intent.status = PaymentStatus.REFUNDED

            if event_id:
                self._processed_events.add(event_id)
                self._persist_webhook_event(event_id, event_type, payment_id, intent.status.value)

            self._persist_payment(intent)

            return {
                "settled": True,
                "duplicate": False,
                "payment_id": payment_id,
                "status": intent.status.value,
                "invoice_settled": invoice_settled,
            }


# Global default singleton
default_hyperswitch_adapter = HyperswitchAdapter()
