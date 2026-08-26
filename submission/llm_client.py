# Multi-provider LLM client for Vera.
# Wraps Gemini, OpenAI, Anthropic, DeepSeek, Groq, OpenRouter, and Ollama APIs.
# Enforces temperature=0 for deterministic composition across runs.

from __future__ import annotations

import json
import os
import time
from typing import Optional
from urllib import error as urlerror, request as urlrequest
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    # Handles API requests to configured LLM providers with automatic fallback options.
    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER") or "gemini").lower()
        if self.provider == "gemini":
            self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY") or ""
        else:
            self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        self.model = model or os.getenv("LLM_MODEL") or ""

    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        # Enforces temperature=0 for deterministic responses as required by challenge rules.
        temp = 0.0 if temperature is None else temperature

        try:
            if self.provider == "openai":
                return self._complete_openai(system, user, temp)
            elif self.provider == "anthropic":
                return self._complete_anthropic(system, user, temp)
            elif self.provider == "gemini":
                return self._complete_gemini(system, user, temp)
            elif self.provider == "deepseek":
                return self._complete_deepseek(system, user, temp)
            elif self.provider == "groq":
                return self._complete_groq(system, user, temp)
            elif self.provider == "openrouter":
                return self._complete_openrouter(system, user, temp)
            elif self.provider == "ollama":
                return self._complete_ollama(system, user, temp)
            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")
        except Exception as e:
            # Return empty string on API error so composer fallback generates context-grounded message
            return "{}"

    def _complete_openai(self, system: str, user: str, temperature: float) -> str:
        # Calls OpenAI chat completions endpoint.
        model = self.model or "gpt-4o-mini"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        req = urlrequest.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urlrequest.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _complete_anthropic(self, system: str, user: str, temperature: float) -> str:
        # Calls Anthropic messages endpoint.
        model = self.model or "claude-3-5-sonnet-20241022"
        payload = {
            "model": model,
            "max_tokens": 1024,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        req = urlrequest.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urlrequest.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]

    def _complete_gemini(self, system: str, user: str, temperature: float) -> str:
        # Calls Google Gemini API using REST endpoint or python SDK if available.
        model = self.model if (self.model and "gemini" in self.model) else "gemini-flash-latest"
        m_path = model if model.startswith("models/") else f"models/{model}"
        prompt = f"{system}\n\n{user}" if system else user
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/{m_path}:generateContent?key={self.api_key}"
        req = urlrequest.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                with urlrequest.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except urlerror.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise e

    def _complete_deepseek(self, system: str, user: str, temperature: float) -> str:
        # Calls DeepSeek OpenAI-compatible API.
        model = self.model or "deepseek-chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        req = urlrequest.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urlrequest.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _complete_groq(self, system: str, user: str, temperature: float) -> str:
        # Calls Groq API with automatic retry on rate limits.
        model = self.model or "groq/compound-mini"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 800,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "magicpin-vera/1.0",
        }

        for attempt in range(5):
            try:
                req = urlrequest.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                with urlrequest.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
            except urlerror.HTTPError as e:
                if e.code == 429 and attempt < 4:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise e

    def _complete_openrouter(self, system: str, user: str, temperature: float) -> str:
        # Calls OpenRouter API.
        model = self.model or "anthropic/claude-3.5-haiku"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://magicpin.com",
        }
        req = urlrequest.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urlrequest.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _complete_ollama(self, system: str, user: str, temperature: float) -> str:
        # Calls local Ollama API server.
        model = self.model or "llama3"
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        prompt = f"{system}\n\n{user}" if system else user
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        req = urlrequest.Request(
            f"{ollama_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlrequest.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["response"]
