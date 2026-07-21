"""
PII / secrets pattern scanner for governance.

Why this exists:
- Detects common sensitive tokens before prompts reach LLM providers.
- Supports deny (block) and redact modes via policy category lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Category codes used in PolicyRules.pii_*_categories
PII_CATEGORIES: tuple[str, ...] = (
    "ssn",
    "email",
    "phone",
    "credit_card",
    "aws_key",
    "api_key",
    "private_key",
)

_CATEGORY_SET = frozenset(PII_CATEGORIES)


@dataclass(frozen=True)
class PiiFinding:
    category: str
    label: str
    start: int
    end: int


# Order matters for overlapping matches — longer / more specific first where needed.
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "private_key",
        "PEM private key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
    (
        "aws_key",
        "AWS access key id",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    (
        "api_key",
        "API key / secret token",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_\-]{20,}|sk-proj-[A-Za-z0-9_\-]{20,}|"
            r"gsk_[A-Za-z0-9]{20,}|agk_[A-Za-z0-9_\-]{20,}|"
            r"xox[baprs]-[A-Za-z0-9\-]{10,}|"
            r"ghp_[A-Za-z0-9]{20,}|"
            r"AIza[0-9A-Za-z\-_]{20,})\b"
        ),
    ),
    (
        "ssn",
        "US Social Security number",
        re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
    ),
    (
        "credit_card",
        "Payment card number",
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    ),
    (
        "email",
        "Email address",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "phone",
        "Phone number",
        re.compile(
            r"(?<!\w)(?:\+?1[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?)\d{3}[\s\-.]?\d{4}(?!\w)"
        ),
    ),
]


def _luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def normalize_pii_categories(categories: list[str] | None) -> list[str]:
    if not categories:
        return []
    out: list[str] = []
    for raw in categories:
        key = raw.strip().lower()
        if key in _CATEGORY_SET and key not in out:
            out.append(key)
    return out


def scan_pii(text: str, *, categories: list[str] | None = None) -> list[PiiFinding]:
    """Return non-overlapping findings (left-to-right, first match wins)."""
    if not text:
        return []
    wanted = set(normalize_pii_categories(categories)) if categories else set(PII_CATEGORIES)
    if not wanted:
        return []

    candidates: list[PiiFinding] = []
    for category, label, pattern in _PATTERNS:
        if category not in wanted:
            continue
        for match in pattern.finditer(text):
            if category == "credit_card":
                digits = re.sub(r"\D", "", match.group(0))
                if not _luhn_ok(digits):
                    continue
            candidates.append(
                PiiFinding(
                    category=category,
                    label=label,
                    start=match.start(),
                    end=match.end(),
                )
            )

    candidates.sort(key=lambda f: (f.start, -(f.end - f.start)))
    selected: list[PiiFinding] = []
    cursor = 0
    for finding in candidates:
        if finding.start < cursor:
            continue
        selected.append(finding)
        cursor = finding.end
    return selected


def redact_pii(text: str, categories: list[str]) -> tuple[str, list[PiiFinding]]:
    """Replace matched spans with [REDACTED:<category>] placeholders."""
    cats = normalize_pii_categories(categories)
    findings = scan_pii(text, categories=cats)
    if not findings:
        return text, []

    parts: list[str] = []
    last = 0
    for finding in findings:
        parts.append(text[last : finding.start])
        parts.append(f"[REDACTED:{finding.category}]")
        last = finding.end
    parts.append(text[last:])
    return "".join(parts), findings
