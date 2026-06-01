# Cloud-Native Data Pipeline Framework

> **End-to-end modern data stack, AWS-native, AI-augmented. Production patterns from 2026, ready to deploy.**

[![CI/CD](https://github.com/JithendraNara/Cloud-Native-Data-Pipeline-Framework/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/JithendraNara/Cloud-Native-Data-Pipeline-Framework/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Iceberg v3](https://img.shields.io/badge/Apache_Iceberg-v3-blue)](https://iceberg.apache.org/)
[![dbt Fusion](https://img.shields.io/badge/dbt-Fusion-orange)](https://www.getdbt.com/)
[![AI Analyst](https://img.shields.io/badge/AI-MiniMax--M2-green)](https://api.minimax.chat/)

A reference implementation of a **modern, AI-augmented data platform**:
**S3 + Apache Iceberg v3 + dbt Fusion + Airflow 3 + Great Expectations + AI Data Analyst**.

Designed to run on AWS, but **fully runnable locally with zero AWS credentials** (MinIO + Iceberg REST + DuckDB).

---

## 🏗️ Architecture

```
                     ┌────────────────────────────────────────────────┐
                     │             Sources (S3 / API / Kinesis)        │
                     └──────────────────────┬─────────────────────────┘
                                            │ (S3 drop / EventBridge / API)
                                            ▼
                     ┌────────────────────────────────────────────────┐
                     │  Ingestion Lambda (PyIceberg v3)               │
                     │  Writes raw → Bronze Iceberg tables in S3       │
                     └──────────────────────┬─────────────────────────┘
                                            │ (time-traveled, partitioned, ACID)
                                            ▼
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  AWS Glue Catalog (Iceberg v3)  ──  S3: bronze / silver / gold buckets     │
   └────────────────────────────────────┬───────────────────────────────────────┘
                                        │
                                        ▼
                     ┌────────────────────────────────────────────────┐
                     │  dbt Fusion Engine                              │
                     │  Bronze → Silver → Gold with Python UDFs       │
                     └──────────────────────┬─────────────────────────┘
                                            │
                                            ▼
                     ┌────────────────────────────────────────────────┐
                     │  Great Expectations data quality suite         │
                     │  + Iceberg snapshot freshness check            │
                     └──────────────────────┬─────────────────────────┘
                                            │
                                            ▼
                     ┌────────────────────────────────────────────────┐
                     │  AI Data Analyst (FastAPI + MiniMax-M2)        │
                     │  NL → SQL → Result + Natural-language answer   │
                     └────────────────────────────────────────────────┘

   Orchestrated end-to-end by Airflow 3.
   Infrastructure as Code: Terraform (VPC, S3, Glue, IAM, Lambda, Athena).
   Local dev: Docker Compose (MinIO + Iceberg REST + Postgres + AI Analyst).
```

---

## 🧱 The Modern Data Stack (2026)

| Layer | Technology | Why |
|-------|-----------|-----|
| **Storage** | S3 + Apache **Iceberg v3** | Open table format, time travel, hidden partitioning, row-level deletes. No vendor lock-in. |
| **Catalog** | AWS Glue (prod) / Iceberg REST (local) | Iceberg v3 native. Picked over Hive metastore — Glue wins for AWS-first shops. |
| **Transform** | **dbt Fusion** engine | Latest. Python UDFs on Snowflake/BigQuery. DuckDB for local dev. |
| **Orchestration** | **Airflow 3** | Industry standard. CeleryExecutor for prod, SequentialExecutor for dev. |
| **Ingestion** | **Lambda + PyIceberg** | Event-driven, scales to zero. Triggers on S3 drop or schedule. |
| **Query** | **Athena** (Trino SQL) | Serverless, Iceberg-native, pay-per-query. |
| **Quality** | **Great Expectations + Soda** | Open source, declarative contracts on Gold tables. |
| **AI Layer** | **MiniMax-M2** (LLM) + FastAPI | NL-to-SQL, multi-step plans, BI ready. |
| **IaC** | **Terraform** (modules per layer) | VPC, storage, IAM, ingestion, monitoring. |
| **Observability** | CloudWatch + SNS + Slack | Alarms on pipeline failures, freshness, schema drift. |
| **CI/CD** | **GitHub Actions** | Lint, test, dbt build (DuckDB), Terraform validate, Docker build, security scan. |

---

## 🚀 Quickstart (5 minutes, local)

Zero AWS needed. Pure Docker.

```bash
# 1. Clone
git clone https://github.com/JithendraNara/Cloud-Native-Data-Pipeline-Framework.git
cd Cloud-Native-Data-Pipeline-Framework

# 2. Generate sample data
python scripts/generate_sample_data.py --rows 50000 --output sample/events.json

# 3. Bring up the local stack
docker compose up -d

# 4. Wait ~30s for MinIO + Iceberg REST to come up
# MinIO console: http://localhost:9001 (minioadmin / minioadmin)

# 5. Seed DuckDB and run dbt locally
python scripts/local_seed.py
cd dbt
mkdir -p ~/.dbt && cp profiles.yml.example ~/.dbt/profiles.yml
DBT_PROFILES_DIR=~/.dbt dbt build --profile data_pipeline --target local
cd ..

# 6. Ask the AI analyst
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the total gross revenue in the last 7 days?"}'
# → { "sql": "...", "rows": [...], "answer": "..." }
```

---

## 🏗️ Production Deploy (AWS)

```bash
# 1. Configure
cd terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
# edit with your values

# 2. Provision
terraform init
terraform plan
terraform apply

# 3. Build and push images (CI does this; manual fallback)
docker build -t ghcr.io/your-org/data-pipeline/ai-analyst:latest ai_analyst/
docker push ghcr.io/your-org/data-pipeline/ai-analyst:latest

# 4. Deploy the AI analyst (Lambda or ECS)
aws lambda create-function \
  --function-name data-pipeline-ai-analyst-prod \
  --package-type Image \
  --code ImageUri=ghcr.io/your-org/data-pipeline/ai-analyst:latest \
  --role arn:aws:iam::ACCOUNT:role/data-pipeline-analyst-lambda-prod \
  --timeout 60

# 5. Set Airflow variables
export AIRFLOW__WEBSERVER__BASE_URL=https://airflow.your-domain.com
# (production Airflow deployment is out of scope here — see the DAGs in airflow/dags/)

# 6. Watch it run
# Every hour: ingest → dbt → quality check → AI eval
```

---

## 📁 Repository Structure

```
.
├── ai_analyst/                 # FastAPI + MiniMax AI data analyst
│   ├── server.py               # /ask, /plan, /schema endpoints
│   ├── models.py               # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
│
├── airflow/dags/
│   └── data_pipeline_dag.py    # End-to-end Airflow 3 DAG
│
├── data_quality/
│   └── gx_suite.py             # Great Expectations validation
│
├── dbt/                        # dbt Fusion project
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── models/
│   │   ├── sources.yml
│   │   ├── staging/            # Bronze → typed
│   │   ├── silver/             # Cleaned, deduplicated
│   │   └── gold/               # BI-ready aggregations
│   ├── tests/
│   │   └── gold.yml
│   └── macros/
│       └── event_categorizer.py  # Python UDF
│
├── docker-compose.yml          # Local stack (MinIO + Iceberg REST + AI analyst)
│
├── lambda/ingestion/           # PyIceberg ingestion Lambda
│   ├── handler.py
│   └── requirements.txt
│
├── scripts/
│   ├── generate_sample_data.py # Synthetic event generator
│   └── local_seed.py           # Seeds DuckDB for local dbt runs
│
├── terraform/
│   ├── modules/
│   │   ├── vpc/                # Multi-AZ networking
│   │   ├── storage/            # S3 + Glue Iceberg catalog
│   │   ├── iam/                # Roles for Lambda, Glue, Airflow
│   │   ├── ingestion/          # Lambda + EventBridge
│   │   └── monitoring/         # CloudWatch + SNS
│   └── environments/dev/
│       └── main.tf
│
├── .github/workflows/ci-cd.yml # CI: lint, dbt build, terraform validate, AI boot test
└── sample/events.json          # Generated sample data
```

---

## 🤖 The AI Analyst

The most novel piece. **A natural-language interface to your data warehouse.**

```bash
# One-shot question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which event_type has the highest avg amount among logged-in users last week?"}'

# → {
#     "sql": "SELECT event_type, AVG(amount) ... FROM ... GROUP BY 1",
#     "rows": [...],
#     "answer": "Purchase events had the highest avg amount at $87.42..."
#   }

# Multi-step plan (agent)
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{"goal": "Diagnose why revenue dropped 20% last week"}'
```

**Why it matters:** the analyst doesn't just generate SQL. It **executes** it, **summarizes** the result, and can **chain** multiple Q&A steps into a single diagnostic flow. This is the agentic BI pattern the entire industry is moving toward in 2026.

---

## 🧪 What `dbt build` Actually Produces

```
Found 4 models, 8 tests, 1 source, 1 seed
.
└── data_pipeline
    ├── stg_events                    [view]   (Bronze → typed)
    ├── events_cleaned                [table]  (Silver)
    ├── daily_user_revenue            [table]  (Gold)
    ├── event_type_funnel             [table]  (Gold)
    └── event_categorizer             [table]  (Gold + Python UDF)
```

All written as **Iceberg v3** tables, partitioned by `event_date`, with time-travel enabled.

---

## 📊 Key Patterns Demonstrated

- **Medallion architecture** (Bronze → Silver → Gold) on Iceberg
- **Open table format** (Iceberg v3) for cross-engine compatibility
- **dbt Fusion** with Python UDFs for the categorization lookup
- **EventBridge + Lambda** for event-driven ingestion
- **AI agent** that goes NL → SQL → Result → NL answer
- **DuckDB local dev** so contributors don't need AWS
- **Terraform modules** for every layer (VPC, S3, IAM, Lambda, monitoring)
- **GitHub Actions** that run dbt build on every PR (with DuckDB)
- **Great Expectations** validating Gold tables after every run

---

## 🔭 What You Could Add Next

- **Stream ingestion** with Kafka / Kinesis instead of S3 drops
- **Real-time serving** with Pinot / Druid on top of Iceberg
- **Data contracts** with OpenLineage + Marquez
- **Reverse ETL** with Hightouch / Census to push Gold into SaaS tools
- **Lakehouse monitoring** with Iceberg's `metadata_log` + S3 events

---

## 🧰 Tech Versions (verified May 2026)

- `dbt-core` 1.8+ (Fusion engine)
- `pyiceberg` 0.9.1
- `apache-airflow` 3.0.0
- `terraform` 1.5+
- `fastapi` 0.110
- `duckdb` 0.10+
- `awswrangler` 3.5+

---

## 📝 License

MIT — fork it, ship it, build on it.
