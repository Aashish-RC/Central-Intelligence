# Central Intelligence — Layer 18: Interaction

Layer 18 provides cross-platform client interaction surfaces across Web, Desktop, Terminal, and IDE, unified under the **Aevum Universal Surface Adapter (Crown Jewel 18.15)**.

## Subsystems & Architecture

| Feature ID | Module | Implementation | Description |
|---|---|---|---|
| **18.1** | `surface/interaction/web` | `LibreChatAdapter` | Multi-provider web chat UI connecting OpenAI, Anthropic, Google, and Ollama in a single conversation thread. |
| **18.2** | `surface/interaction/desktop` | `JanDesktopAdapter` | Local-first privacy desktop client supporting on-device models with offline guarantees. |
| **18.3** | `surface/interaction/terminal` | `OpenCodeAdapter` (TS) | Terminal-based AI coding agent with ANSI color syntax highlighting and CLI tool execution. |
| **18.4** | `surface/interaction/ide` | `ZedIdeAdapter` (TS) | IDE integration supporting inline code transformation and assistant context panels. |
| **18.15** | `surface/interaction/universal` | `UniversalSurfaceAdapter` 🚩 **CROWN JEWEL** | Presentation normalization layer rendering rich content, generative UI, buttons, and streams consistently across Web, Desktop, Terminal, and IDE. |
| **18.07** | `surface/interaction/continuity` | `ConversationContinuityEngine` | Synchronizes conversation state across client surfaces using L15 CRDT reconciliation. |
| **18.09-18.11** | `surface/interaction/depth` | `DepthLevelSwitcher` | Guided / Standard / Pro mode switcher with transparency inspector for sources, memories, and token cost. |
| **18.18-18.24** | `surface/interaction/proactive` | `ProactiveNudgeEngine` | Immediate routing for urgent alerts and scheduled daily briefs at designated times (e.g. 9:00 AM). |
| **18.34-18.37** | `surface/interaction/ambient` | `AmbientModeManager` | Opt-in always-listening mode with on-device wake-word detection and visual presence indicators. |
| **18.38-18.42** | `surface/interaction/settings` | `SettingsCenter` | Consolidated settings control plane uniting Accessibility (WCAG AAA), Localization (auto RTL), and First-Run Wizard onboarding. |

## Testing

```bash
pytest surface/interaction/ -v
node control/orchestration/node_modules/tsx/dist/cli.mjs --test surface/interaction/terminal/tests/opencode.test.ts surface/interaction/ide/tests/zed.test.ts
```
