"""Security Governor: Static code inspection, path traversal checks, and environment sanitization."""

import os
import re
from typing import Dict, List, Optional, Pattern, Tuple
from ..core.interfaces import BaseSecurityGovernor
from ..core.models import ExecutionRequest

BLOCKED_CODE_PATTERNS: List[Pattern] = [
    re.compile(r"\bctypes\b"),
    re.compile(r"(?:/etc/shadow|/etc/passwd|SAM|SYSTEM32[\/\\]config)", re.IGNORECASE),
    re.compile(r"(?:^|[\/\\\'\"\s])(?:\.vault_key|id_rsa|id_ed25519)(?:$|[\/\\\'\"\s])", re.IGNORECASE),
    re.compile(r"\bos\.fork\(\)"),
]

BLOCKED_NETWORK_PATTERNS: List[Pattern] = [
    re.compile(r"\bimport\s+socket\b"),
    re.compile(r"\bfrom\s+socket\s+import\b"),
    re.compile(r"\burllib\.request\b"),
    re.compile(r"\brequests\.(?:get|post|put|delete)\b"),
    re.compile(r"\bhttp\.client\b"),
]

SENSITIVE_ENV_KEYS: List[str] = [
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "AUTH",
    "DATABASE_URL",
    "PRIVATE",
]

# Hard ceiling thresholds for Feature 5.33
MAX_ALLOWED_TIMEOUT_SECONDS: float = 300.0
MAX_ALLOWED_MEMORY_MB: int = 4096
MAX_ALLOWED_OUTPUT_BYTES: int = 10 * 1024 * 1024
MAX_ALLOWED_FILES_COUNT: int = 100
MAX_ALLOWED_TOTAL_FILE_BYTES: int = 25 * 1024 * 1024


class SecurityGovernor(BaseSecurityGovernor):
    """Enforces static security policies, resource limits (Feature 5.33), and environment sanitization."""

    def validate_resource_limits(self, limits) -> Tuple[bool, Optional[str]]:
        """Validates that requested resource constraints are within allowable bounds."""
        if limits.timeout_seconds <= 0:
            return False, "timeout_seconds must be positive"
        if limits.timeout_seconds > MAX_ALLOWED_TIMEOUT_SECONDS:
            return False, f"timeout_seconds {limits.timeout_seconds} exceeds hard ceiling of {MAX_ALLOWED_TIMEOUT_SECONDS}s"

        if limits.max_memory_mb <= 0:
            return False, "max_memory_mb must be positive"
        if limits.max_memory_mb > MAX_ALLOWED_MEMORY_MB:
            return False, f"max_memory_mb {limits.max_memory_mb} exceeds hard ceiling of {MAX_ALLOWED_MEMORY_MB}MB"

        if limits.max_output_bytes <= 0:
            return False, "max_output_bytes must be positive"
        if limits.max_output_bytes > MAX_ALLOWED_OUTPUT_BYTES:
            return False, f"max_output_bytes {limits.max_output_bytes} exceeds hard ceiling of {MAX_ALLOWED_OUTPUT_BYTES} bytes"

        return True, None

    def validate_files_quota(self, files: Dict[str, str], limits) -> Tuple[bool, Optional[str]]:
        """Validates file count and aggregate byte payload for virtual filesystem."""
        if len(files) > limits.max_files_count:
            return False, f"Files count {len(files)} exceeds allowed limit of {limits.max_files_count}"

        total_bytes = 0
        for name, content in files.items():
            content_bytes = len(content.encode("utf-8"))
            if content_bytes > limits.max_file_size_bytes:
                return False, f"File '{name}' exceeds individual size limit of {limits.max_file_size_bytes} bytes"
            total_bytes += content_bytes

        if total_bytes > MAX_ALLOWED_TOTAL_FILE_BYTES:
            return False, f"Total virtual files size {total_bytes} bytes exceeds quota {MAX_ALLOWED_TOTAL_FILE_BYTES} bytes"

        return True, None

    def validate_request(self, request: ExecutionRequest) -> Tuple[bool, Optional[str]]:
        # 1. Validate requested resource bounds (Feature 5.33)
        valid_limits, limit_err = self.validate_resource_limits(request.limits)
        if not valid_limits:
            return False, f"Resource limit violation: {limit_err}"

        # 2. Validate file upload quota (Feature 5.33)
        valid_quota, quota_err = self.validate_files_quota(request.files, request.limits)
        if not valid_quota:
            return False, f"Disk quota violation: {quota_err}"

        code = request.code

        # Check blocked patterns
        for pat in BLOCKED_CODE_PATTERNS:
            if pat.search(code):
                return False, f"Code violates security policy: matched blocked pattern '{pat.pattern}'"

        # Check dangerous command patterns
        for bad in [
            "rm -rf /",
            "rm -rf --no-preserve-root",
            ":(){ :|:& };:",
            "mkfs",
            "dd if=/dev/zero",
            "chmod -R 777 /",
        ]:
            if bad in code:
                return False, f"Command blocked by sandbox security policy: '{bad}'"

        # Check network access if disabled
        if not request.limits.network_access:
            for pat in BLOCKED_NETWORK_PATTERNS:
                if pat.search(code):
                    return False, f"Network access is disabled for this sandbox: blocked '{pat.pattern}'"

        # Check virtual files for path traversal
        for filename in request.files.keys():
            if ".." in filename or filename.startswith(("/", "\\")):
                return False, f"Path traversal attempt detected in filename: '{filename}'"

        return True, None

    def sanitize_environment(
        self, allowed_vars: List[str], custom_env: Dict[str, str]
    ) -> Dict[str, str]:
        """Produces a pristine environment containing only allowed system vars and custom inputs."""
        sanitized: Dict[str, str] = {}
        for var in allowed_vars:
            val = os.environ.get(var)
            if val is not None:
                sanitized[var] = val

        # Add custom environment, masking any accidental host secrets
        for k, v in custom_env.items():
            sanitized[k] = v

        # Extra safety: strip any variable with secret markers
        for k in list(sanitized.keys()):
            upper_k = k.upper()
            if any(marker in upper_k for marker in SENSITIVE_ENV_KEYS) and k not in custom_env:
                sanitized.pop(k, None)

        return sanitized
