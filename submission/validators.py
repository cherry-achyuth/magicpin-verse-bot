# Post-LLM validation and repair layer.
# Inspects composed messages to catch forbidden raw URLs, multiple CTAs,
# misplaced CTAs, duplicate messages, and ungrounded numbers or facts.

from __future__ import annotations

from difflib import SequenceMatcher
import json
import re
from typing import Any, Dict, List, Optional, Tuple


def check_no_raw_urls(body: str) -> Tuple[bool, str]:
    # Meta policy rejects raw URLs in messages; we strictly forbid http/https/www links.
    url_pattern = r"(https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.(?:com|in|org|net|co|io)\b)"
    match = re.search(url_pattern, body)
    if match:
        return False, f"Contains raw URL: {match.group(0)}"
    return True, ""


def clean_raw_urls(body: str) -> str:
    # Strips any raw URL references from the message body text.
    url_pattern = r"(https?://\S+|www\.\S+)"
    return re.sub(url_pattern, "", body).strip()


def check_single_cta(body: str) -> Tuple[bool, str]:
    # Ensures there is at most one question mark or call-to-action in the message.
    question_count = body.count("?")
    if question_count > 1:
        return False, f"Contains {question_count} questions/CTAs (max allowed is 1)"
    return True, ""


def check_cta_position(body: str) -> Tuple[bool, str]:
    # Checks if the question/CTA lands in the last or second-to-last sentence.
    if "?" not in body:
        return True, ""

    sentences = [s.strip() for s in re.split(r"[.!]\s+|\n+", body) if s.strip()]
    if not sentences:
        return True, ""

    last_two = " ".join(sentences[-2:])
    if "?" not in last_two:
        return False, "CTA question mark is not near the end of the message"
    return True, ""


def check_anti_repetition(
    body: str, prior_bodies: List[str], threshold: float = 0.82
) -> Tuple[bool, str]:
    # Prevents repeating identical or nearly identical messages to the same merchant.
    body_clean = body.strip().lower()
    for prior in prior_bodies:
        prior_clean = prior.strip().lower()
        if body_clean == prior_clean:
            return False, "Exact match with a previously sent message"

        ratio = SequenceMatcher(None, body_clean, prior_clean).ratio()
        if ratio >= threshold:
            return False, f"Near-duplicate of prior message ({int(ratio*100)}% similarity)"

    return True, ""


def extract_numbers(text: str) -> List[str]:
    # Extracts all numeric sequences and percentages from text for ground-truth matching.
    return re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?%?", text)


def check_no_fabrication(
    body: str,
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    # Verifies that numbers and percentages in the message appear in the provided contexts.
    body_nums = extract_numbers(body)
    if not body_nums:
        return True, ""

    context_str = (
        f"{json.dumps(category)} {json.dumps(merchant)} {json.dumps(trigger)} {json.dumps(customer) if customer else ''}"
    )

    # Standard conversational numbers that are always allowed (slot options, standard windows)
    allowed_standard_nums = {
        "1", "2", "3", "4", "5", "6", "7", "10", "12", "14", "24", "30", "60", "90", "180", "365", "2026", "2025"
    }

    # Extract all numbers from context
    ctx_numbers = set(extract_numbers(context_str))
    # Also add percentage equivalents (e.g. 0.18 -> 18%, 0.05 -> 5%)
    for n in list(ctx_numbers):
        try:
            val = float(n.replace("%", "").replace(",", ""))
            if 0 < val < 1:
                pct_val = round(val * 100, 1)
                pct_str = f"{int(pct_val)}" if pct_val.is_integer() else f"{pct_val}"
                ctx_numbers.add(pct_str)
                ctx_numbers.add(f"{pct_str}%")
        except ValueError:
            pass

    unsupported = []
    for num in body_nums:
        clean_num = num.replace("%", "").replace(",", "").strip()
        if clean_num in allowed_standard_nums:
            continue

        if (
            clean_num not in context_str
            and num not in context_str
            and clean_num not in ctx_numbers
            and num not in ctx_numbers
        ):
            unsupported.append(num)

    if unsupported:
        return False, f"Fabricated numbers not found in context: {', '.join(unsupported)}"
    return True, ""


def validate_message(
    body: str,
    cta: str,
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
    prior_bodies: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    # Runs all validation checks against a generated body text.
    reasons = []

    ok, reason = check_no_raw_urls(body)
    if not ok:
        reasons.append(reason)

    ok, reason = check_single_cta(body)
    if not ok:
        reasons.append(reason)

    ok, reason = check_cta_position(body)
    if not ok:
        reasons.append(reason)

    if prior_bodies:
        ok, reason = check_anti_repetition(body, prior_bodies)
        if not ok:
            reasons.append(reason)

    ok, reason = check_no_fabrication(
        body, category, merchant, trigger, customer
    )
    if not ok:
        reasons.append(reason)

    return len(reasons) == 0, reasons
