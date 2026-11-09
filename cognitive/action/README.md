# Layer 5: Action & Tools Hub

Layer 5 manages agent execution, sandboxing, remote device access, code interpretation, and federated tool/connector integrations across external services.

---

## 1. Connectors Hub

The connector subsystem provides pre-built, typed connectors following the ActivePieces piece contract pattern.

Registered Connectors:
- **Slack** (`pieces/slack.ts`): Post messages and interact with Slack workspaces.
- **HTTP** (`pieces/http.ts`): Generic REST/HTTP request dispatcher.
- **OpenAI Chat** (`pieces/openaiChat.ts`): External model inference proxy.
- **Email** (`pieces/email.ts`): Send and inspect emails via SMTP/IMAP.
- **Calendar** (`pieces/calendar.ts`): Read and schedule calendar events.
- **Search** (`pieces/search.ts`): Web and document retrieval connector.
- **Browser** (`pieces/browser.ts`): Playwright/browser automation actions.
- **OpenClaw** (`pieces/openclaw.ts`): OS-level file operations and multi-platform chat messaging.
- **Nango** (`nango_adapter.ts`): Meta-connector providing 500+ pre-built OAuth integrations (GitHub, Slack, Google Workspace, Salesforce, HubSpot).

---

## 2. OpenClaw Adapter (OS Actions & Multi-Channel Messaging)

- **Repo:** [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)
- **License:** MIT
- **Why Chosen:** Provides unified host OS action execution (opening files, launching applications, querying system status) and cross-channel chat messaging to Discord, Telegram, WhatsApp, Slack, Teams, Twitch, and Google Chat.

### Usage Example

```

---

## 3. Nango Adapter (500+ Federated OAuth APIs)

- **Repo:** [https://github.com/NangoHQ/nango](https://github.com/NangoHQ/nango)
- **License:** Elastic-2.0
- **Why Chosen:** Replaces fragile manual OAuth token refresh cycles with a federated layer managing credentials and proxies across 500+ SaaS APIs (GitHub, Slack, Google Workspace, Jira, Salesforce, HubSpot).
- **Configuration:**
  - `NANGO_SECRET_KEY`: Nango server secret key.
  - `NANGO_HOST`: Nango server host URL (default: `http://localhost:3003`).
  - Docker Compose: service `nango` using `nangohq/nango:latest` exposing ports `3003` and `8080`.

### Usage Example

```typescript
import { nangoAdapter } from './connectors/nango_adapter.js';

// Authenticate to GitHub via Nango and list repositories
const repos = await nangoAdapter.listGithubRepos('user-connection-id');
console.log(repos);
```

---

## 4. ACI.dev Adapter (Unified Tool Federation)

- **Repo:** [https://github.com/aipotheosis-labs/aci](https://github.com/aipotheosis-labs/aci)
- **License:** Apache-2.0
- **Why Chosen:** Enables unified tool federation so agents can dynamically discover and execute tools across MCP servers, Nango OAuth integrations, and native connectors through a single consistent contract (`federated:{provider}:{tool}`).

### Usage Example

```typescript
import { aciFederation } from './connectors/aci_adapter.js';

// 1. Discover all federated tools
const tools = await aciFederation.listFederatedTools();

// 2. Execute any federated tool seamlessly
const repos = await aciFederation.executeTool('federated:nango:github_list_repos');
const file = await aciFederation.executeTool('federated:mcp:filesystem:read_file', { path: 'README.md' });
```

---

## 5. Concurrency & Lock Manager, Shared Scratchpad (Features 5.44, 5.45, 8.49)

Located in `cognitive/action/shared_state/`:
- **DistributedLockManager (`lock_manager.py`):** Mutual exclusion (mutex) and shared reader-writer locks with auto-expiring TTL leases, reentrancy support, and renewal heartbeats.
- **SharedScratchpad (`scratchpad.py`):** Thread-safe collaborative blackboard supporting atomic Compare-and-Set (CAS), atomic increments, append operations, and complete audit logging across concurrent agents.

---

## 6. Action Preview Renderer (Feature 5.27)

Located in `cognitive/action/safety/action_preview.py`:
- **Shell Previews:** Detects dangerous invocations (`rm -rf`, raw disk access, `chmod 777`, elevated `sudo`) with danger scoring and confirmation requirements.
- **SQL Previews:** Differentiates safe read-only queries from schema teardowns (`DROP`, `TRUNCATE`) and unconstrained bulk mutations missing `WHERE` clauses.
- **File Write Previews:** Computes unified line diffs (`+` / `-`), identifies potential data wipeouts, and guards sensitive credentials (`.env`, private keys).
- **API Call Previews:** Masks sensitive authorization headers, bearer tokens, passwords, and private secrets prior to operator display.

---

## 7. Curated Tool Registry (Feature 5.08)

Located in `cognitive/action/registry/curated_registry.py`:
- **Admin Curation & Whitelisting:** Explicit administrative verification and approval required before tools are active for agent reasoning loops.
- **Role-Based Access Control (RBAC):** Strict role prerequisites per tool (`required_roles`) with administrative bypass.
- **Sliding-Window Rate Limiting:** Enforces per-agent, per-tool requests-per-minute (RPM) ceilings over moving 60-second windows.
- **Input Schema Validation:** Validates arguments against defined property types and required fields prior to dispatch.

---

## 8. Review-Before-Wider-Sharing Pipeline (Features 5.47, 19.35)

Located in `cognitive/action/safety/sharing_pipeline.py`:
- **Scoping Governance:** Governs promotion of agent discoveries and assets across scopes: `agent_private` -> `team_internal` -> `cross_team` -> `public`.
- **Automated Redaction Scanning:** Discovers and redacts API keys, passwords, bearer tokens, emails, phone numbers, and payment cards.
- **Supervisor Approval Gate:** Requires explicit reviewer confirmation before assets containing sensitive findings or targeting external scopes can be distributed.





typescript
import { getConnectorAction } from './connectors/connectorRegistry.js';

// 1. Send Discord message
const sendMessage = getConnectorAction('openclaw', 'send_channel_message');
await sendMessage?.run({
  auth: { api_token: process.env.DISCORD_BOT_TOKEN },
  propsValue: {
    channel: 'discord',
    target_id: 'discord-channel-id',
    message: 'Task execution completed successfully.',
  },
});

// 2. Open file on host
const openFile = getConnectorAction('openclaw', 'open_file');
const fileStats = await openFile?.run({
  propsValue: { file_path: './reports/summary.pdf' },
});
```

---

## 3. Nango Adapter (500+ Federated OAuth APIs)

- **Repo:** [https://github.com/NangoHQ/nango](https://github.com/NangoHQ/nango)
- **License:** Elastic-2.0
- **Why Chosen:** Replaces fragile manual OAuth token refresh cycles with a federated layer managing credentials and proxies across 500+ SaaS APIs (GitHub, Slack, Google Workspace, Jira, Salesforce, HubSpot).
- **Configuration:**
  - `NANGO_SECRET_KEY`: Nango server secret key.
  - `NANGO_HOST`: Nango server host URL (default: `http://localhost:3003`).
  - Docker Compose: service `nango` using `nangohq/nango:latest` exposing ports `3003` and `8080`.

### Usage Example

```typescript
import { nangoAdapter } from './connectors/nango_adapter.js';

// Authenticate to GitHub via Nango and list repositories
const repos = await nangoAdapter.listGithubRepos('user-connection-id');
console.log(repos);
```

---

## 4. ACI.dev Adapter (Unified Tool Federation)

- **Repo:** [https://github.com/aipotheosis-labs/aci](https://github.com/aipotheosis-labs/aci)
- **License:** Apache-2.0
- **Why Chosen:** Enables unified tool federation so agents can dynamically discover and execute tools across MCP servers, Nango OAuth integrations, and native connectors through a single consistent contract (`federated:{provider}:{tool}`).

### Usage Example

```typescript
import { aciFederation } from './connectors/aci_adapter.js';

// 1. Discover all federated tools
const tools = await aciFederation.listFederatedTools();

// 2. Execute any federated tool seamlessly
const repos = await aciFederation.executeTool('federated:nango:github_list_repos');
const file = await aciFederation.executeTool('federated:mcp:filesystem:read_file', { path: 'README.md' });
```

---

## 5. Concurrency & Lock Manager, Shared Scratchpad (Features 5.44, 5.45, 8.49)

Located in `cognitive/action/shared_state/`:
- **DistributedLockManager (`lock_manager.py`):** Mutual exclusion (mutex) and shared reader-writer locks with auto-expiring TTL leases, reentrancy support, and renewal heartbeats.
- **SharedScratchpad (`scratchpad.py`):** Thread-safe collaborative blackboard supporting atomic Compare-and-Set (CAS), atomic increments, append operations, and complete audit logging across concurrent agents.

---

## 6. Action Preview Renderer (Feature 5.27)

Located in `cognitive/action/safety/action_preview.py`:
- **Shell Previews:** Detects dangerous invocations (`rm -rf`, raw disk access, `chmod 777`, elevated `sudo`) with danger scoring and confirmation requirements.
- **SQL Previews:** Differentiates safe read-only queries from schema teardowns (`DROP`, `TRUNCATE`) and unconstrained bulk mutations missing `WHERE` clauses.
- **File Write Previews:** Computes unified line diffs (`+` / `-`), identifies potential data wipeouts, and guards sensitive credentials (`.env`, private keys).
- **API Call Previews:** Masks sensitive authorization headers, bearer tokens, passwords, and private secrets prior to operator display.

---

## 7. Curated Tool Registry (Feature 5.08)

Located in `cognitive/action/registry/curated_registry.py`:
- **Admin Curation & Whitelisting:** Explicit administrative verification and approval required before tools are active for agent reasoning loops.
- **Role-Based Access Control (RBAC):** Strict role prerequisites per tool (`required_roles`) with administrative bypass.
- **Sliding-Window Rate Limiting:** Enforces per-agent, per-tool requests-per-minute (RPM) ceilings over moving 60-second windows.
- **Input Schema Validation:** Validates arguments against defined property types and required fields prior to dispatch.

---

## 8. Review-Before-Wider-Sharing Pipeline (Features 5.47, 19.35)

Located in `cognitive/action/safety/sharing_pipeline.py`:
- **Scoping Governance:** Governs promotion of agent discoveries and assets across scopes: `agent_private` -> `team_internal` -> `cross_team` -> `public`.
- **Automated Redaction Scanning:** Discovers and redacts API keys, passwords, bearer tokens, emails, phone numbers, and payment cards.
- **Supervisor Approval Gate:** Requires explicit reviewer confirmation before assets containing sensitive findings or targeting external scopes can be distributed.






