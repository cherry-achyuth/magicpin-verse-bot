# Main FastAPI server implementation for Vera Merchant AI Assistant.
# Provides all 5 required endpoints (/v1/healthz, /v1/metadata, /v1/context,
# /v1/tick, /v1/reply) with context management and error resilience.

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from submission.composer import Composer
from submission.context_store import ContextStore, ConversationStore
from submission.conversation_handlers import handle_reply
from submission.models import (
    Action,
    ContextPushRequest,
    ContextPushResponse,
    HealthzResponse,
    MetadataResponse,
    ReplyRequest,
    ReplyResponse,
    TickRequest,
    TickResponse,
)

app = FastAPI(title="Vera Merchant AI Assistant")

start_time = time.time()
context_store = ContextStore()
conversation_store = ConversationStore()
composer = Composer()


@app.get("/v1/healthz", response_model=HealthzResponse)
async def get_healthz():
    # Returns liveness status and loaded context counts across all scopes.
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - start_time),
        "contexts_loaded": context_store.get_counts(),
    }


@app.get("/v1/metadata", response_model=MetadataResponse)
async def get_metadata():
    # Returns static team and model metadata for evaluation.
    return {
        "team_name": os.getenv("TEAM_NAME", "Charan"),
        "team_members": ["Charan"],
        "model": os.getenv("LLM_MODEL", "groq/compound-mini"),
        "approach": "context-aware multi-trigger composer with validation repair",
        "contact_email": os.getenv("CONTACT_EMAIL", "charanteja88976@gmail.com"),
        "version": "1.0.0",
        "submitted_at": "2026-08-25T10:00:00Z",
    }


@app.post("/v1/context", response_model=ContextPushResponse)
async def push_context(req: ContextPushRequest):
    # Stores versioned context object (category, merchant, customer, trigger).
    valid_scopes = {"category", "merchant", "customer", "trigger"}
    if req.scope not in valid_scopes:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "accepted": False,
                "reason": "invalid_scope",
                "details": f"Scope must be one of {sorted(valid_scopes)}",
            },
        )

    accepted, resp_data = context_store.put(
        req.scope, req.context_id, req.version, req.payload
    )

    if not accepted:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=resp_data,
        )

    return resp_data


def process_single_trigger(trg_id: str) -> Optional[Action]:
    # Resolves contexts, checks suppression, and composes an action for a single trigger.
    trg_payload = context_store.get("trigger", trg_id)
    if not trg_payload:
        return None

    merchant_id = trg_payload.get("merchant_id")
    if not merchant_id:
        return None

    merchant_payload = context_store.get("merchant", merchant_id)
    if not merchant_payload:
        return None

    cat_slug = merchant_payload.get("category_slug")
    category_payload = context_store.get("category", cat_slug)
    if not category_payload:
        return None

    customer_id = trg_payload.get("customer_id")
    customer_payload = (
        context_store.get("customer", customer_id) if customer_id else None
    )

    suppression_key = trg_payload.get("suppression_key", f"{trg_id}:{merchant_id}")
    if conversation_store.is_suppressed(suppression_key):
        return None

    conv_id = f"conv_{trg_id}_{merchant_id}"

    # Compose message
    composed = composer.compose(
        category=category_payload,
        merchant=merchant_payload,
        trigger=trg_payload,
        customer=customer_payload,
    )

    action = Action(
        conversation_id=conv_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        send_as=composed["send_as"],
        trigger_id=trg_id,
        template_name=None,
        template_params=None,
        body=composed["body"],
        cta=composed["cta"],
        suppression_key=suppression_key,
        rationale=composed["rationale"],
    )

    conversation_store.add_suppression_key(suppression_key)
    conversation_store.add_turn(conv_id, "vera", composed["body"])
    return action


executor = ThreadPoolExecutor(max_workers=8)


@app.post("/v1/tick", response_model=TickResponse)
async def handle_tick(req: TickRequest):
    # Evaluates available triggers in parallel to satisfy the strict response budget.
    actions: List[Action] = []
    if not req.available_triggers:
        return {"actions": []}

    futures = {executor.submit(process_single_trigger, tid): tid for tid in req.available_triggers}
    try:
        for f in as_completed(futures, timeout=25.0):
            try:
                action = f.result()
                if action:
                    actions.append(action)
            except Exception:
                pass
    except TimeoutError:
        pass

    return {"actions": actions}


@app.post("/v1/reply", response_model=ReplyResponse)
async def reply(req: ReplyRequest):
    # Handles multi-turn reply turns from merchant or customer.
    history = conversation_store.get_history(req.conversation_id)

    merchant_payload = context_store.get("merchant", req.merchant_id) if req.merchant_id else None
    cat_slug = merchant_payload.get("category_slug") if merchant_payload else None
    category_payload = context_store.get("category", cat_slug) if cat_slug else None

    reply_res = handle_reply(
        conversation_id=req.conversation_id,
        merchant_id=req.merchant_id,
        customer_id=req.customer_id,
        from_role=req.from_role,
        message=req.message,
        turn_number=req.turn_number,
        history=history,
        composer=composer,
        category=category_payload,
        merchant=merchant_payload,
    )

    conversation_store.add_turn(req.conversation_id, req.from_role, req.message)
    if reply_res.get("body"):
        conversation_store.add_turn(req.conversation_id, "vera", reply_res["body"])

    if reply_res.get("action") in ["end", "wait"]:
        conversation_store.set_status(req.conversation_id, reply_res["action"])

    return reply_res


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Catches unhandled exceptions and returns clean JSON error response.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_error", "details": str(exc)},
    )
