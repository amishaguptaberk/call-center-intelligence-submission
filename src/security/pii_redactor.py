import re

from src.graph.state import PIIRedactionResult

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "SSN": re.compile(r"(?<!\d)(?:\d{3}[\s-]\d{2}[\s-]\d{4}|\d{9})(?!\d)"),
    "CREDIT_CARD": re.compile(
        r"(?<!\d)(?:\d{13,19}|\d{4}(?:[\s-]\d{4}){3}|\d{4}[\s-]\d{6}[\s-]\d{5}|\d{4}[\s-]\d{4}[\s-]\d{5})(?!\d)"
    ),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "PHONE": re.compile(
        r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    ),
}


def _matches(text: str) -> list[tuple[int, int, str]]:
    matches: list[tuple[int, int, str]] = []
    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            matches.append((match.start(), match.end(), pii_type))

    matches.sort(key=lambda m: (m[0], -m[1]))

    filtered: list[tuple[int, int, str]] = []
    for start, end, pii_type in matches:
        if filtered and start < filtered[-1][1]:
            continue
        filtered.append((start, end, pii_type))

    return filtered


def redact_pii(text: str) -> PIIRedactionResult:
    filtered = _matches(text)
    redacted_text = text
    for start, end, pii_type in reversed(filtered):
        redacted_text = redacted_text[:start] + f"[REDACTED_{pii_type}]" + redacted_text[end:]

    return PIIRedactionResult(
        redacted_text=redacted_text,
        pii_found=bool(filtered),
    )


def redact_segments(texts: list[str]) -> tuple[list[str], bool]:
    spans = _matches("\n".join(texts))
    output = []
    offset = 0
    for original in texts:
        value = original
        for start, end, kind in reversed(spans):
            left, right = max(start - offset, 0), min(end - offset, len(original))
            if left < right:
                placeholder = f"[REDACTED_{kind}]" if start >= offset else ""
                value = value[:left] + placeholder + value[right:]
        output.append(value)
        offset += len(original) + 1
    return output, bool(spans)
