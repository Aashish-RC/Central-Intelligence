"""Tests for L3 Knowledge multi-modal ingestion, RSS/Atom feeds, and RRF re-ranking."""

import io
from email.message import EmailMessage

from PIL import Image

from cognitive.knowledge.ingest.audio_video import AudioVideoIngestor
from cognitive.knowledge.ingest.email import EmailIngestor
from cognitive.knowledge.ingest.image_ingest import ImageIngestor
from cognitive.knowledge.ingest.version_tracker import SourceVersionTracker
from cognitive.knowledge.ingest.video_transcript import VideoTranscriptIngestor
from cognitive.knowledge.search.core.models import CorpusType, SearchDocument
from cognitive.knowledge.search.engines.rrf import ReciprocalRankFusion
from cognitive.knowledge.web_search.feed_ingestor import FeedIngestor


def test_video_transcript_srt_and_vtt_ingest_and_search():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.500
Welcome to this tutorial on distributed vector indexes.

00:00:05.000 --> 00:00:09.000
HNSW graphs allow sub-millisecond approximate nearest neighbor lookup.
"""
    ing = VideoTranscriptIngestor()
    chunks = ing.ingest("yt-vid-1", vtt, title="Vector Indexing", window_segments=2)
    assert len(chunks) == 1
    assert chunks[0].metadata["start_time"] == "00:00:01.000"

    hits = ing.search("HNSW graphs nearest neighbor")
    assert len(hits) == 1
    assert "HNSW" in hits[0].chunk.text


def test_audio_video_ingest_podcast_and_search():
    class StubSpeech:
        def transcribe_file(self, _path):
            return type(
                "Out",
                (),
                {
                    "text": "Today on the podcast we explore federated learning in clinical hospitals. Differential privacy protects patient records.",
                    "language": "en",
                    "segments": [],
                },
            )()

    ing = AudioVideoIngestor(speech_adapter=StubSpeech())
    res = ing.ingest_audio("pod-42", "episode42.mp3", title="Clinical AI Podcast")
    assert res.chunks_indexed >= 1
    hits = ing.search("differential privacy patient records")
    assert len(hits) >= 1
    assert "privacy" in hits[0].chunk.text.lower()


def test_email_ingest_eml_headers_body_attachments_and_search():
    msg = EmailMessage()
    msg["Message-ID"] = "<abc@example.org>"
    msg["Subject"] = "Q4 Compliance Audit"
    msg["From"] = "compliance@example.org"
    msg["To"] = "team@example.org"
    msg.set_content("Please review the attached ISO 42001 checklist before Friday.")
    msg.add_attachment(b"col1,col2\n1,2\n", maintype="text", subtype="csv", filename="iso42001.csv")

    ing = EmailIngestor()
    parsed = ing.ingest("eml-1", msg.as_bytes())
    assert parsed.subject == "Q4 Compliance Audit"
    assert [a.filename for a in parsed.attachments] == ["iso42001.csv"]

    hits = ing.search("ISO 42001 checklist")
    assert len(hits) == 1


def test_rss_and_atom_feed_refresh_incremental():
    rss_v1 = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>RegUpdates</title>
      <item><guid>id-1</guid><title>AI Act Guidance</title><link>https://reg.local/1</link><description>Initial guidance</description></item>
    </channel></rss>"""
    rss_v2 = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>RegUpdates</title>
      <item><guid>id-1</guid><title>AI Act Guidance</title><link>https://reg.local/1</link><description>Initial guidance</description></item>
      <item><guid>id-2</guid><title>Audit Rule Update</title><link>https://reg.local/2</link><description>New reporting rule</description></item>
    </channel></rss>"""

    payloads = [rss_v1, rss_v2]
    feed = FeedIngestor(fetcher=lambda _u: payloads.pop(0))
    first = feed.refresh("https://reg.local/rss")
    assert len(first) == 1
    assert first[0].title == "AI Act Guidance"

    second = feed.refresh("https://reg.local/rss")
    assert len(second) == 1
    assert second[0].item_id == "id-2"


def test_image_ingest_with_vlm_description_and_search():
    img = Image.new("RGB", (64, 64), color=(10, 120, 200))

    class StubVLM:
        def analyze_image(self, _img, prompt=""):
            return type(
                "VLMRes",
                (),
                {
                    "description": "Architecture blueprint diagram showing Kafka event bus connected to Postgres.",
                    "detected_objects": ["diagram", "kafka", "postgres"],
                    "model_used": "stub-vlm",
                },
            )()

    ing = ImageIngestor(vlm_client=StubVLM())
    meta = ing.ingest("img-1", img, title="System Diagram")
    assert meta.width == 64
    hits = ing.search("Kafka event bus Postgres")
    assert len(hits) == 1


def test_rrf_post_fusion_cross_encoder_reranking():
    d_low_ce = SearchDocument(
        id="doc_generic",
        corpus_type=CorpusType.NOTE,
        title="General Notes",
        content="deployment notes for servers",
    )
    d_high_ce = SearchDocument(
        id="doc_exact",
        corpus_type=CorpusType.NOTE,
        title="Zero Downtime Canary Deployment",
        content="Step-by-step zero downtime canary deployment with automated rollback.",
    )
    # Give d_low_ce better initial rank so RRF alone would put it first
    lex = [(d_low_ce, 10.0), (d_high_ce, 8.0)]
    vec = [(d_low_ce, 0.9), (d_high_ce, 0.85)]

    rrf = ReciprocalRankFusion()
    no_rerank = rrf.fuse(lex, vec, rerank=False)
    assert no_rerank[0].document.id == "doc_generic"

    reranked = rrf.fuse(lex, vec, query="zero downtime canary deployment", rerank=True)
    assert reranked[0].document.id == "doc_exact"


def test_source_version_tracker_reingests_only_changed_diff():
    tracker = SourceVersionTracker()
    v1 = "Section A: Unchanged intro.\n\nSection B: Old metric threshold is 50ms."
    s1 = tracker.sync_source("page-1", v1)
    assert s1.added_or_updated_blocks == 2
    assert s1.unchanged_blocks == 0

    v2 = "Section A: Unchanged intro.\n\nSection B: Updated metric threshold is 25ms."
    s2 = tracker.sync_source("page-1", v2)
    assert s2.unchanged_blocks == 1
    assert s2.added_or_updated_blocks == 1
    assert s2.reingested_chunk_ids == ["page-1:blk:1"]

