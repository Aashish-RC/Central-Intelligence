"""Security Governor: Static code inspection, path traversal checks, and environment sanitization."""

import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Pattern, Tuple
from ..core.interfaces import BaseSecurityGovernor
from ..core.models import ExecutionRequest

BLOCKED_CODE_PATTERNS: List[Pattern] = [
    re.compile(r"\bctypes\b"),
    re.compile(r"(?:/etc/shadow|/etc/passwd|SAM|SYSTEM32[\/\\]config)", re.IGNORECASE),
    re.compile(r"(?:^|[\/\\\'\"\s])(?:\.vault_key|id_rsa|id_ed25519)(?:$|[\/\\\'\"\s])", re.IGNORECASE),
    re.compile(r"\bos\.fork\(\)"),
    re.compile(r"\b(?:nc|netcat)\b.*?-e\s+", re.IGNORECASE),
    re.compile(r"/dev/tcp/[^\s/]+/\d+", re.IGNORECASE),
    # Windows host escape & execution primitives
    re.compile(r"\b(?:cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?)\s+/(?:c|k|e|v|q)\b", re.IGNORECASE),
    re.compile(r"\b(?:powershell(?:\.exe)?|pwsh(?:\.exe)?)\b.*?(?:-enc(?:odedcommand)?|-c(?:ommand)?|-ep(?:ecutionpolicy)?\s+bypass)", re.IGNORECASE),
    re.compile(r"\b(?:wscript|cscript|mshta|rundll32|reg|vssadmin|certutil|bitsadmin)(?:\.exe)?\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdiskpart(?:\.exe)?\b", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z]:[\/\\](?:windows|winnt|programdata|system32|syswow64)|\\\\(?:localhost|127\.0\.0\.1|[^\s\/\\]+)[\/\\])", re.IGNORECASE),
    re.compile(r"(?:HKLM|HKCU|HKEY_LOCAL_MACHINE|HKEY_CURRENT_USER)[\/\\]", re.IGNORECASE),
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

# Windows reserved device names: CON, PRN, AUX, NUL, COM1-9, LPT1-9
WINDOWS_RESERVED_DEVICE_NAMES: Pattern = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE
)

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

    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, Optional[str]]:
        """Validate that a filename is safe to write inside a scratch directory."""
        if not filename or not isinstance(filename, str) or not filename.strip():
            return False, "Filename cannot be empty or whitespace only"

        # Check for null bytes or control characters
        if any(ord(c) < 32 for c in filename) or "\0" in filename:
            return False, f"Prohibited control characters in filename: '{filename}'"

        # Check for absolute unix or windows paths
        if filename.startswith(("/", "\\")) or os.path.isabs(filename):
            return False, f"Absolute path escape detected in filename: '{filename}'"

        # Check for Windows drive-letter traversal (e.g. C:foo, C:\foo, D:/foo)
        if re.match(r"^[a-zA-Z]:", filename):
            return False, f"Windows drive path escape detected in filename: '{filename}'"

        # Check for Windows UNC network share path (e.g. \\server\share or //server/share)
        if filename.startswith(("\\\\", "//")):
            return False, f"UNC network share path escape detected in filename: '{filename}'"

        # Check for NTFS Alternate Data Stream escape (e.g. file.txt:stream)
        if ":" in filename:
            return False, f"NTFS alternate data stream escape detected in filename: '{filename}'"

        # Check for relative traversal
        parts = Path(filename).parts
        if not parts:
            return False, f"Invalid filename: '{filename}'"

        for part in parts:
            if part in ("..", "."):
                return False, f"Path traversal attempt detected in filename: '{filename}'"
            if ".." in part:
                return False, f"Path traversal attempt detected in filename component: '{part}'"
            # Windows strips trailing dots and spaces, which can cause file overwrite/escape
            if part.endswith((".", " ")) or part.startswith(" "):
                return False, f"Dangerous trailing/leading whitespace or dot in filename component: '{part}'"
            # Reserved Windows device names in ANY path component (e.g. aux/foo.txt)
            stem = Path(part).stem
            if WINDOWS_RESERVED_DEVICE_NAMES.match(part) or WINDOWS_RESERVED_DEVICE_NAMES.match(stem):
                return False, f"Reserved Windows device name detected in filename component: '{part}'"

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
            "cmd.exe",
            "powershell.exe",
            "pwsh.exe",
        ]:
            if bad in code:
                return False, f"Command blocked by sandbox security policy: '{bad}'"

        # Check network access if disabled
        if not request.limits.network_access:
            for pat in BLOCKED_NETWORK_PATTERNS:
                if pat.search(code):
                    return False, f"Network access is disabled for this sandbox: blocked '{pat.pattern}'"

        # Check virtual files for path traversal & dangerous Windows paths
        for filename in request.files.keys():
            is_valid_file, file_err = self.validate_filename(filename)
            if not is_valid_file:
                return False, file_err

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
