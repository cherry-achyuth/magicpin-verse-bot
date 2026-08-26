# Smoke tests for LLMClient initialization and configuration switching.

from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from submission.llm_client import LLMClient


def test_llm_client_config():
    # Test default initialization from env
    client = LLMClient(provider="gemini", model="gemini-1.5-flash")
    assert client.provider == "gemini"
    assert client.model == "gemini-1.5-flash"

    # Test changing model dynamically without code changes
    client2 = LLMClient(provider="openai", model="gpt-4o-mini")
    assert client2.provider == "openai"
    assert client2.model == "gpt-4o-mini"

    print("LLMClient configuration tests passed!")


if __name__ == "__main__":
    test_llm_client_config()
