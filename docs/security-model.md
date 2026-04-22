# PRIPYAT-1986 — Security & Governance Model

## Overview

This document defines the security architecture for deploying PRIPYAT-1986 in
production on Azure, following the **Azure Well-Architected Framework (WAF)
Security Pillar** and **Microsoft Cloud Security Benchmark (MCSB)**.

---

## 1. Identity & Access Control

### Azure Entra ID Integration
All human access authenticates through **Azure Entra ID** with MFA enforcement.

| Role | Permissions | Example Users |
|------|-------------|---------------|
| **Operator** | View dashboard, monitor alerts, acknowledge warnings. Cannot override SCRAM or disable ECCS. | Control room staff |
| **Supervisor** | All Operator permissions + toggle AI Intervention, review agent reasoning, approve manual overrides at risk 60–85. | Shift supervisor |
| **Admin** | All Supervisor permissions + deploy configuration, modify thresholds, access audit logs, manage users. | Plant safety engineer |
| **Auditor** (read-only) | View decision logs, audit trail, compliance reports. Cannot modify any state. | Regulatory inspector |

### Service-to-Service Authentication
- **Managed Identities** for all Azure service connections (AKS → OpenAI, AKS → Cosmos DB, AKS → Key Vault)
- No API keys stored in application code or environment variables in production
- Key Vault references used in AKS pod environment injection

---

## 2. Secret Management — Azure Key Vault

| Secret | Key Vault Name | Rotation Policy |
|--------|---------------|-----------------|
| Azure OpenAI API Key | `openai-api-key` | 90-day auto-rotation |
| Cosmos DB Connection String | `cosmos-connection` | Managed Identity (no key needed) |
| Event Hubs Connection String | `eventhubs-connection` | 90-day auto-rotation |
| AI Search Admin Key | `aisearch-admin-key` | 90-day auto-rotation |

**Access Policy**: Only AKS Managed Identity and Admin role can read secrets.
No human user has direct Key Vault data-plane access without PIM elevation.

---

## 3. Data Classification & Governance

| Data Category | Classification | Retention | Storage | Encryption |
|---------------|---------------|-----------|---------|------------|
| Reactor telemetry (sensor readings) | **Confidential** | 90 days hot, 1 year archive | Cosmos DB + Event Hubs | AES-256 at rest, TLS 1.3 in transit |
| Agent decisions & reasoning | **Internal** | 1 year (regulatory requirement) | Cosmos DB | AES-256 at rest, TLS 1.3 in transit |
| Risk scores & audit trail | **Internal** | 5 years (compliance) | Cosmos DB (immutable) | AES-256 at rest |
| LLM prompts & responses | **Confidential** | 30 days | Log Analytics (redacted) | AES-256 at rest |
| Final simulation reports | **Public** | Indefinite | Blob Storage | AES-256 at rest |
| Evacuation plans | **Restricted** | Active + 5 years | Cosmos DB | AES-256 at rest |

### Immutable Audit Trail
Every agent decision is written to Cosmos DB with a composite partition key:
```
{tick_number}_{agent_name}_{ISO_timestamp}
```
Records are write-once (no update/delete operations in application code).
Cosmos DB Change Feed enables real-time audit streaming to Log Analytics.

---

## 4. Network Security

```
┌─────────────────── Azure VNET ───────────────────────┐
│                                                       │
│  ┌─── AKS Subnet ───┐    ┌─── Services Subnet ───┐  │
│  │ FastAPI + Dashboard│───▶│ Cosmos DB (private EP) │  │
│  │ Agent Pipeline     │───▶│ Azure OpenAI (priv EP) │  │
│  │                    │───▶│ Key Vault (private EP)  │  │
│  │                    │───▶│ Event Hubs (private EP) │  │
│  └────────────────────┘    └────────────────────────┘  │
│          │                                             │
│    ┌─────▼──────┐                                      │
│    │ App Gateway │ ◄── WAF v2 (OWASP 3.2 rules)       │
│    │ + TLS term  │                                     │
│    └─────────────┘                                     │
└───────────────────────────────────────────────────────┘
         │
    Public Internet (operators via Entra ID auth)
```

- **No public endpoints** for backend services (Cosmos, OpenAI, Key Vault)
- All traffic routed through **Azure Application Gateway with WAF v2**
- NSG rules restrict AKS subnet to outbound-only for Azure PaaS services

---

## 5. Monitoring & Alerting — Azure Monitor

### Log Analytics Workspace
All telemetry flows to a centralized Log Analytics workspace:
- Container logs (AKS)
- Application Insights (FastAPI traces)
- Cosmos DB diagnostics
- Key Vault audit logs

### Alert Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| LLM Latency Breach | `avg(llm_latency_ms) > 5000` over 1 min | Sev 2 | Notify Supervisor + auto-fallback to rules |
| Pipeline Failure | Agent pipeline throws unhandled exception | Sev 1 | Page Admin + halt simulation |
| Risk Score Critical | `risk_score > 85` sustained 3+ ticks | Sev 1 | Dashboard flash + auto-SCRAM log |
| High Fallback Rate | `llm_fallback_count / total_ticks > 0.5` over 5 min | Sev 3 | Notify Admin |
| Unauthorized Access | Failed Entra ID auth > 5 attempts in 10 min | Sev 1 | Lock account + page Admin |

### Dashboards
- **Azure Monitor Workbook**: Real-time agent pipeline health, LLM call stats, cost tracking
- **Application Insights**: Request traces, dependency maps, failure analysis

---

## 6. Compliance Considerations

| Framework | Relevance | Implementation |
|-----------|-----------|----------------|
| **NRC 10 CFR 50** | Nuclear safety reporting requirements | Immutable audit trail in Cosmos DB |
| **NERC CIP** | Critical infrastructure protection | RBAC, network isolation, access logging |
| **IAEA Safety Standards** | Nuclear safety culture requirements | AI cannot weaken safety floor (guardrail pattern) |
| **GDPR/Data Protection** | If deployed with personal data | Data classification, retention policies, right to delete (non-audit data only) |
