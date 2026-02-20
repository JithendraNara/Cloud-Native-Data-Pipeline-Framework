# Cloud-Native Data Pipeline Framework

![CI/CD](https://github.com/JithendraNara/Cloud-Native-Data-Pipeline-Framework/workflows/CI/CD/badge.svg)
![Coverage](https://codecov.io/gh/JithendraNara/Cloud-Native-Data-Pipeline-Framework/branch/main/graph/badge.svg)

Enterprise-grade modular ELT framework v2.0 - massively upgraded from v1.

## What's New in v2.0

### Infrastructure (Terraform)
- **VPC Module** - Multi-AZ VPC with public/private subnets, NAT Gateways, EIPs
- **Security Groups** - Comprehensive SGs for ALB, EC2, RDS, ECS, ElastiCache, Bastion
- **Monitoring Module** - CloudWatch alarms, SNS alerts, dashboards
- **ECS Support** - Containerized ETL workloads with Fargate

### DevOps
- **GitHub Actions CI/CD** - Full pipeline: lint → test → security scan → build → deploy
- **Docker Compose** - LocalStack, PostgreSQL, Redis, Airflow, Grafana, Prometheus
- **Trivy Security Scanning** - Vulnerability detection
- **Multi-stage Dockerfile** - Optimized ETL container

### Data Pipeline
- **Configuration Module** - Centralized config management
- **Monitoring Module** - Structured logging, metrics, data quality checks
- **Comprehensive Tests** - Unit + integration tests with pytest

## Architecture

```
AWS Cloud
┌─────────────────────────────────────────────────────────────┐
│  VPC (10.0.0.0/16) - us-east-1a, us-east-1b                 │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Public Subnets  │  │ Private Subnets │                  │
│  │ 10.0.1.0/24     │  │ 10.0.10.0/24    │                  │
│  │ 10.0.2.0/24     │  │ 10.0.11.0/24    │                  │
│  └────────┬────────┘  └────────┬────────┘                  │
│           │                    │                           │
│  ┌────────▼────────┐  ┌────────▼────────┐                  │
│  │  NAT Gateway   │  │  ECS Fargate    │                  │
│  │  ALB           │  │  (Airflow)      │                  │
│  └─────────────────┘  └────────┬────────┘                  │
│                                 │                           │
│  ┌──────────────────────────────▼────────────────────────┐│
│  │              Private Subnet Services                   ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      ││
│  │  │ RDS (pg)    │ │ ElastiCache │ │ S3 Bucket   │      ││
│  │  │ Star Schema │ │ (Redis)     │ │ Data Lake   │      ││
│  │  └─────────────┘ └─────────────┘ └─────────────┘      ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘

CloudWatch Monitoring → SNS → Email/PagerDuty
```

## Quick Start

### Local Development
```bash
docker compose -f docker/docker-compose.yml up -d

# Services:
# Airflow:    http://localhost:8080 (airflow/airflow)
# pgAdmin:    http://localhost:5050 (admin@pipeline.local/admin)
# Grafana:    http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
# LocalStack: http://localhost:4566
```

### Deploy to AWS
```bash
cd terraform/environments/prod
terraform init
terraform plan
terraform apply
```

## Project Structure (v2.0)

```
.
├── .github/workflows/ci-cd.yml    # Full CI/CD pipeline
├── docker/
│   ├── docker-compose.yml         # Local dev environment
│   ├── Dockerfile.etl             # ETL container
│   ├── prometheus/                # Metrics config
│   └── grafana/                   # Dashboards
├── etl/src/
│   ├── api/                       # FastAPI endpoints
│   ├── config/                    # Config management
│   ├── extract/                   # REST extraction
│   ├── transform/                 # Data transformation
│   ├── load/                      # RDS loading
│   ├── utils/                     # S3 utilities
│   ├── monitoring/                # Logging, metrics, quality
│   └── tests/                     # Unit tests
├── airflow/dags/                  # Airflow DAGs
├── terraform/
│   ├── environments/prod/         # Production Terraform
│   └── modules/
│       ├── vpc/                   # Networking
│       ├── security-group/        # Firewall rules
│       ├── s3/                    # Storage
│       ├── rds/                   # PostgreSQL
│       ├── iam/                   # Roles/policies
│       ├── monitoring/            # CloudWatch
│       └── ecs/                   # Containers
├── tests/
│   ├── unit/                      # Unit tests
│   └── integration/               # Integration tests
└── sql/schemas/                   # Star schema DDL
```

## Features

| Category | Features |
|----------|----------|
| **Infrastructure** | VPC, Subnets, NAT, IGW, Security Groups, RDS, S3, IAM, ECS |
| **Pipeline** | REST extraction, transformation, S3 staging, RDS loading |
| **Monitoring** | CloudWatch alarms, SNS alerts, dashboards, structured logging |
| **Data Quality** | Null checks, duplicate detection, value range validation |
| **CI/CD** | Lint, test, security scan, build, deploy |
| **Local Dev** | Docker Compose with 8 services |

## Testing

```bash
pytest --cov=etl.src --cov-report=html
flake8 etl/src/ --max-line-length=120
bandit -r etl/src/
```

## Monitoring Alerts

- RDS CPU > 80%
- RDS Storage > 85%
- ECS CPU/Memory > 80%
- Pipeline task failures

## v1 → v2.0 Diff

| Component | v1 | v2.0 |
|-----------|----|----|
| Networking | Basic | VPC + multi-AZ + NAT |
| Security | Minimal SGs | 6 comprehensive SGs |
| Monitoring | Basic | CloudWatch + SNS + Dashboards |
| CI/CD | None | Full GitHub Actions |
| Docker | None | Compose + Dockerfile |
| Testing | None | Unit + Integration |
| Config | Hardcoded | Centralized module |

---

Built massive. 🦞
