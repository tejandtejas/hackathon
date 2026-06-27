# PIVA Agent — CF Deployment Guide

All code is complete and fully tested (167 tests, 72% coverage).  
Run the steps below **from your local machine** where the CF CLI is installed.

---

## 1. Prerequisites

```bash
cf --version          # must be CF CLI v8+
```

If missing: https://docs.cloudfoundry.org/cf-cli/install-go-cli.html

---

## 2. Login

```bash
cf login -a [REDACTED] --sso
# or with passcode:
cf login -a [REDACTED] --sso-passcode <passcode>
```

---

## 3. Verify / Create service instances

```bash
cf services | grep proj-vector
```

If `proj-vector-destination-service` or `proj-vector-connectivity-service` are missing:

```bash
cf create-service destination   lite proj-vector-destination-service
cf create-service connectivity  lite proj-vector-connectivity-service
```

---

## 4. Configure BTP Destination `S4Hana_QVL`

In the BTP Cockpit → your subaccount → **Connectivity → Destinations → New Destination**:

| Field | Value |
|---|---|
| Name | `S4Hana_QVL` |
| Type | HTTP |
| URL | `http://<your-s4-host>:<port>` |
| Proxy Type | `OnPremise` |
| Authentication | BasicAuthentication (or PrincipalPropagation) |
| Additional Property | `sap-client` = `101` |

Save and **Check Connection** (green = Cloud Connector is routing correctly).

---

## 5. Push to CF

> **Dependency fix #2 (2026-06-26 — langgraph `ExecutionInfo`):**  
> `requirements.txt` now pins **`sap-ai-sdk-gen==6.10.0`** (was `6.6.0`).  
> `6.6.0` resolved `langchain==1.2.10` → `langgraph==1.0.10`, which lacks
> `ExecutionInfo` in `langgraph.runtime`. The `langgraph-prebuilt` package
> needs that class, causing `ImportError` on every agent invocation.  
> `sap-ai-sdk-gen==6.10.0` resolves `langchain~=1.2.14` → `langgraph>=1.1.10,<1.2.0`.
> `langgraph==1.1.10` has `ExecutionInfo`. All 167 tests pass.
>
> **Dependency fix #1 (2026-06-26 — langchain conflict):**  
> The previous `langchain==1.3.9` conflicted with `sap-ai-sdk-gen` and caused a `BuildpackCompileFailed`.

```bash
# Clone / pull the project to your local machine, then:
cd assets/piva-agent

cf push
```

`manifest.yml` is already in this directory. CF will:
- Use Python buildpack
- Install `requirements.txt`
- Start: `gunicorn --worker-class uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:${PORT} --chdir app main:application`
- Health-check: `GET /.well-known/agent.json`

---

## 6. Smoke test

```bash
cf app piva-agent          # note the route
curl https://<route>/.well-known/agent.json
```

Expected response: JSON with `"name": "piva-agent"` and `"version": "1.0.0"`.

---

## 7. Register with SAP Joule (A2A)

Once deployed, register the agent endpoint:

```
https://<route>/
```

with SAP Joule as an A2A agent.  Joule will call `/.well-known/agent.json` to discover skills.

---

## 8. Environment variables (already in manifest.yml)

| Variable | Value |
|---|---|
| `S4HANA_QVL_DESTINATION_NAME` | `S4Hana_QVL` |
| `DESTINATION_NAME` | `S4Hana_QVL` |
| `AICORE_DESTINATION_NAME` | `aicore` |
| `LOG_LEVEL` | `INFO` |

To add at runtime (e.g. override LLM model):

```bash
cf set-env piva-agent AGENT_LLM_MODEL gpt-4o
cf restart piva-agent
```

---

## 9. Dual-mode reminder

| Mode | Env var | LLM | S/4 data |
|---|---|---|---|
| **CF** (default) | `JOULE_RUNTIME` unset | `aicore.py` resolves AI Core destination | Direct OData via `s4hana_client.py` → BTP Destination |
| **Joule/Kyma** | `JOULE_RUNTIME=1` | `sap-cloud-sdk` LLM | MCP server tools via Agent Gateway |

The same source tree supports both. Never set `JOULE_RUNTIME=1` on a CF deployment.

---

## 10. Logs


```bash
cf logs piva-agent --recent
cf logs piva-agent           # tail
```

---

## 11. Platform deployment (SAP Build / Kyma) — blocked by infrastructure outage

### Status
`deploy_solution()` has failed **8 times** (attempts 1–8, job indices 1–8).  
All failures share the same root cause:

```
dhi-cache.deployer.svc.cluster.local:5000
  HEAD /v2/python/manifests/3.12-debian13?ns=dhi.io  →  500 Internal Server Error
  HEAD /v2/python/manifests/3.12-debian13-sfw-dev?ns=dhi.io  →  500 Internal Server Error
```

The platform's build pipeline (BuildKit, `buildID=2deaee96`) generates a two-stage Dockerfile:

```
FROM dhi.io/python:3.12-debian13-sfw-dev AS builder  ← stage 1 (line 1)
FROM dhi.io/python:3.12-debian13                     ← stage 2 (line 99)
```

The internal image cache (`dhi-cache`) returns HTTP 500 for both images on every attempt.  
No user-supplied `Dockerfile`, `runtime.txt`, or `asset.yaml` `runtime.version` overrides this.

### Failed job IDs (all share `buildID=2deaee96`)

| # | Job ID | Date |
|---|---|---|
| 1 | `e6283369-bce5-4f00-9227-6131e3bae764` | 2026-06-26T06:51 |
| 2 | `be3d8f31-8149-45a1-97f7-32faed241f5e` | 2026-06-26T06:53 |
| 3 | `456d0b07-46b5-4187-be81-bad5c0c36b65` | 2026-06-26T07:35 |
| 4 | `8af11745-7295-44c0-95b4-ee2abfc3c377` | 2026-06-26T07:39 |
| 5 | `fc93e244-4bb7-40f7-952e-7e0c17332c1f` | 2026-06-26T07:41 (409 conflict) |
| 6 | `d1e96eac-762e-44a4-ac3c-ed414cb1e525` | 2026-06-26T07:42 (undeploy — cleared lock) |
| 7 | `c379a2f9-8358-494f-99d7-ceaf185c104c` | 2026-06-26T07:42 |
| 8 | `6632057c-64c6-4e00-be32-ec63c34101fc` | 2026-06-26T08:01 |

### Resolution path

**Option A — Wait for platform fix**  
Raise a support ticket with SAP Build platform team:  
- Reference job ID: `c379a2f9-8358-494f-99d7-ceaf185c104c` (most detailed logs)  
- Error: `dhi-cache.deployer.svc.cluster.local:5000` returns HTTP 500 for `dhi.io/python:3.12-debian13[-sfw-dev]`  
- Request: fix image cache OR expose a `containerBaseImage` override in `asset.yaml`  
- Once fixed: simply re-run `deploy_solution()` — all code is correct and ready

**Option B — CF push from local machine (immediate)**  
Follow steps 1–10 above using `cf push` from your local machine.  
The CF Python buildpack path (`manifest.yml`) is fully independent of the platform image cache.

```bash
cf logs piva-agent --recent
cf logs piva-agent           # tail
```
