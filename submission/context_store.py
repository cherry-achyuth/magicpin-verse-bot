# In-memory storage for context objects and active conversations.
# Manages versioned context updates (categories, merchants, customers, triggers)
# and keeps track of turn histories for multi-turn conversations.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ContextStore:
    # Stores context items keyed by (scope, context_id).
    def __init__(self):
        self._store: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def put(
        self, scope: str, context_id: str, version: int, payload: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        # Atomically updates context if the incoming version is higher than what we have.
        key = (scope, context_id)
        current = self._store.get(key)

        if current:
            if current["version"] == version:
                return True, {
                    "accepted": True,
                    "ack_id": f"ack_{context_id}_v{version}",
                    "stored_at": current["updated_at"],
                }
            elif current["version"] > version:
                return False, {
                    "accepted": False,
                    "reason": "stale_version",
                    "current_version": current["version"],
                }

        now_str = datetime.now(timezone.utc).isoformat()
        self._store[key] = {
            "version": version,
            "payload": payload,
            "updated_at": now_str,
        }
        return True, {
            "accepted": True,
            "ack_id": f"ack_{context_id}_v{version}",
            "stored_at": now_str,
        }

    def get(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        # Returns the stored payload for a given scope and ID.
        item = self._store.get((scope, context_id))
        return item["payload"] if item else None

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        # Returns the stored version number for a given scope and ID.
        item = self._store.get((scope, context_id))
        return item["version"] if item else None

    def get_by_scope(self, scope: str) -> Dict[str, Dict[str, Any]]:
        # Returns all payloads for a specific scope.
        result = {}
        for (s, cid), item in self._store.items():
            if s == scope:
                result[cid] = item["payload"]
        return result

    def get_counts(self) -> Dict[str, int]:
        # Returns total context items loaded per scope for healthz.
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for (scope, _), _ in self._store.items():
            if scope in counts:
                counts[scope] += 1
            else:
                counts[scope] = 1
        return counts

    def clear(self):
        # Wipes all stored contexts.
        self._store.clear()


class ConversationStore:
    # Stores turn history and status for active conversations.
    def __init__(self):
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}
        self._status: Dict[str, Dict[str, Any]] = {}
        self._sent_suppression_keys: set[str] = set()

    def add_turn(
        self,
        conversation_id: str,
        role: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ):
        # Appends a turn to the conversation history.
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
            self._status[conversation_id] = {"status": "open"}

        turn = {
            "from": role,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            turn.update(extra)
        self._conversations[conversation_id].append(turn)

    def get_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        # Returns ordered turns for a conversation.
        return self._conversations.get(conversation_id, [])

    def set_status(
        self,
        conversation_id: str,
        status: str,
        wait_until: Optional[str] = None,
    ):
        # Updates conversation status (open, waiting, ended).
        self._status[conversation_id] = {
            "status": status,
            "wait_until": wait_until,
        }

    def get_status(self, conversation_id: str) -> Dict[str, Any]:
        # Gets current status of a conversation.
        return self._status.get(conversation_id, {"status": "open"})

    def add_suppression_key(self, key: str):
        # Marks a trigger suppression key as active.
        if key:
            self._sent_suppression_keys.add(key)

    def is_suppressed(self, key: str) -> bool:
        # Checks if a trigger suppression key was already sent.
        if not key:
            return False
        return key in self._sent_suppression_keys

    def clear(self):
        # Wipes all conversation state.
        self._conversations.clear()
        self._status.clear()
        self._sent_suppression_keys.clear()
