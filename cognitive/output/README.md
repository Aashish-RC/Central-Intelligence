# Layer 6: Output Generation & Multimodal Surfaces

Layer 6 provides multi-surface generation, generative UI, interactive canvases, document synthesis, and output integrity enforcement across the Central Intelligence platform.

## Architecture & Subsystems

### 1. Generative UI & AG-UI Protocol
- **CopilotKit Adapter (`generative_ui/copilotkit_adapter.ts`)**: Implements the AG-UI protocol for rendering interactive form widgets, progress indicators, streaming tables, and client-callable action registries directly inside conversational chat streams.
- **TipTap Adapter (`editor/tiptap_adapter.ts`)**: Headless ProseMirror rich-text editor supporting markdown parsing, syntax-highlighted code blocks, and bidirectional serialization.
- **Mermaid Adapter (`diagrams/mermaid_adapter.ts`)**: Text-to-diagram rendering engine for flowcharts, sequence diagrams, and ERDs with accessible vector SVG outputs.
- **Tldraw Adapter (`canvas/tldraw_adapter.ts`)**: Infinite whiteboard canvas supporting geometric shapes, connectors, freehand drawings, and real-time bounding box calculation.
- **AG-UI Glue Adapters (`generative_ui/ag_ui_adapters/`)**: Wraps TipTap editor documents and Tldraw whiteboards as first-class generative UI widgets embeddable within CopilotKit chat surfaces.

### 2. Output Integrity & Verification
- **Surgical Claim Diff Patcher (`integrity/claim_diff_patcher.py`, Feature 6.37)**: When Layer 11 verification refutes a factual claim, patches *only* the refuted sentences in-place without re-streaming or invalidating the remaining document.
- **Cryptographic Watermarker (`integrity/watermarker.py`, Features 6.31, 6.32)**: Embeds invisible HMAC-SHA256 signatures and standardized "AI-generated" provenance metadata into generated images and audio artifacts with tamper detection.

### 3. Multi-Surface Presentation
- **Output Format Negotiator (`format_negotiator.py`, Feature 6.35)**: Dynamically selects and tailors presentation formatting based on target surfaces: ANSI terminal text for CLI, responsive compact cards for Mobile, rich Markdown/HTML for Web, inline-styled MIME for Email, and SSML for Voice.
- **Citation Formatter (`citations/formatter.py`, Feature 6.33)**: Formats academic and professional citations in APA, MLA, Chicago, inline, and footnote styles, wired with Layer 3 Knowledge license and copyright provenance.
- **Accessible Output Renderer (`accessibility/renderer.py`, Feature 6.34)**: Generates WCAG 2.2 AA compliant alt text, ARIA landmarks, and WebVTT/SRT subtitles for images, video, and audio.

### 4. Real-Time Collaboration & Document Synthesis
- **Co-Editing Conflict Resolver (`collaboration/conflict_resolver.py`, Feature 6.38)**: Operational Transformation (OT) engine ensuring concurrent multi-user edits merge deterministically without overwriting each other.
- **Document Assembly Template Engine (`documents/template_engine.py`, Features 6.25–6.28)**: Assembles multi-section reports, slide presentations, and technical specifications complete with automatic Table of Contents (TOC) and bibliographic citations.

## Test Verification

```bash
# TypeScript tests (Generative UI, TipTap, Mermaid, Tldraw, AG-UI)
node control/orchestration/node_modules/tsx/dist/cli.mjs --test cognitive/output/**/tests/*.test.ts

# Python tests (Integrity, Negotiator, Citations, Accessibility, Collaboration, Templates)
python -m pytest cognitive/output/ -q -m 'not live'
```
