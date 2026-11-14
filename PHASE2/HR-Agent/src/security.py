"""Security helpers: hashing, safety IDs, and PII redaction."""
from __future__ import annotations

import hashlib
import re


def token_hash(token: str) -> str:
    """Return a deterministic SHA-256 hex digest of the raw token."""
    return hashlib.sha256(token.encode()).hexdigest()


def stable_safety_id(employee_id: str) -> str:
    """Return a stable, non-identifying hash suitable for provider safety_identifier."""
    return hashlib.sha256(f"safety:{employee_id}".encode()).hexdigest()[:16]


def redact(value: str) -> str:
    """Redact email, Indonesian phone numbers, token-like values, and medical detail."""
    # Email addresses
    value = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[EMAIL]", value)
    # Indonesian phone numbers: +62xxx, 08xxx
    value = re.sub(r"(\+62|0)\d{8,13}", "[PHONE]", value)
    # Token-like and secret strings
    value = re.sub(r"(?i)\b[A-Za-z0-9_-]*(?:token|secret|key|api)[A-Za-z0-9_-]*\b", "[REDACTED]", value)
    value = re.sub(r"\b[A-Za-z0-9_-]{20,}\b", "[REDACTED]", value)
    # Medical details and diagnosis
    value = re.sub(r"(?i)(diagnosis|diagnosa|kondisi medis|medical details?|medical condition)\s*:\s*[^;,.\n]+", "[MEDICAL]", value)
    value = re.sub(r"(?i)\b(diabetes|hipertensi|kanker|cancer|hiv|aids|covid|depresi|depression)\b", "[MEDICAL]", value)
    return value

