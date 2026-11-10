# Layer 1: Perception (Cognitive Architecture)

The Perception Layer serves as the sensory front-end for Central-Intelligence, ingesting and normalizing real-time multi-modal data streams across voice, speech, documents, vision, screen context, and physical accessibility hardware before feeding into downstream reasoning and context layers.

## Subsystems & Modality Adapters

1. **Real-Time Audio & WebRTC (`cognitive/perception/audio/livekit_adapter.py`)**
   - LiveKit WebRTC adapter for sub-100ms bidirectional voice communication.
   - Generates room join JWTs, establishes audio sessions, and streams/receives PCM/Opus chunks.
   - Docker service: `livekit` (`livekit/livekit-server:latest`, port 7880).

2. **Offline Speech-to-Text (`cognitive/perception/audio/handy_adapter.py`)**
   - Handy offline STT adapter backed by local Whisper.
   - 100% air-gapped transcription of `.wav`, `.mp3`, `.ogg`, and `.flac` files with zero network egress.

3. **Web & Dynamic Document Scraping (`cognitive/perception/document/crawl4ai_adapter.py`)**
   - Crawl4AI dynamic page crawler transforming web pages and HTML into clean, LLM-ready Markdown.
   - Automatic table conversion to GFM markdown tables, link extraction, and boilerplate stripping.

4. **Desktop Screen Awareness (`cognitive/perception/screen/screenpipe_adapter.py`)**
   - Screenpipe continuous 24/7 desktop visual capture with local OCR chronological indexing.
   - Supports historical queries (e.g. "what was on screen 5 minutes ago").

5. **Layout-Aware Document Parsing (`cognitive/perception/document/unstructured_adapter.py`)**
   - Unstructured.io adapter extracting structured JSON from PDF, DOCX, PPTX, and XLSX documents.
   - Extracts bounding boxes, tables, titles, form fields, and narrative text.

6. **Vision OCR Extraction (`cognitive/perception/vision/paddleocr_adapter.py`)**
   - PaddleOCR adapter for extracting printed text, handwritten notes, and multi-language characters from images.

7. **Vision-Language Model Pipeline (`cognitive/perception/vision/vlm_client.py`)**
   - Multimodal client bridging image queries to Layer 4 Model Gateway (`gpt-4o`, `claude-3-5-sonnet`).
   - Image description, object detection, and scene classification.

8. **Unified Input Normalizer (`cognitive/perception/normalize/`)**
   - Temporally synchronized event queue aggregating all perception streams (WebRTC audio, user prompts, screen OCR frames, scraped documents).
   - Cryptographic provenance tagging (`source`, `trust`, `modality`, `timestamp`).

9. **Situational Context Probe (`cognitive/perception/situational/context_probe.py`)**
   - Discovers ambient runtime context: `{date, time, tz, locale, device, activity}`.
   - Supplies grounded environmental context directly to Layer 9 `SituationalInjector`.

10. **Physical Accessibility Drivers (`cognitive/perception/accessibility/`)**
    - Standard interfaces for switch access (`SwitchAccessDriver`), infrared eye tracking (`EyeTrackingDriver`), and sign language recognition (`SignLanguageRecognizer`).

## Verification Suite

```bash
python -m pytest cognitive/perception/ -q -m 'not live'
```

