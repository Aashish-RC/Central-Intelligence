"""Tests for Part E L1/L3/L6 partial-to-full upgrades."""

import struct

import pytest
from PIL import Image, ImageDraw

from cognitive.knowledge.quality.scorer import FreshnessTracker
from cognitive.knowledge.search.indexer.deduplicator import SimHashDeduplicator
from cognitive.knowledge.web_search.scraper.sitemap import SitemapParser
from cognitive.output.structured import SchemaEnforcer, SchemaValidationError, StructuredFormFiller
from cognitive.output.voice_speech.core.models import VoiceStyleConfig
from cognitive.output.voice_speech.tts.synthesis_engine import SpeechSynthesizer
from cognitive.perception.audio.vad import VoiceActivityDetector
from cognitive.perception.code.syntax_parser import SyntaxAwareCodeParser
from cognitive.perception.normalize.modality_fallback import (
    ModalityFallbackRouter,
    ModelCapabilityProfile,
)
from cognitive.perception.vision.quality_and_safety import (
    BarcodeReader,
    FaceRedactor,
    ImageQualityAssessor,
)
from cognitive.perception.voice_speech.stt.dictation_engine import (
    format_reader_ready,
    remove_disfluencies,
)


def test_part_e1_l1_perception_upgrades():
    # 1.07 Syntax-aware code parsing
    parser = SyntaxAwareCodeParser()
    parsed = parser.parse("import os\ndef greet(name):\n    return name\n", language="python")
    assert "os" in parsed.imports
    assert [s.name for s in parsed.symbols] == ["greet"]

    # 1.27 & 1.28 Disfluencies & reader-ready
    assert remove_disfluencies("um so the the system is uh ready") == "so the system is ready"
    assert format_reader_ready("um how are you", speaker="Alice") == "Alice: How are you?"

    # 1.30 VAD
    vad = VoiceActivityDetector(sample_rate=16000, frame_ms=20, energy_threshold=0.05)
    silence = b"\x00\x00" * 1600  # 0.1s silence
    loud = struct.pack("<h", 12000) * 1600  # 0.1s loud tone
    segs = vad.detect_speech_segments(silence + loud)
    assert len(segs) == 1
    assert segs[0].start_seconds >= 0.09

    # 1.34, 1.37, 1.38 Quality, Face redaction, Barcode
    img = Image.new("RGB", (256, 256), (120, 140, 160))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 120, 120], fill=(20, 220, 40))
    q = ImageQualityAssessor().assess(img)
    assert q.width == 256 and q.quality_tier in ("good", "blurry")

    red = FaceRedactor().redact(img, explicit_regions=[(40, 40, 100, 100)], method="solid")
    assert len(red.redacted_regions) == 1
    assert red.redacted_image.getpixel((60, 60)) == (0, 0, 0)

    img.info["qr_payload"] = "https://verify.local/123"
    assert BarcodeReader().decode(img)[0].payload == "https://verify.local/123"

    # 1.45 Modality fallback router
    router = ModalityFallbackRouter()
    text_only_model = ModelCapabilityProfile(model_id="qwen-text", supported_modalities={"text"})
    fb = router.route("image", b"pngbytes", text_only_model)
    assert fb.fallback_applied is True and fb.target_modality == "text"


def test_part_e2_l3_knowledge_upgrades():
    # 3.02 Sitemap XML parsing
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs.local/a</loc><priority>0.9</priority></url>
      <url><loc>https://docs.local/b</loc><priority>0.2</priority></url>
    </urlset>"""
    urls, _ = SitemapParser.parse_xml(xml, min_priority=0.5)
    assert [u.loc for u in urls] == ["https://docs.local/a"]

    # 3.16 SimHash near-duplicate detection
    dedup = SimHashDeduplicator(max_hamming_distance=6)
    base = (
        "Distributed consensus protocols such as Raft and Paxos ensure fault tolerant state "
        "machine replication across clustered database nodes even during network partitions "
        "and leader failover events in production infrastructure."
    )
    text_a = base + " Operators monitor quorum health continuously."
    text_b = base + " Teams monitor quorum health continuously."
    is_dup1, _ = dedup.register_or_check("d1", text_a)
    is_dup2, matched = dedup.register_or_check("d2", text_b)
    assert is_dup1 is False
    assert is_dup2 is True and matched == "d1"

    # 3.40 Persistent FreshnessTracker
    ft = FreshnessTracker(default_ttl_seconds=60.0)
    ft.record_ingested("src-1", timestamp=1000.0)
    assert ft.sweep_stale_sources(now=1030.0) == []
    assert ft.sweep_stale_sources(now=1100.0) == ["src-1"]
    assert ft.get_record("src-1").is_stale is True


def test_part_e3_l6_output_upgrades():
    # 6.20 Voice SSML rendering
    ssml = SpeechSynthesizer.render_ssml(
        "Important alert",
        VoiceStyleConfig(emotion="serious", pace="slow", emphasis="strong", accent="en-GB"),
    )
    assert '<speak xml:lang="en-GB"' in ssml
    assert 'data-emotion="serious"' in ssml
    assert '<emphasis level="strong">Important alert</emphasis>' in ssml

    # 6.21, 6.23, 6.24 Schema enforcement & form filling
    schema = {
        "type": "object",
        "required": ["name", "count"],
        "properties": {"name": {"type": "string"}, "count": {"type": "integer"}, "mode": {"type": "string", "default": "auto"}},
    }
    enforcer = SchemaEnforcer()
    validated = enforcer.validate('```json\n{"name": "job1", "count": 3}\n```', schema)
    assert validated["mode"] == "auto"

    with pytest.raises(SchemaValidationError):
        enforcer.validate({"name": "job1", "count": "bad"}, schema)

    filler = StructuredFormFiller()
    form_res = filler.fill_form(
        [{"name": "full_name", "required": True, "aliases": ["applicant"]}, {"name": "role", "default": "engineer"}],
        {"Applicant": "Ada Lovelace"},
    )
    assert form_res.complete is True
    assert form_res.filled_fields == {"full_name": "Ada Lovelace", "role": "engineer"}
