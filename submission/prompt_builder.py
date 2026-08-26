# Builds system and user prompts for LLM message composition.
# Handles trigger-kind dispatch, merchant vs customer paths, category voice,
# single CTA rules, language mix, and strict anti-fabrication guidelines.

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("prompt_builder")


def build_system_prompt(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
) -> str:
    # Construct system prompt with category voice guidelines and compliance rules.
    slug = category.get("slug", "generic")
    voice = category.get("voice", {})
    tone = voice.get("tone", "professional and friendly")
    allowed = voice.get("vocab_allowed", [])
    taboos = voice.get("vocab_taboo") or voice.get("taboos") or []

    owner_name = merchant.get("identity", {}).get("owner_first_name", "")
    languages = merchant.get("identity", {}).get("languages", ["en"])
    lang_str = ", ".join(languages)

    is_customer_facing = customer is not None

    if is_customer_facing:
        prompt = f"""You are Vera composing a message ON BEHALF OF {merchant.get('identity', {}).get('name', 'the merchant')} to their customer.
Role & Tone:
- Tone: {tone}
- Target Languages: {lang_str}
- Send As MUST be: "merchant_on_behalf"
- NEVER use forbidden words: {taboos}
- NEVER promise guaranteed cures, 100% results, or false assurances.
- NEVER include raw URLs (e.g. no http:// or www.). Use clear plain-text descriptions instead.
- NEVER invent facts, prices, dates, or details not present in the provided context.

Call-to-Action Rules:
- Include EXACTLY ONE CTA in or near the last sentence.
- For appointment/recall messages, provide a clear multi-choice slot CTA (e.g., "Would Saturday 10am or Sunday 2pm suit you better?").

Output Format:
You MUST output valid JSON with keys:
{{"body": "<message text>", "cta": "<cta_type>", "send_as": "merchant_on_behalf", "rationale": "<brief rationale>"}}
"""
    else:
        prompt = f"""You are Vera, an intelligent AI business partner created by magicpin for merchant owners.
Role & Tone:
- Category: {slug}
- Tone: {tone}
- Owner Name: {owner_name} (Use prefix "Dr." for dental category if appropriate)
- Languages: {lang_str}
- Send As MUST be: "vera"
- NEVER use forbidden taboo words: {taboos}
- NEVER include raw URLs (no http:// or www.). Describe links in words if needed.
- NEVER fabricate numbers, dates, citations, or competitor names not in the context.
- CITE sources explicitly when referencing research, digests, or news.

Call-to-Action Rules:
- Include EXACTLY ONE CTA in the final sentence.
- Use open-ended, binary, or low-friction asks to encourage merchant reply.

Output Format:
You MUST output valid JSON with keys:
{{"body": "<message text>", "cta": "<cta_type>", "send_as": "vera", "rationale": "<brief rationale>"}}
"""

    return prompt


def build_user_prompt(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
) -> str:
    # Build user prompt incorporating 4-context payload and trigger kind framing.
    kind = trigger.get("kind", "generic")
    payload = trigger.get("payload", {})
    scope = trigger.get("scope", "merchant")

    framing_instruction = get_trigger_framing(kind, payload, scope)

    context_summary = {
        "category_slug": category.get("slug"),
        "category_voice": category.get("voice"),
        "peer_stats": category.get("peer_stats"),
        "digest": category.get("digest", [])[:2],
        "offer_catalog": category.get("offer_catalog", [])[:3],
        "merchant_name": merchant.get("identity", {}).get("name"),
        "owner_first_name": merchant.get("identity", {}).get("owner_first_name"),
        "locality": merchant.get("identity", {}).get("locality"),
        "languages": merchant.get("identity", {}).get("languages"),
        "performance": merchant.get("performance"),
        "active_offers": [
            o for o in merchant.get("offers", []) if o.get("status") == "active"
        ],
        "trigger_kind": kind,
        "trigger_payload": payload,
        "trigger_urgency": trigger.get("urgency"),
    }

    if customer:
        context_summary["customer"] = {
            "name": customer.get("identity", {}).get("name"),
            "language_pref": customer.get("identity", {}).get("language_pref"),
            "relationship": customer.get("relationship"),
            "state": customer.get("state"),
            "preferred_slots": customer.get("preferences", {}).get(
                "preferred_slots"
            ),
            "consent_scope": customer.get("consent", {}).get("scope"),
        }

    user_prompt = f"""=== CONTEXT ===
{json.dumps(context_summary, indent=2)}

=== TRIGGER FRAMING ===
{framing_instruction}

Compose the single structured JSON message response now.
"""
    return user_prompt


def get_trigger_framing(kind: str, payload: Dict[str, Any], scope: str) -> str:
    # Dispatches specific framing instructions based on the trigger kind.
    framings = {
        "research_digest": "Frame as an insightful industry digest update. Cite the source title/issue explicitly.",
        "cde_opportunity": "Highlight practical continuing education or technique updates from recent digest literature.",
        "regulation_change": "Inform the merchant of regulatory updates or safety compliance standards in their category.",
        "perf_dip": f"Highlight performance drop using specific payload metric. Suggest actionable recovery offer.",
        "seasonal_perf_dip": "Address seasonal performance dip with peer benchmark insights and active offer refresh.",
        "perf_spike": "Celebrate performance spike with specific metrics. Recommend scaling current active offers.",
        "milestone_reached": f"Congratulate merchant on reaching milestone ({payload.get('metric', 'views/calls')}).",
        "dormant_with_vera": "Re-engage dormant merchant with a high-value quick update or offer refresh ask.",
        "review_theme_emerged": f"Share positive/constructive theme emerging from recent reviews ({payload.get('theme', 'feedback')}).",
        "competitor_opened": f"Alert merchant to local market changes in {payload.get('locality', 'their area')}.",
        "festival_upcoming": f"Suggest special seasonal promo for upcoming festival ({payload.get('festival_name', 'upcoming event')}).",
        "category_seasonal": "Highlight seasonal demand trends for specific services in this category.",
        "ipl_match_today": "Leverage match day excitement with quick flash-deal or event special ask.",
        "wedding_package_followup": "Suggest highlighting wedding packages and group bookings.",
        "supply_alert": "Provide heads-up on inventory/supply trends or popular demand items.",
        "gbp_unverified": "Remind merchant to verify their Google Business Profile to boost views and calls.",
        "renewal_due": "Remind merchant about subscription renewal and highlight key performance gains.",
        "curious_ask_due": "Ask a low-friction question about upcoming inventory or seasonal availability.",
        "active_planning_intent": "Assist merchant with proactive campaign planning for next month.",
        "recall_due": "Send polite recall reminder for checkup/cleaning based on last visit history.",
        "customer_lapsed_soft": "Re-engage soft lapsed customer with a warm personal invitation or routine checkup.",
        "customer_lapsed_hard": "Re-engage long lapsed customer emphasizing convenient slots and friendly care.",
        "appointment_tomorrow": "Send friendly appointment confirmation for tomorrow with slot details.",
        "chronic_refill_due": "Remind patient/customer about regular prescription or care product refill.",
        "trial_followup": "Follow up warmly on recent first visit and ask about their experience.",
        "winback_eligible": "Offer a special returning service package to win back inactive clients.",
    }

    if kind in framings:
        return framings[kind]

    logger.warning(f"Unknown trigger kind '{kind}' - falling back to generic framing.")
    return f"Provide a relevant, concise update regarding {kind} using facts from the payload."
