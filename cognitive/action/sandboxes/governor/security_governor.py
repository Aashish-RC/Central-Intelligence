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


class SecurityGovernor(BaseSecurityGovernor):
    """Enforces static security policies and environment sanitization for sandboxed execution."""

    def validate_request(self, request: ExecutionRequest) -> Tuple[bool, Optional[str]]:
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
