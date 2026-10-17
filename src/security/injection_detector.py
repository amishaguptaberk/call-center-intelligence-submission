import re

from src.graph.state import InjectionScanResult

# (regex, name). Call-center phrasing like "ignore the previous charge" must not match.
INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\bignore\b.{0,40}\bprevious\b.{0,20}\b(?:instructions|prompts?|rules|directions|commands|context)\b",
            re.IGNORECASE,
        ),
        "ignore_previous",
    ),
    (
        re.compile(
            r"\bignore\b.{0,40}\bprior\b.{0,20}\b(?:instructions|prompts?|rules|directions|commands|context)\b",
            re.IGNORECASE,
        ),
        "ignore_prior",
    ),
    (
        re.compile(
            r"\bdisregard\b.{0,40}\bprior\b.{0,20}\b(?:instructions|prompts?|rules|directions|commands|context)\b",
            re.IGNORECASE,
        ),
        "disregard_prior",
    ),
    (
        re.compile(
            r"\bforget\b.{0,40}\bprevious\b.{0,20}\b(?:instructions|prompts?|rules|directions|commands|context)\b",
            re.IGNORECASE,
        ),
        "forget_previous",
    ),
    (
        re.compile(
            r"\b(?:show|print|repeat|output|display)\b.{0,40}\b(?:system prompt|hidden prompt|your (?:system )?prompt)\b",
            re.IGNORECASE,
        ),
        "prompt_leak",
    ),
    (
        re.compile(
            r"\b(?:what|which|how)\b.{0,50}\b(?:system prompt|hidden instructions|your instructions)\b",
            re.IGNORECASE,
        ),
        "prompt_leak_question",
    ),
    (
        re.compile(
            r"(?:<\|im_start\|>\s*system|###\s*system\b|\bsystem\s*prompt\s*:)",
            re.IGNORECASE,
        ),
        "system_prompt_inject",
    ),
    (re.compile(r"<<SYS>>"), "llama_system_tag"),
    (re.compile(r"\[INST\]"), "llama_inst_tag"),
    (re.compile(r"\[/INST\]"), "llama_inst_close_tag"),
    (
        re.compile(
            r"\b(?:you are now(?!\s+(?:speaking|connected|being|transferred|reached|talking|eligible|confirmed|all set|on hold)\b)"
            r"|act as(?!\s+soon\b)(?!\s+your\s+point of contact\b)(?!\s+(?:a|the)\s+(?:liaison|reference)\b)"
            r"|pretend (?:to be|you are)"
            r"|from now on you are)\b",
            re.IGNORECASE,
        ),
        "role_switch",
    ),
    (re.compile(r"\bnew instructions\b", re.IGNORECASE), "new_instructions"),
    (re.compile(r"\bDAN\b|(?i:\bdo anything now\b)"), "dan_mode"),
    (re.compile(r"\bjailbreak\b", re.IGNORECASE), "jailbreak"),
    (
        re.compile(r"\boverride\b.{0,30}\bsafety\b", re.IGNORECASE),
        "override_safety",
    ),
    (
        re.compile(r"\bignore\b.{0,30}\btranscript\b", re.IGNORECASE),
        "ignore_transcript",
    ),
    (
        re.compile(
            r"(?:^|\n)\s*(?:Human|Assistant)\s*:|\bend of (?:the )?conversation\b",
            re.IGNORECASE,
        ),
        "conversation_inject",
    ),
    (
        re.compile(
            r"\b(?:i(?:'m| am) (?:your |the )?(?:developer|creator|administrator)|this is an authorized test)\b",
            re.IGNORECASE,
        ),
        "social_engineering",
    ),
    (
        re.compile(
            r"\btranslate\b.{0,80}\b(?:ignore|disregard|jailbreak|system prompt)\b",
            re.IGNORECASE,
        ),
        "translate_attack",
    ),
    (re.compile(r"\bignore\b.{0,30}\bsafety\b", re.IGNORECASE), "ignore_safety"),
    (
        re.compile(
            r"\b(?:system override|override (?:the |your )?system)\b",
            re.IGNORECASE,
        ),
        "system_override",
    ),
    (
        re.compile(
            r"\breveal\b.{0,40}\b(?:system prompt|hidden prompt|your (?:instructions|prompt)|secrets?)\b",
            re.IGNORECASE,
        ),
        "reveal_attack",
    ),
]


def detect_injection(text: str) -> InjectionScanResult:
    normalized = " ".join(text.split())
    matches: list[str] = []
    for regex, name in INJECTION_PATTERNS:
        if regex.search(text) or regex.search(normalized):
            matches.append(name)
    return InjectionScanResult(
        injection_detected=bool(matches),
        matched_patterns=matches,
    )
