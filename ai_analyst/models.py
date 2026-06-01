"""Pydantic schemas + tiny LLM client for the AI analyst."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field


# --- Request/Response models ---

class AskRequest(BaseModel):
    question: str = Field(..., description="Natural-language question about the data.")
    session_id: Optional[str] = Field(None, description="Session ID for multi-turn context.")


class AskResponse(BaseModel):
    question: str
    sql: str
    rows: List[Dict[str, Any]]
    answer: str
    table_count: int
    sources: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Tables/columns cited in the SQL, for transparency.",
    )


class PlanRequest(BaseModel):
    goal: str
    session_id: Optional[str] = None


class PlanStep(BaseModel):
    question: Optional[str] = None
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    error: Optional[str] = None
    why: Optional[str] = None


class PlanResponse(BaseModel):
    goal: str
    steps: List[PlanStep]


# --- New: multi-turn chat with session memory ---

class ChatRequest(BaseModel):
    message: str = Field(..., description="A single message in the conversation.")
    session_id: str = Field(..., description="Session ID — used to load prior turns.")
    stream: bool = Field(default=False, description="If true, response is server-sent events.")


class ChatResponse(BaseModel):
    session_id: str
    question: str
    sql: str
    rows: List[Dict[str, Any]]
    answer: str
    turn_count: int
    sources: List[Dict[str, str]] = Field(default_factory=list)


class SessionInfo(BaseModel):
    session_id: str
    turn_count: int
    recent_sql_count: int
    created_at: float
    last_activity_at: float
    ttl_seconds_remaining: int


# --- LLM client ---

class MiniMaxClient:
    """MiniMax chat client. Uses MiniMax-M2 (production) or M2.7 (light)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "MiniMax-M2"):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.model = model
        self.base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")

    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
        response_format_json: bool = False,
    ) -> str:
        if not self.api_key:
            return f"[local fallback] {user[:300]}"
        body: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if response_format_json:
            body["response_format"] = {"type": "json_object"}
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def chat_stream(
        self,
        system: str,
        user: str,
        temperature: float = 0.1,
    ):
        """Streaming chat. Yields token strings as they arrive."""
        if not self.api_key:
            yield f"[local fallback] {user[:300]}"
            return

        body: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        with requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=60,
            stream=True,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    return
                try:
                    import json
                    obj = json.loads(payload)
                    delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
