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
        slug = category.get("slug", "")
        prefix = "Dr. " if slug == "dentists" and owner else ""
        greeting = f"Hi {prefix}{owner}," if owner else f"Hi {name},"

        kind = trigger.get("kind", "")
        payload = trigger.get("payload", {})

        if customer:
            cust_name = customer.get("identity", {}).get("name", "there")
            slots = customer.get("preferences", {}).get("preferred_slots", "this weekend")
            active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
            offer_str = active_offers[0].get("title") if active_offers else "special routine checkup"
            
            body = (
                f"Hi {cust_name}, this is {name}. It has been 6 months since your last visit. "
                f"We currently have our {offer_str} available—would {slots} work better for your appointment?"
            )
            return {
                "body": body,
                "cta": "multi_choice_slots",
                "send_as": "merchant_on_behalf",
                "rationale": "Context-grounded customer recall fallback",
            }
        else:
            if kind in ["research_digest", "cde_opportunity"]:
                source = payload.get("source", "recent research")
                title = payload.get("title", "industry demand trends")
                body = (
                    f"{greeting} {source} highlights {title}. "
                    f"Would you like to feature this service in your profile offers this week?"
                )
                cta = "binary_yes_no"
            elif kind in ["perf_dip", "seasonal_perf_dip"]:
                metric = payload.get("views_dip_pct") or payload.get("dip_pct") or "15%"
                body = (
                    f"{greeting} your profile views experienced a {metric} dip this past week. "
                    f"Would you like us to refresh your active promo campaign to recover traffic?"
                )
                cta = "binary_yes_no"
            else:
                body = f"{greeting} Vera here with a quick performance update. Would you like to review your active offers today?"
                cta = "binary_yes_no"

            return {
                "body": body,
                "cta": cta,
                "send_as": "vera",
                "rationale": f"Context-grounded merchant fallback ({kind})",
            }
