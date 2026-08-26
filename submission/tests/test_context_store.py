# Unit tests for ContextStore and ConversationStore.

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from submission.context_store import ContextStore, ConversationStore


def test_context_store_versioning():
    store = ContextStore()

    # 1. First push v1 -> accepts
    ok1, resp1 = store.put("category", "dentists", 1, {"slug": "dentists"})
    assert ok1 is True
    assert resp1["accepted"] is True
    assert resp1["ack_id"] == "ack_dentists_v1"

    # 2. Duplicate push v1 -> rejects 409 shape
    ok2, resp2 = store.put("category", "dentists", 1, {"slug": "dentists"})
    assert ok2 is False
    assert resp2["accepted"] is False
    assert resp2["reason"] == "stale_version"
    assert resp2["current_version"] == 1

    # 3. Newer push v2 -> accepts and updates
    ok3, resp3 = store.put("category", "dentists", 2, {"slug": "dentists", "v": 2})
    assert ok3 is True
    assert resp3["accepted"] is True
    assert resp3["ack_id"] == "ack_dentists_v2"
    assert store.get("category", "dentists") == {"slug": "dentists", "v": 2}

    # 4. Old push v1 again -> rejects with current_version: 2
    ok4, resp4 = store.put("category", "dentists", 1, {"slug": "dentists"})
    assert ok4 is False
    assert resp4["accepted"] is False
    assert resp4["reason"] == "stale_version"
    assert resp4["current_version"] == 2

    print("ContextStore versioning unit tests passed!")


def test_conversation_store():
    conv_store = ConversationStore()

    conv_store.add_turn("conv_123", "vera", "Hello!")
    conv_store.add_turn("conv_123", "merchant", "Hi, tell me more.")

    history = conv_store.get_history("conv_123")
    assert len(history) == 2
    assert history[0]["from"] == "vera"
    assert history[1]["from"] == "merchant"

    conv_store.set_status("conv_123", "waiting", wait_until="2026-04-26T18:00:00Z")
    status = conv_store.get_status("conv_123")
    assert status["status"] == "waiting"

    assert conv_store.is_suppressed("key_1") is False
    conv_store.add_suppression_key("key_1")
    assert conv_store.is_suppressed("key_1") is True

    print("ConversationStore unit tests passed!")


if __name__ == "__main__":
    test_context_store_versioning()
    test_conversation_store()
