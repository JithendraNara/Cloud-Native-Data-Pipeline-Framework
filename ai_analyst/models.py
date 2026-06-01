"""Pydantic schemas + tiny LLM client for the AI analyst."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., description="Natural-language question about the data.")


class AskResponse(BaseModel):
    question: str
    sql: str
    rows: List[Dict[str, Any]]
    answer: str
    table_count: int


class PlanRequest(BaseModel):
    goal: str


class PlanStep(BaseModel):
    question: str
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    answer: Optional[str] = None
    error: Optional[str] = None
    why: Optional[str] = None


class PlanResponse(BaseModel):
    goal: str
    steps: List[PlanStep]


class MiniMaxClient:
    """MiniMax chat client. Uses MiniMax-M2 (production) or M2.7 (light)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "MiniMax-M2"):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.model = model
        self.base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")

    def chat(self, system: str, user: str, temperature: float = 0.1) -> str:
        if not self.api_key:
            return f"[local fallback] {user[:300]}"
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
