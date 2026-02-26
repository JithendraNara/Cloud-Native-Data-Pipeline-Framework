# Cloud-Native Data Pipeline Framework

CI/CD-enabled, modular ELT framework for AWS with infrastructure as code.

## Architecture

```
Source Systems → Ingestion (Python) → S3 Raw → Glue Catalog → Redshift/Athena → BI
                                          ↑
                          Airflow orchestration + Terraform provisioning
```

## Tech Stack

| Layer | Technology |
|---|---|
| Pipeline Logic | Python |
| Orchestration | Apache Airflow |
| Infrastructure | Terraform (HCL) |
| Cloud | AWS — S3, Glue, Redshift, Lambda |
| CI/CD | GitHub Actions |

## Features

- Modular ELT components — each step is independently testable and deployable
- Infrastructure as Code — full AWS stack provisioned via Terraform
- CI/CD pipelines — automated testing and deployment through GitHub Actions
- Data quality validation — built-in checks at each pipeline stage
- Monitoring and alerting — CloudWatch integration for pipeline health

## Setup

```bash
git clone https://github.com/JithendraNara/Cloud-Native-Data-Pipeline-Framework.git
cd Cloud-Native-Data-Pipeline-Framework

# Provision infrastructure
cd terraform && terraform init && terraform apply

# Run pipelines
cd ../airflow && docker-compose up -d
```
