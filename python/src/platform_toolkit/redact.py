"""Strip secrets from text before it leaves the cluster."""

from __future__ import annotations

import re

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # key=value or key: value where the key looks sensitive
    (
        re.compile(
            r"(?i)\b([\w.-]*(?:password|passwd|secret|token|apikey|api_key|access_key)[\w.-]*)"
            r"(\s*[:=]\s*)(\"?)([^\s\"',]+)"
        ),
        r"\1\2\3[REDACTED]",
    ),
    # Authorization headers
    (re.compile(r"(?i)(authorization:\s*(?:bearer|basic)\s+)\S+"), r"\1[REDACTED]"),
    # JWTs
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "[REDACTED_JWT]"),
    # PEM blocks
    (
        re.compile(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", re.DOTALL),
        "[REDACTED_PEM]",
    ),
    # AWS access key ids
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
]


def redact(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
