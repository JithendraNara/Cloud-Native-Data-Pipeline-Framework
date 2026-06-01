"""
AI Data Analyst Agent.

Endpoints:
  POST /ask        NL → SQL → result + answer (single-shot, with optional session context)
  POST /ask/stream NL → SQL → result + streaming answer (server-sent events)
  POST /plan       Multi-step investigation (agent-style)
  POST /chat       Multi-turn conversation with session memory
  GET  /session/:id Get session info (turn count, recent SQL, TTL)
  DELETE /session/:id Clear a session
  GET  /schema     Reflect available tables
  GET  /health     Health check
  GET  /stats      Session store stats

Stack:
  FastAPI + MiniMax-M2 (LLM) + PyIceberg (catalog) + DuckDB (local) / Athena (prod)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from models import (
    AskRequest,
    AskResponse,
    ChatRequest,
    ChatResponse,
    MiniMaxClient,
    PlanRequest,
    PlanResponse,
    PlanStep,
    SessionInfo,
)
from session import Session, SessionStore, Turn, store as default_store

log = logging.getLogger("ai-analyst")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="AI Data Analyst Agent",
    description="Natural-language interface to the data pipeline's Gold layer. Multi-turn, streaming, agent-style.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment
DATABASE = os.environ.get("ICEBERG_GOLD_NAMESPACE", "gold_dev")
ATHENA_WG = os.environ.get("ATHENA_WORKGROUP", "data-pipeline-dev")
ATHENA_OUTPUT = os.environ.get("ATHENA_OUTPUT", "s3://data-pipeline-warehouse/results/")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
SESSIONS: SessionStore = default_store

LLMClient = MiniMaxClient


# --- SQL generation + execution ---

SQL_GEN_SYSTEM = """You are a SQL generator for Apache Iceberg tables in AWS Athena (Trino SQL).

Available tables (Gold layer):
{schema}

Conversation context (for follow-up questions):
{history}

Rules:
- Use Trino SQL syntax (date_trunc, interval, current_date, etc.).
- Use double-quoted identifiers only when needed.
- For follow-up questions, reference the prior SQL if appropriate (e.g., "the same query but filtered to ...")
- Always filter by event_date >= current_date - interval '30' day unless the user asks for a different window.
- Wrap datetime/timestamp comparisons in cast(... as timestamp).
- Return only the SQL — no prose, no markdown fences."""


def get_schema() -> Dict[str, List[Dict[str, str]]]:
    """Reflect schema for Gold tables via Glue catalog."""
    import boto3

    glue = boto3.client("glue", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    tables = []
    paginator = glue.get_paginator("get_tables")
    for page in paginator.paginate(DatabaseName=DATABASE):
        for t in page["TableList"]:
            tables.append(
                {
                    "table": t["Name"],
                    "columns": [
                        {"name": c["Name"], "type": c["Type"]}
                        for c in t.get("StorageDescriptor", {}).get("Columns", [])
                    ],
                }
            )
    return {t["table"]: t["columns"] for t in tables}


def run_query(sql: str) -> List[Dict[str, Any]]:
    """Execute via Athena, return rows as list of dicts."""
    try:
        import awswrangler as wr

        df = wr.athena.read_sql_query(
            sql,
            database=DATABASE,
            workgroup=ATHENA_WG,
            s3_output=ATHENA_OUTPUT,
            ctas_approach=False,
        )
        return df.to_dict(orient="records")
    except Exception as e:
        log.error("Query failed: %s | SQL=%s", e, sql)
        raise


def extract_sources(sql: str) -> List[Dict[str, str]]:
    """Extract the tables and columns referenced in the SQL for transparency."""
    sources: List[Dict[str, str]] = []
    # Match FROM / JOIN <table_name>
    table_pattern = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w\.]*)", re.IGNORECASE)
    tables = set(table_pattern.findall(sql))
    for t in tables:
        sources.append({"type": "table", "name": t})
    return sources


def generate_sql(question: str, history: str = "") -> str:
    """Generate SQL for a question, optionally with conversation history."""
    schema = get_schema()
    schema_str = "\n".join(
        f"- {name}({', '.join(c['name'] + ':' + c['type'] for c in cols)})"
        for name, cols in schema.items()
    )
    llm = LLMClient()
    system = SQL_GEN_SYSTEM.format(schema=schema_str, history=history or "(none)")
    raw = llm.chat(system=system, user=question).strip().strip("`")
    if raw.lower().startswith("sql\n"):
        raw = raw[4:]
    return raw


# --- Endpoints ---

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/schema")
def schema() -> Dict[str, Any]:
    """Return the available Gold tables and their columns."""
    try:
        return {"database": DATABASE, "tables": get_schema()}
    except Exception as e:
        raise HTTPException(500, f"Schema reflection failed: {e}")


@app.get("/stats")
def stats() -> Dict[str, Any]:
    """Session store stats."""
    return SESSIONS.stats()


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """NL question → SQL → result + natural-language summary.

    If session_id is provided, the prior conversation is included as context.
    """
    history = ""
    if req.session_id:
        sess = SESSIONS.get(req.session_id)
        if sess:
            history = sess.to_prompt_context()

    sql = generate_sql(req.question, history)
    log.info("Generated SQL: %s", sql)
    rows = run_query(sql)

    summary = LLMClient().chat(
        system=(
            "You are a data analyst. Given the question, SQL, and result rows, "
            "write a 2-3 sentence natural-language answer. Be specific. Cite numbers. "
            "If the result is empty, suggest why that might be."
        ),
        user=f"Question: {req.question}\nSQL: {sql}\nRows (first 50): {rows[:50]}",
    )

    sources = extract_sources(sql)

    if req.session_id:
        sess = SESSIONS.get_or_create(req.session_id)
        sess.add_turn(Turn(role="user", content=req.question))
        sess.add_turn(Turn(role="assistant", content=summary, sql=sql, rows=rows[:20]))

    return AskResponse(
        question=req.question,
        sql=sql,
        rows=rows,
        answer=summary,
        table_count=len(rows),
        sources=sources,
    )


@app.post("/ask/stream")
def ask_stream(req: AskRequest) -> StreamingResponse:
    """Streaming version of /ask. Sends tokens as SSE.

    Wire format: server-sent events. Each event has `data: <json>` where
    the JSON object has {event, data, ts} fields.
    """
    history = ""
    if req.session_id:
        sess = SESSIONS.get(req.session_id)
        if sess:
            history = sess.to_prompt_context()

    sql = generate_sql(req.question, history)

    def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'event': 'sql', 'data': sql, 'ts': 0})}\n\n"

        try:
            rows = run_query(sql)
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"
            return

        yield f"data: {json.dumps({'event': 'rows', 'data': rows[:100], 'ts': 1})}\n\n"

        # Stream the natural-language answer
        summary_prompt = (
            f"Question: {req.question}\nSQL: {sql}\nRows (first 50): {rows[:50]}"
        )
        full_answer = ""
        for token in LLMClient().chat_stream(
            system=(
                "You are a data analyst. Given the question, SQL, and result rows, "
                "write a 2-3 sentence natural-language answer. Be specific. Cite numbers."
            ),
            user=summary_prompt,
        ):
            full_answer += token
            yield f"data: {json.dumps({'event': 'token', 'data': token, 'ts': 2})}\n\n"

        yield f"data: {json.dumps({'event': 'done', 'data': {'full_answer': full_answer, 'row_count': len(rows)}, 'ts': 3})}\n\n"

        if req.session_id:
            sess = SESSIONS.get_or_create(req.session_id)
            sess.add_turn(Turn(role="user", content=req.question))
            sess.add_turn(Turn(role="assistant", content=full_answer, sql=sql, rows=rows[:20]))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    """Multi-step plan: break a goal into Q&A sub-questions and execute them."""
    llm = LLMClient()
    plan_system = """You are a data analyst. Given a high-level business goal, return a JSON array of
3-6 concrete analytical sub-questions that, together, would answer the goal.
Each entry must have: {"question": "...", "why": "..."}.
Return ONLY valid JSON."""

    plan_json = llm.chat(system=plan_system, user=req.goal)
    try:
        steps = json.loads(plan_json)
    except json.JSONDecodeError:
        steps = [{"question": req.goal, "why": "Default fallback."}]

    executed: List[PlanStep] = []
    for step in steps:
        q = step.get("question", "").strip()
        if not q:
            continue
        try:
            result = ask(AskRequest(question=q, session_id=req.session_id))
            executed.append(PlanStep(
                question=q,
                sql=result.sql,
                rows=result.rows[:20],
                answer=result.answer,
            ))
        except Exception as e:
            executed.append(PlanStep(question=q, error=str(e), why=step.get("why")))

    return PlanResponse(goal=req.goal, steps=executed)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Multi-turn conversation.

    A session_id is required. The prior turns are loaded as context.
    Returns the answer plus the current turn count.
    """
    sess = SESSIONS.get_or_create(req.session_id)
    history = sess.to_prompt_context()
    sql = generate_sql(req.message, history)
    log.info("Chat SQL: %s", sql)
    rows = run_query(sql)

    summary = LLMClient().chat(
        system=(
            "You are a conversational data analyst. Given the conversation history, "
            "the latest question, the generated SQL, and the result rows, "
            "write a 2-3 sentence natural-language answer. Be specific. "
            "Reference prior turns when relevant."
        ),
        user=(
            f"Conversation so far:\n{history}\n\n"
            f"New question: {req.message}\n"
            f"SQL: {sql}\nRows (first 50): {rows[:50]}"
        ),
    )

    sess.add_turn(Turn(role="user", content=req.message))
    sess.add_turn(Turn(role="assistant", content=summary, sql=sql, rows=rows[:20]))

    return ChatResponse(
        session_id=req.session_id,
        question=req.message,
        sql=sql,
        rows=rows,
        answer=summary,
        turn_count=len(sess.turns),
        sources=extract_sources(sql),
    )


@app.get("/session/{session_id}", response_model=SessionInfo)
def get_session(session_id: str) -> SessionInfo:
    """Get session info: turn count, recent SQL count, TTL remaining."""
    sess = SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, f"Session {session_id} not found")
    import time
    ttl_remaining = max(0, int(sess.last_activity_at + 60 * 60 - time.time()))
    return SessionInfo(
        session_id=session_id,
        turn_count=len(sess.turns),
        recent_sql_count=len(sess.recent_sql),
        created_at=sess.created_at,
        last_activity_at=sess.last_activity_at,
        ttl_seconds_remaining=ttl_remaining,
    )


@app.delete("/session/{session_id}")
def clear_session(session_id: str) -> Dict[str, str]:
    """Delete a session from memory."""
    if SESSIONS.delete(session_id):
        return {"ok": "true", "message": f"Deleted session {session_id}"}
    raise HTTPException(404, f"Session {session_id} not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
