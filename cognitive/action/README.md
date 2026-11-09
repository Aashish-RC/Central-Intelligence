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

---

## 2. OpenClaw Adapter (OS Actions & Multi-Channel Messaging)

- **Repo:** [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)
- **License:** MIT
- **Why Chosen:** Provides unified host OS action execution (opening files, launching applications, querying system status) and cross-channel chat messaging to Discord, Telegram, WhatsApp, Slack, Teams, Twitch, and Google Chat.

### Usage Example

```typescript
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
