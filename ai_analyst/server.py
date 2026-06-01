"""
AI Data Analyst Agent.

Endpoints:
  POST /ask   {"question": "..."}  → NL → SQL → result + natural-language answer
  GET  /schema → list of available tables + columns
  POST /plan  {"goal": "..."}     → multi-step plan with agent execution

Stack:
  FastAPI + MiniMax M2.7 (LLM) + PyIceberg (catalog) + DuckDB (local exec) / Athena (prod)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import AskRequest, AskResponse, PlanRequest, PlanResponse, MiniMaxClient

log = logging.getLogger("ai-analyst")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="AI Data Analyst Agent",
    description="Natural-language interface to the data pipeline's Gold layer.",
    version="1.0.0",
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


# --- LLM client (re-export from models.py for convenience) ---

LLMClient = MiniMaxClient


# --- SQL generation + execution ---

SQL_GEN_SYSTEM = """You are a SQL generator for Apache Iceberg tables in AWS Athena (Trino SQL).

Available tables (Gold layer):
{schema}

Rules:
- Use Trino SQL syntax (date_trunc, interval, current_date, etc.).
- Use double-quoted identifiers only when needed.
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
                        {"name": c["Name"], "type": c["Type"]} for c in t.get("StorageDescriptor", {}).get("Columns", [])
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


# --- Endpoints ---

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/schema")
def schema() -> Dict[str, Any]:
    """Return the available Gold tables and their columns."""
    try:
        return {"database": DATABASE, "tables": get_schema()}
    except Exception as e:
        raise HTTPException(500, f"Schema reflection failed: {e}")


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """NL question → SQL → result + natural-language summary."""
    schema = get_schema()
    schema_str = "\n".join(
        f"- {name}({', '.join(c['name'] + ':' + c['type'] for c in cols)})"
        for name, cols in schema.items()
    )

    llm = LLMClient()
    system = SQL_GEN_SYSTEM.format(schema=schema_str)
    sql = llm.chat(system=system, user=req.question).strip().strip("`")
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()

    log.info("Generated SQL: %s", sql)
    rows = run_query(sql)

    summary_system = "You are a data analyst. Given the question, SQL, and result rows, write a 2-3 sentence natural-language answer. Be specific. Cite numbers."
    summary = llm.chat(
        system=summary_system,
        user=f"Question: {req.question}\nSQL: {sql}\nRows (first 50): {rows[:50]}",
    )

    return AskResponse(
        question=req.question,
        sql=sql,
        rows=rows,
        answer=summary,
        table_count=len(rows),
    )


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    """Multi-step plan: break a goal into Q&A sub-questions and execute them."""
    llm = LLMClient()
    plan_system = """You are a data analyst. Given a high-level business goal, return a JSON array of
3-6 concrete analytical sub-questions that, together, would answer the goal.
Each entry must have: {"question": "...", "why": "..."}.
Return ONLY valid JSON."""

    plan_json = llm.chat(system=plan_system, user=req.goal)
    import json
    try:
        steps = json.loads(plan_json)
    except json.JSONDecodeError:
        # Fallback to single question
        steps = [{"question": req.goal, "why": "Default fallback."}]

    # Execute each step
    executed = []
    for step in steps:
        q = step.get("question", "")
        if not q:
            continue
        try:
            ask_req = AskRequest(question=q)
            result = ask(ask_req)
            executed.append(
                {
                    "question": q,
                    "sql": result.sql,
                    "rows": result.rows[:20],
                    "answer": result.answer,
                }
            )
        except Exception as e:
            executed.append({"question": q, "error": str(e)})

    # Normalize dicts to PlanStep instances
    from models import PlanStep as _PlanStep
    normalized = [_PlanStep(**{k: v for k, v in s.items() if k in _PlanStep.model_fields}) for s in executed]
    return PlanResponse(goal=req.goal, steps=normalized)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
