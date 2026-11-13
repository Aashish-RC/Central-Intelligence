# Central Intelligence (Aevum CI Brain) API Specification

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000` (or configured gateway ingress)  
**Authentication Scheme:** `Authorization: Bearer <Keycloak_JWT>`  
**Content-Type:** `application/json`

---

## Overview

Central Intelligence exposes unified REST interfaces for interacting with its cognitive engine, context management, memory tiers, execution runtimes, billing meters, and safety controls.

---

## 1. Authentication & Headers

All requests to protected endpoints require an OpenID Connect (OIDC) JWT token issued by Keycloak:
```http
GET /api/v1/... HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json
X-Tenant-ID: tenant_default
X-Session-ID: sess_94ba4983
```

---

## 2. Layer 2: Memory API (`/api/v1/memory`)

### 2.1 Remember Interaction
Records a user or agent interaction, extracts atomic facts, resolves conflicting claims, and indexes dense vectors into Qdrant/Chroma.

- **Endpoint:** `POST /api/v1/remember`
- **Auth:** Required (`Bearer`)
- **Request Body:**
  ```json
  {
    "user_id": "usr_dev_42",
    "text": "User prefers dark mode and uses Python 3.12 for microservices.",
    "session_id": "sess_94ba4983",
    "role": "user",
    "metadata": {
      "source": "librechat",
      "tenant_id": "default"
    }
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "event_id": "c1f729e8-4660-449e-b2d9-3ec8ec49f390",
    "working_turns_count": 1,
    "facts_extracted": 2,
    "archival_id": "c1f729e8-4660-449e-b2d9-3ec8ec49f390",
    "conflicts_resolved": 0
  }
  ```

### 2.2 Recall Context
Recalls consolidated context across Tier 1 (Working), Tier 2 (Facts), and Tier 3 (Archival Vector Embeddings).

- **Endpoint:** `POST /api/v1/recall`
- **Auth:** Required (`Bearer`)
- **Request Body:**
  ```json
  {
    "user_id": "usr_dev_42",
    "query": "What are the user's interface and language preferences?",
    "session_id": "sess_94ba4983",
    "top_k": 5
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "active_window": [
      {
        "role": "user",
        "content": "User prefers dark mode and uses Python 3.12 for microservices."
      }
    ],
    "facts": [
      {
        "key": "interface_mode",
        "value": "dark mode",
        "confidence": 1.0
      },
      {
        "key": "preferred_language",
        "value": "Python 3.12",
        "confidence": 1.0
      }
    ],
    "semantic_records": [
      {
        "id": "c1f729e8-4660-449e-b2d9-3ec8ec49f390",
        "score": 0.892,
        "payload": "User prefers dark mode and uses Python 3.12 for microservices."
      }
    ]
  }
  ```

---

## 3. Layer 9: Context Engineering API (`/v1/context`)

### 3.1 Assemble Token-Bounded Context
Assembles prompt context respecting token budgets with Dual Boundary prompt injection defense wrapping.

- **Endpoint:** `POST /v1/context/assemble`
- **Auth:** Required
- **Request Body:**
  ```json
  {
    "system_instructions": "You are Central Intelligence assistant.",
    "user_id": "usr_dev_42",
    "session_id": "sess_94ba4983",
    "memory_records": ["User preference: dark mode"],
    "retrieved_knowledge": ["Documentation: REST endpoints specification"],
    "budget_config": {
      "total_budget": 4096,
      "system_budget": 600,
      "memory_budget": 800,
      "knowledge_budget": 1200,
      "tools_budget": 500
    }
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "system_prompt": "You are Central Intelligence assistant.",
    "memory_context": "User preference: dark mode",
    "knowledge_context": "Documentation: REST endpoints specification",
    "tools_context": "",
    "conversation_context": "",
    "full_prompt": "SYSTEM: You are Central Intelligence assistant.\n...",
    "token_counts": {
      "system": 12,
      "memory": 8,
      "knowledge": 15
    },
    "total_tokens": 35,
    "sources_included": ["system", "memory", "knowledge"],
    "pruned": false,
    "compacted": false,
    "strategy_used": "priority_budget",
    "metadata": {}
  }
  ```

---

## 4. Layer 7 & 8: Agent Execution API (`/agents`)

### 4.1 List Pre-Packaged Templates
Returns available blueprints (Coder, Researcher, Customer Support).

- **Endpoint:** `GET /agents/templates`
- **Response (`200 OK`):**
  ```json
  [
    {
      "id": "coder",
      "name": "Security & Code Auditor",
      "manifest": { ... }
    },
    {
      "id": "researcher",
      "name": "Deep Research Specialist",
      "manifest": { ... }
    }
  ]
  ```

### 4.2 Execute Agent Task
Executes a multi-step cognitive agent workflow with optional sandbox execution.

- **Endpoint:** `POST /agents/{agent_id}/execute`
- **Request Body:**
  ```json
  {
    "prompt": "Analyze the codebase for OWASP vulnerabilities and write report.",
    "session_id": "sess_94ba4983",
    "max_steps": 10
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "execution_id": "exec_84091a0",
    "agent_id": "coder",
    "status": "completed",
    "steps_executed": 3,
    "output": "Vulnerability review complete. Zero high-severity findings.",
    "tokens_consumed": 1420
  }
  ```

---

## 5. Layer 10 & 14: Safety & Audit Ledger API

### 5.1 Check Guardrails & PII Scrubbing
Submits untrusted input to NeMo Guardrails and the 4-tier PII scrubber.

- **Endpoint:** `POST /api/v1/safety/check`
- **Request Body:**
  ```json
  {
    "prompt": "Here is my private token sk-abcdef1234567890abcdef1234567890 for API calls.",
    "user_id": "usr_dev_42"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "allowed": true,
    "action": "redact",
    "sanitized_prompt": "Here is my private token [REDACTED_API_KEY] for API calls.",
    "pii_detected": ["API_KEY"],
    "threat_category": null,
    "audit_event_id": "aud_0182ab9"
  }
  ```

### 5.2 Merkle Ledger Audit Root
Retrieves the latest cryptographic SHA-256 Merkle root hash of the audit log.

- **Endpoint:** `GET /api/v1/audit/merkle-root`
- **Response (`200 OK`):**
  ```json
  {
    "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "entry_count": 1428,
    "timestamp": "2026-11-13T13:30:00Z"
  }
  ```

---

## 6. Health & Status Endpoints

All core subsystems provide `/health` endpoints:
- `GET /health` on Port 8000 (Central Gateway)
- `GET /health` on Port 8001 (Memory Engine)
- `GET /health` on Port 8002 (Context Assembler)
- `GET /health` on Port 8003 (Agent Runtime)
