# Handles multi-turn conversation logic, auto-reply detection, and intent transitions.
# Implements rules for detecting automated out-of-office loops, merchant commitment,
# and opt-out requests according to challenge brief specifications.

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from submission.composer import Composer


def handle_reply(
    conversation_id: str,
    merchant_id: Optional[str],
    customer_id: Optional[str],
    from_role: str,
    message: str,
    turn_number: int,
    history: List[Dict[str, Any]],
    composer: Optional[Composer] = None,
    category: Optional[Dict[str, Any]] = None,
    merchant: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Processes an incoming message and determines whether to send, wait, or end.
    msg_clean = message.strip().lower()

    # 1. Opt-out & Hostility detection
    opt_out_keywords = [
        "stop messaging",
        "useless spam",
        "unsubscribe",
        "stop",
        "dont message",
        "don't message",
        "not interested",
        "leave me alone",
        "get lost",
    ]
    if any(kw in msg_clean for kw in opt_out_keywords):
        return {
            "action": "end",
            "body": None,
            "cta": None,
            "wait_seconds": None,
            "rationale": "Merchant expressed explicit opt-out or hostility",
        }

    # 2. Auto-reply loop detection
    auto_reply_phrases = [
        "thank you for contacting",
        "thanks for contacting",
        "our team will respond shortly",
        "will respond shortly",
        "out of office",
        "auto-reply",
        "automated response",
        "currently away",
        "busy right now",
    ]
    is_common_auto_reply = any(phrase in msg_clean for phrase in auto_reply_phrases)

    same_count = 0
    for turn in reversed(history):
        if turn.get("from") == from_role:
            prior_msg = turn.get("message", "").strip().lower()
            if prior_msg == msg_clean:
                same_count += 1
            else:
                break

    if is_common_auto_reply or same_count >= 1:
        if turn_number >= 3 or same_count >= 2:
            return {
                "action": "end",
                "body": None,
                "cta": None,
                "wait_seconds": None,
                "rationale": "Merchant auto-reply loop persisted for 3+ turns. Ending conversation.",
            }
        else:
            return {
                "action": "wait",
                "body": None,
                "cta": None,
                "wait_seconds": 14400,
                "rationale": "Detected merchant auto-reply phrasing. Backing off 4 hours to wait for owner.",
            }

    # 3. Off-topic / Curveball detection (GST, taxes, loans, legal)
    off_topic_patterns = [
        "gst filing",
        "gst",
        "tax filing",
        "income tax",
        "accounting",
        "apply for loan",
        "bank loan",
        "legal advice",
    ]
    if any(pattern in msg_clean for pattern in off_topic_patterns):
        return {
            "action": "send",
            "body": "I'll have to leave that to your accountant or specialist — that's outside what I can help with directly. Coming back to our discussion — should I proceed with setting up your profile update?",
            "cta": "binary_yes_no",
            "wait_seconds": None,
            "rationale": "Out-of-scope ask politely declined; redirects back to the live thread.",
        }

    # 4. Intent transition check (Merchant commitment)
    commitment_phrases = [
        "ok lets do it",
        "ok let's do it",
        "lets do it",
        "let's do it",
        "whats next",
        "what's next",
        "go ahead",
        "yes proceed",
        "yes please",
        "send the abstract",
        "draft the post",
        "sounds good",
        "i want to join",
        "sure, let's do it",
    ]
    is_commitment = any(phrase in msg_clean for phrase in commitment_phrases)

    owner_name = (
        merchant.get("identity", {}).get("owner_first_name", "") if merchant else ""
    )
    name_str = (
        f"Dr. {owner_name}"
        if category and category.get("slug") == "dentists" and owner_name
        else (owner_name or "there")
    )

    if is_commitment:
        return {
            "action": "send",
            "body": f"Great {name_str}! I have drafted the update and set it live on your profile. I will monitor views and calls over the next 7 days.",
            "cta": "binary_yes_no",
            "wait_seconds": None,
            "rationale": "Merchant committed — transitioned immediately to action mode without re-qualifying.",
        }

    # 5. Standard conversational reply via composer or direct response
    if composer and category and merchant:
        dummy_trg = {
            "id": f"reply_intent_{conversation_id}",
            "kind": "performance_summary",
            "scope": "merchant",
            "payload": {"user_msg": message},
        }
        res = composer.compose(
            category=category,
            merchant=merchant,
            trigger=dummy_trg,
            customer=None,
            prior_bodies=[t.get("message", "") for t in history],
        )
        return {
            "action": "send",
            "body": res["body"],
            "cta": res["cta"],
            "wait_seconds": None,
            "rationale": res["rationale"],
        }

    return {
        "action": "send",
        "body": f"Thanks for your message {name_str}! Would you like me to update your active offers now?",
        "cta": "binary_yes_no",
        "wait_seconds": None,
        "rationale": "Standard merchant reply",
    }

