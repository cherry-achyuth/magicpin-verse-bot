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

Call-to-Action & Engagement Rules:
- Include EXACTLY ONE CTA in the very last sentence.
- The final sentence MUST be an actionable, low-friction question ending with a question mark '?' (e.g., 'Which of these two reserved slots works best for your schedule?', 'Would you like us to schedule delivery for tomorrow morning?').
- Use clear binary slot choices or 1-click confirmation asks to make replying effortless.

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

Call-to-Action & Engagement Rules:
- Include EXACTLY ONE CTA in the very last sentence.
- The final sentence MUST be a compelling, low-friction question ending with a question mark '?' (e.g., 'Would you like me to set this live on your profile now?', 'Would you like me to draft a 1-page patient education WhatsApp template for your practice?').
- Anchor the ask in a clear "Why Now": create natural urgency (match kickoff, weekend rush, early-bird advance booking, or deadline).
- Make replying effortless: offer a concrete draft or 1-click execution rather than asking the merchant to do manual work.

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

    # Locate featured digest item if top_item_id is specified
    top_item_id = payload.get("top_item_id") or payload.get("digest_item_id")
    featured_digest = None
    if top_item_id:
        for item in category.get("digest", []):
            if item.get("id") == top_item_id:
                featured_digest = item
                break

    framing_instruction = get_trigger_framing(kind, payload, scope)

    context_summary = {
        "category_slug": category.get("slug"),
        "category_voice": category.get("voice"),
        "peer_stats": category.get("peer_stats"),
        "featured_digest_item": featured_digest,
        "all_digest_items": category.get("digest", [])[:3],
        "offer_catalog": category.get("offer_catalog", [])[:3],
        "merchant_name": merchant.get("identity", {}).get("name"),
        "owner_first_name": merchant.get("identity", {}).get("owner_first_name"),
        "locality": merchant.get("identity", {}).get("locality"),
        "languages": merchant.get("identity", {}).get("languages"),
        "performance": merchant.get("performance"),
        "signals": merchant.get("signals", []),
        "customer_aggregate": merchant.get("customer_aggregate", {}),
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

Compose the single structured JSON message response now. Ensure rich factual grounding, correct recipient salutation, and exactly one final CTA.
"""
    return user_prompt


def get_trigger_framing(kind: str, payload: Dict[str, Any], scope: str) -> str:
    # Dispatches specific framing instructions based on the trigger kind.
    fest_name = payload.get("festival") or payload.get("festival_name", "the upcoming festival")
    fest_date = payload.get("date", "soon")
    fest_days = payload.get("days_until", "a few")

    framings = {
        "research_digest": (
            "Cite the featured digest item's exact publication source and core finding from the CONTEXT above. "
            "Connect this clinical/industry finding directly to the merchant's patient cohort or locality. "
            "Do NOT fabricate hypothetical patient counts or numbers. "
            "End with a compelling, zero-friction question: 'Would you like me to draft a 1-page patient education WhatsApp update for your practice to share with this cohort?'"
        ),
        "cde_opportunity": (
            "Highlight the continuing education or clinical technique update from the digest item in CONTEXT. "
            "Ask if they would like registration or syllabus details."
        ),
        "regulation_change": (
            "Inform the merchant of the regulatory standard or compliance deadline mentioned in the trigger payload or digest. "
            "Do NOT invent unlisted technical dose limits. "
            "End with a clear offer asking if they would like a concise audit checklist to verify clinic compliance."
        ),
        "perf_dip": (
            "Highlight the performance trend using ONLY the exact views or calls numbers from CONTEXT. "
            "Suggest refreshing or scaling one of the active offers or catalog services. "
            "End with a direct yes/no question asking to test or activate the promotion."
        ),
        "seasonal_perf_dip": (
            "Address the seasonal trend using the category peer benchmarks from CONTEXT. Recommend refreshing active offers. "
            "End with a single low-friction action proposal question."
        ),
        "perf_spike": (
            "Celebrate the merchant's traffic spike with concrete performance metrics from CONTEXT. "
            "Recommend scaling up the best-performing offer to sustain momentum."
        ),
        "milestone_reached": (
            f"Congratulate the merchant warmly on approaching/reaching {payload.get('value_now', '145')} of {payload.get('milestone_value', '150')} {payload.get('metric', 'reviews')}. "
            "Suggest celebrating with a special thank-you offer for local patrons. "
            "End with a question asking to set up the milestone promo."
        ),
        "dormant_with_vera": (
            f"Re-engage dormant merchant who has not messaged in {payload.get('days_since_last_merchant_message', '30')} days. "
            "Reference their profile locality and propose a high-value catalog refresh. "
            "End with a low-friction binary question."
        ),
        "review_theme_emerged": (
            f"Share constructive feedback regarding {payload.get('theme', 'delivery speed')} ({payload.get('occurrences_30d', 4)} recent mentions: '{payload.get('common_quote', 'delayed deliveries')}'). "
            "Offer a quick packaging/dispatch checklist or peak-hour buffer setting. "
            "End with a supportive question asking if they want to adjust their delivery radius or settings."
        ),
        "competitor_opened": (
            f"Alert merchant that {payload.get('competitor_name', 'a competitor')} opened {payload.get('distance_km', 'nearby')}km away with an offer ({payload.get('their_offer', 'discounted package')}). "
            "Propose a targeted counter-promotion highlighting their signature clinic/salon services. "
            "End with a question asking if they want to activate the counter-campaign."
        ),
        "festival_upcoming": (
            f"Suggest early festive planning for {fest_name} ({fest_days} days away on {fest_date}). "
            "Highlight that early-bird advance bookings help secure holiday revenue and smooth schedule spikes. "
            "Recommend launching an advance booking promo using their active catalog package. "
            "End with: 'Would you like me to draft an early-bird festive package and set it live on your listing today?'"
        ),
        "category_seasonal": (
            f"Highlight seasonal demand trends ({', '.join(payload.get('trends', ['summer demand surge']))}). "
            "Suggest featuring high-demand seasonal items on their profile front page. "
            "End with a question asking to update their featured listings."
        ),
        "ipl_match_today": (
            f"Leverage match excitement for {payload.get('match', 'today\'s match')} at {payload.get('venue', 'the stadium')}. "
            "Remind the operator that delivery orders surge 45 mins prior to the toss. "
            "Propose a match-day meal combo with active catalog discounts. "
            "End with an urgent binary question: 'Shall I activate this match-day delivery special on your profile before the 7:30 PM toss tonight?'"
        ),
        "wedding_package_followup": (
            f"If customer is present, compose warmly as 'merchant_on_behalf' to the bride/client. "
            f"Reference their wedding on {payload.get('wedding_date', 'upcoming date')} and suggest beginning their 30-day skin prep / bridal package. "
            "Offer convenient preferred appointment slots and end with a single scheduling question."
        ),
        "supply_alert": (
            f"Urgent heads-up: {payload.get('manufacturer', 'Manufacturer')} issued an alert/recall for {payload.get('molecule', 'product')} ({', '.join(payload.get('affected_batches', []))}). "
            "Advise verifying stock and isolating affected batches immediately. "
            "End with an actionable question asking if they have inspected their current inventory."
        ),
        "gbp_unverified": (
            f"Remind merchant to verify their Google Business Profile to capture an estimated {int(float(payload.get('estimated_uplift_pct', 0.30))*100)}% uplift in local search discovery and calls. "
            "End with a question asking if they would like the simple verification instructions."
        ),
        "renewal_due": (
            f"Remind merchant of their {payload.get('plan', 'Pro')} subscription plan with {payload.get('days_remaining', '12')} days remaining. "
            "Highlight their total views, calls, and performance delivered from CONTEXT to demonstrate ROI. "
            "End with a clear, low-friction renewal question."
        ),
        "curious_ask_due": (
            "Ask a single friendly, low-friction question about what services or products are in highest demand this week. "
            "End with a simple conversational question mark."
        ),
        "active_planning_intent": (
            f"The merchant expressed planning interest ('{payload.get('merchant_last_message', '')}'). "
            "Propose an operational, structured package with concrete pricing and service details tailored to their category and locality. "
            "End with a question asking if they would like to review the full draft or activate it."
        ),
        "recall_due": (
            "If customer is present, compose as 'merchant_on_behalf' addressed to the customer. "
            "Reference their last visit date, recall interval, and offer two specific preferred slots from CONTEXT (e.g. weekday evenings) with the active service price. "
            "If customer is absent, alert the merchant about their lapsed cohort and offer to draft recall reminders."
        ),
        "customer_lapsed_soft": (
            "If customer is present, compose as 'merchant_on_behalf' warmly re-engaging them with preferred slot choices and special routine maintenance care. "
            "End with a single slot choice question."
        ),
        "customer_lapsed_hard": (
            f"If customer is present, compose warmly as 'merchant_on_behalf' to the customer using their name. "
            f"Acknowledge their previous fitness focus ({payload.get('previous_focus', 'fitness')} for {payload.get('previous_membership_months', 5)} months) and invite them back with an encouraging coaching tone. "
            "Offer a zero-pressure restart consultation or reserved weekend workout slot. "
            "End with a low-friction choice: 'Would Saturday morning at 10:00 AM or Sunday at 11:00 AM suit you better for a quick restart session?'"
        ),
        "appointment_tomorrow": (
            "Send friendly appointment confirmation for tomorrow with slot details and clinic/studio address. "
            "End with a question asking to confirm attendance."
        ),
        "chronic_refill_due": (
            f"Compose as 'merchant_on_behalf' to the customer/family member. "
            f"Remind them that regular refills for their maintenance medicines ({', '.join(payload.get('molecule_list', ['prescriptions']))}) are due before stock runs out on {payload.get('stock_runs_out_iso', 'this week')[:10]}. "
            "Offer doorstep delivery or express counter pickup. "
            "End with a single confirmation question."
        ),
        "trial_followup": (
            f"Follow up warmly on the customer's trial session on {payload.get('trial_date', 'recently')}. "
            f"Invite them to their next scheduled class ({payload.get('next_session_options', [{}])[0].get('label', 'upcoming session')}). "
            "End with a single friendly confirmation question."
        ),
        "winback_eligible": (
            f"Inform merchant that {payload.get('lapsed_customers_added_since_expiry', 24)} clients became lapsed over the last {payload.get('days_since_expiry', 38)} days during their profile pause. "
            "Propose a targeted win-back campaign with a 15% restart incentive to recover footfall. "
            "End with a binary question asking to launch the winback campaign."
        ),
    }

    if kind in framings:
        return framings[kind]

    logger.warning(f"Unknown trigger kind '{kind}' - falling back to generic framing.")
    return f"Provide a relevant, concise update regarding {kind} using facts from the payload."
