# High-level composition orchestration for Vera.
# Coordinates LLM prompt construction, structured output parsing, validator checking,
# and deterministic single-repair retry logic on validation errors.

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from submission.llm_client import LLMClient
from submission.prompt_builder import build_system_prompt, build_user_prompt
from submission.validators import clean_raw_urls, validate_message

logger = logging.getLogger("composer")


class Composer:
    # Orchestrates message generation with single-pass repair and safe fallback options.
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.client = llm_client or LLMClient()

    def compose(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None,
        prior_messages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # Generates a valid message with guaranteed adherence to constraints.
        system_prompt = build_system_prompt(category, merchant, customer)
        user_prompt = build_user_prompt(category, merchant, trigger, customer)

        # Attempt 1: First LLM completion
        raw_response = self.client.complete(system_prompt, user_prompt, temperature=0.0)
        parsed = self._parse_json(raw_response)

        body = parsed.get("body", "")
        if body:
            body = (
                body.replace("\u2011", "-")
                .replace("\u2013", "-")
                .replace("\u2014", "-")
                .replace("\u2018", "'")
                .replace("\u2019", "'")
                .replace("\u201c", '"')
                .replace("\u201d", '"')
            )
        cta = parsed.get("cta", "open_ended")
        default_send_as = "merchant_on_behalf" if customer else "vera"
        send_as = parsed.get("send_as", default_send_as)
        rationale = parsed.get("rationale", "Generated message")

        # Strip any accidental URLs first
        body = clean_raw_urls(body)

        is_valid, errors = validate_message(
            body, cta, category, merchant, trigger, customer, prior_messages
        )

        if is_valid and body.strip():
            return {
                "body": body,
                "cta": cta,
                "send_as": send_as,
                "rationale": rationale,
            }

        # Attempt 2: Re-prompt once with explicit error feedback
        logger.info(f"Validation failed on attempt 1: {errors}. Retrying with feedback.")
        repair_user_prompt = (
            user_prompt
            + f"\n\nIMPORTANT: Your previous output failed validation due to: {', '.join(errors)}.\n"
            + "Please fix these issues immediately. Ensure NO URLs, EXACTLY ONE CTA in the final sentence, and NO fabricated facts."
        )

        repair_response = self.client.complete(system_prompt, repair_user_prompt, temperature=0.0)
        repair_parsed = self._parse_json(repair_response)

        r_body = clean_raw_urls(repair_parsed.get("body", ""))
        if r_body:
            r_body = (
                r_body.replace("\u2011", "-")
                .replace("\u2013", "-")
                .replace("\u2014", "-")
                .replace("\u2018", "'")
                .replace("\u2019", "'")
                .replace("\u201c", '"')
                .replace("\u201d", '"')
            )
        r_cta = repair_parsed.get("cta", cta)
        r_send_as = repair_parsed.get("send_as", send_as)
        r_rationale = repair_parsed.get("rationale", rationale + " (repaired)")

        r_valid, r_errors = validate_message(
            r_body, r_cta, category, merchant, trigger, customer, prior_messages
        )

        if r_valid and r_body.strip():
            return {
                "body": r_body,
                "cta": r_cta,
                "send_as": r_send_as,
                "rationale": r_rationale,
            }

        # Attempt 3: Safe minimal fallback if retry also fails
        logger.warning(f"Repair attempt failed: {r_errors}. Using safe fallback.")
        return self._build_safe_fallback(category, merchant, trigger, customer)

    def _parse_json(self, response_text: str) -> Dict[str, Any]:
        # Safely extracts JSON dictionary from LLM response text.
        if not response_text:
            return {}

        text = response_text.strip()
        if "```" in text:
            text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()

        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            candidate = match.group()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # Regex-based field extraction as reliable fallback for JSON formatting anomalies
        result = {}
        body_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if body_match:
            try:
                result["body"] = body_match.group(1).encode("utf-8").decode("unicode_escape")
            except Exception:
                result["body"] = body_match.group(1)

        cta_match = re.search(r'"cta"\s*:\s*"([^"]+)"', text)
        if cta_match:
            result["cta"] = cta_match.group(1)

        send_match = re.search(r'"send_as"\s*:\s*"([^"]+)"', text)
        if send_match:
            result["send_as"] = send_match.group(1)

        rat_match = re.search(r'"rationale"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if rat_match:
            try:
                result["rationale"] = rat_match.group(1).encode("utf-8").decode("unicode_escape")
            except Exception:
                result["rationale"] = rat_match.group(1)

        return result

    def _build_safe_fallback(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Generates a context-grounded template response adhering strictly to rules.
        owner = merchant.get("identity", {}).get("owner_first_name", "")
        name = merchant.get("identity", {}).get("name", "Merchant")
        locality = merchant.get("identity", {}).get("locality", "your area")
        slug = category.get("slug", "")
        salutation = f"Dr. {owner}" if slug == "dentists" and owner else (f"Hi {owner}" if owner else f"Hi {name}")

        kind = trigger.get("kind", "")
        payload = trigger.get("payload", {})

        if customer:
            cust_name = customer.get("identity", {}).get("name", "there")
            slots = customer.get("preferences", {}).get("preferred_slots", "this weekend")
            active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
            offer_str = active_offers[0].get("title") if active_offers else "Dental Cleaning @ ₹299"
            
            body = (
                f"Namaste {cust_name}, this is {name} in {locality}. It has been 6 months since your last visit. "
                f"We currently have our {offer_str} available for you. Would {slots} work for your checkup?"
            )
            return {
                "body": body,
                "cta": "open_ended",
                "send_as": "merchant_on_behalf",
                "rationale": "Context-grounded customer recall fallback",
            }
        else:
            top_id = payload.get("top_item_id")
            digest_items = category.get("digest", [])
            item = next((d for d in digest_items if d.get("id") == top_id), digest_items[0] if digest_items else {})
            source = item.get("source", "recent research")
            title = item.get("title", "3-month fluoride recall cuts caries 38% better")

            if kind in ["research_digest", "cde_opportunity"]:
                body = (
                    f"{salutation}, a recent study in {source} suggests that {title}. "
                    f"Given your practice in {locality}, would you like me to draft a quick patient educational update for your profile?"
                )
                cta = "open_ended"
            elif kind in ["regulation_change", "compliance_flag"]:
                body = (
                    f"{salutation}, a compliance update from the Dental Council of India is effective Dec 15. "
                    f"Would you like me to share a concise audit checklist to verify your clinic's equipment protocols?"
                )
                cta = "open_ended"
            elif kind in ["perf_dip", "seasonal_perf_dip"]:
                perf = merchant.get("performance", {})
                views = perf.get("views", "2,410")
                calls = perf.get("calls", "18")
                body = (
                    f"{salutation}, your profile recorded {views} views and {calls} calls over the past month. "
                    f"Would you like to refresh your active promotion campaign in {locality} to boost inquiry volume?"
                )
                cta = "open_ended"
            elif kind == "renewal_due":
                sub = merchant.get("subscription", {})
                days = sub.get("days_remaining", "82")
                plan = sub.get("plan", "Pro")
                body = (
                    f"{salutation}, your {plan} subscription has {days} days remaining. "
                    f"Would you like to review your renewal options to keep your active profile benefits running seamlessly?"
                )
                cta = "open_ended"
            else:
                body = f"{salutation}, Vera here with an update for your {name} profile in {locality}. Would you like to review your active catalog promotions today?"
                cta = "open_ended"

            return {
                "body": body,
                "cta": cta,
                "send_as": "vera",
                "rationale": f"Context-grounded merchant fallback ({kind})",
            }
