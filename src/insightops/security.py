"""Read-only SQL guardrails and prompt-injection controls."""

from __future__ import annotations

import re


DEFAULT_APPROVED_VIEWS = frozenset({
    "vw_control_center", "vw_quality_summary", "vw_metric_monitoring",
    "vw_anomaly_center", "vw_report_review",
})
FORBIDDEN_SQL = frozenset({
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "grant", "revoke", "copy", "execute", "call", "merge", "replace", "attach",
})
INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?(previous|prior|system)\s+instructions",
    r"reveal\s+(the\s+)?(system|developer)\s+prompt",
    r"act\s+as\s+(an?\s+)?unrestricted",
    r"bypass\s+(security|guardrails|policy)",
    r"jailbreak",
)


def strip_sql_comments(sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", without_block)


def validate_read_only_sql(sql: str, approved_views: frozenset[str] = DEFAULT_APPROVED_VIEWS, row_limit: int = 200) -> str:
    cleaned = " ".join(strip_sql_comments(sql).strip().split())
    lowered = cleaned.lower()
    if not re.match(r"^(select|with)\b", lowered):
        raise ValueError("Only SELECT or WITH queries are allowed")
    if ";" in cleaned.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")
    tokens = set(re.findall(r"\b[a-z_]+\b", lowered))
    blocked = sorted(tokens.intersection(FORBIDDEN_SQL))
    if blocked:
        raise ValueError(f"Forbidden SQL operation: {blocked[0].upper()}")
    referenced = set(re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_.]*)", lowered))
    normalized = {item.split(".")[-1] for item in referenced}
    unauthorized = sorted(normalized - set(approved_views))
    if unauthorized:
        raise ValueError(f"View is not approved for Copilot access: {unauthorized[0]}")
    if not re.search(r"\blimit\s+\d+\b", lowered):
        cleaned = cleaned.rstrip(";") + f" LIMIT {row_limit}"
    else:
        match = re.search(r"\blimit\s+(\d+)\b", lowered)
        if match and int(match.group(1)) > row_limit:
            cleaned = re.sub(r"(?i)\blimit\s+\d+\b", f"LIMIT {row_limit}", cleaned)
    return cleaned


def detect_prompt_injection(text: str) -> list[str]:
    return [pattern for pattern in INJECTION_PATTERNS if re.search(pattern, text, flags=re.I)]


def sanitize_data_text(text: str, max_length: int = 4000) -> str:
    """Treat file content as untrusted data and remove control characters."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", str(text))[:max_length]
    if detect_prompt_injection(cleaned):
        return "[UNTRUSTED_INSTRUCTION_REMOVED]"
    return cleaned


def safe_question(question: str) -> str:
    if detect_prompt_injection(question):
        raise ValueError("The question contains an instruction that conflicts with Copilot security controls")
    return sanitize_data_text(question, max_length=1000)

