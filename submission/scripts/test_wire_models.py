# Test script to verify API request/response Pydantic models against api-call-examples.md

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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


def test_roundtrip():
    # 1. Healthz Response (Example 1.1)
    healthz_json = {
        "status": "ok",
        "uptime_seconds": 124,
        "contexts_loaded": {
            "category": 5,
            "merchant": 50,
            "customer": 200,
            "trigger": 100,
        },
    }
    obj = HealthzResponse.model_validate(healthz_json)
    assert obj.status == "ok"
    assert obj.contexts_loaded["category"] == 5

    # 2. Metadata Response (Example 1.2)
    meta_json = {
        "team_name": "Team Alpha",
        "team_members": ["Alice", "Bob"],
        "model": "claude-opus-4-7",
        "approach": "single-prompt composer",
        "contact_email": "team@example.com",
        "version": "1.2.0",
        "submitted_at": "2026-04-26T08:00:00Z",
    }
    meta_obj = MetadataResponse.model_validate(meta_json)
    assert meta_obj.team_name == "Team Alpha"

    # 3. Context Push Request & Response (Example 1.3 & 1.5)
    push_req_json = {
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "delivered_at": "2026-04-26T09:45:00Z",
        "payload": {"slug": "dentists"},
    }
    push_obj = ContextPushRequest.model_validate(push_req_json)
    assert push_obj.scope == "category"

    resp_409_json = {
        "accepted": False,
        "reason": "stale_version",
        "current_version": 1,
    }
    resp_409_obj = ContextPushResponse.model_validate(resp_409_json)
    assert resp_409_obj.accepted is False
    assert resp_409_obj.current_version == 1

    # 4. Tick Request & Response (Example 2.2)
    tick_req_json = {
        "now": "2026-04-26T10:35:00Z",
        "available_triggers": ["trg_001_research_digest_dentists"],
    }
    tick_req_obj = TickRequest.model_validate(tick_req_json)
    assert len(tick_req_obj.available_triggers) == 1

    tick_resp_json = {
        "actions": [
            {
                "conversation_id": "conv_m_001_drmeera_research_W17",
                "merchant_id": "m_001_drmeera_dentist_delhi",
                "customer_id": None,
                "send_as": "vera",
                "trigger_id": "trg_001_research_digest_dentists",
                "template_name": "vera_research_digest_v1",
                "template_params": ["Dr. Meera", "JIDA Oct issue"],
                "body": "Dr. Meera, JIDA's Oct issue landed...",
                "cta": "open_ended",
                "suppression_key": "research:dentists:2026-W17",
                "rationale": "External research digest",
            }
        ]
    }
    tick_resp_obj = TickResponse.model_validate(tick_resp_json)
    assert len(tick_resp_obj.actions) == 1
    assert tick_resp_obj.actions[0].send_as == "vera"

    # 5. Reply Request & Response (Example 2.4, 2.5, 2.6)
    reply_req_json = {
        "conversation_id": "conv_m_001_drmeera_research_W17",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": "Yes please send the abstract",
        "received_at": "2026-04-26T10:42:00Z",
        "turn_number": 2,
    }
    reply_req_obj = ReplyRequest.model_validate(reply_req_json)
    assert reply_req_obj.turn_number == 2

    reply_send_json = {
        "action": "send",
        "body": "Sending the abstract now...",
        "cta": "binary_yes_no",
        "rationale": "Honoring asks",
    }
    reply_send_obj = ReplyResponse.model_validate(reply_send_json)
    assert reply_send_obj.action == "send"

    reply_wait_json = {
        "action": "wait",
        "wait_seconds": 14400,
        "rationale": "Detected auto-reply",
    }
    reply_wait_obj = ReplyResponse.model_validate(reply_wait_json)
    assert reply_wait_obj.action == "wait"
    assert reply_wait_obj.wait_seconds == 14400

    reply_end_json = {
        "action": "end",
        "rationale": "Merchant opted out",
    }
    reply_end_obj = ReplyResponse.model_validate(reply_end_json)
    assert reply_end_obj.action == "end"

    print("All wire model roundtrips passed successfully!")


if __name__ == "__main__":
    test_roundtrip()
