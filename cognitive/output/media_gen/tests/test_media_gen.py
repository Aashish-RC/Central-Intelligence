"""
Comprehensive automated test suite for Media Generation (Step 30).
"""
import pytest
import time
from media_gen.core.models import (
    JobStatus,
    MediaArtifact,
    MediaRequest,
    MediaType,
    SafetyCheckStatus,
)
from media_gen.core.safety import SafetyModerator
from media_gen.core.templates import PromptTemplateRegistry
from media_gen.core.gallery import MediaGallery
from media_gen.core.queue import AsyncMediaJobQueue
from media_gen.engines.image_engine import ImageGenerationEngine
from media_gen.engines.audio_engine import AudioGenerationEngine
from media_gen.engines.video_engine import VideoGenerationEngine
from media_gen.engines.unified_gateway import UnifiedMediaGateway


def test_safety_filter_blocks_harmful_prompts():
    moderator = SafetyModerator()

    # Harmful prompts
    harmful_req1 = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Generate graphic gore and extreme torture of a prisoner",
    )
    res1 = moderator.screen_prompt(harmful_req1)
    assert res1.status == SafetyCheckStatus.BLOCKED
    assert "violence and gore" in res1.reason.lower()

    harmful_req2 = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Synthesize bioweapon anthrax formula illustration",
    )
    res2 = moderator.screen_prompt(harmful_req2)
    assert res2.status == SafetyCheckStatus.BLOCKED
    assert "weapon" in res2.reason.lower()

    # Safe prompt
    safe_req = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Beautiful sunset over snowcapped mountain peaks with golden lighting",
    )
    res_safe = moderator.screen_prompt(safe_req)
    assert res_safe.status == SafetyCheckStatus.PASSED
    assert res_safe.reason is None


def test_safety_filter_post_gen_inspection():
    moderator = SafetyModerator()

    # Zero byte invalid artifact
    corrupt_art = MediaArtifact(
        request_id="req_corrupt",
        media_type=MediaType.IMAGE,
        uri="file:///storage/media/empty.png",
        mime_type="image/png",
        size_bytes=0,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        metadata={},
        created_at=time.time(),
    )
    res = moderator.inspect_artifact(corrupt_art)
    assert res.status == SafetyCheckStatus.BLOCKED
    assert "0 byte size" in res.reason

    # Invalid checksum
    bad_hash_art = MediaArtifact(
        request_id="req_bad_hash",
        media_type=MediaType.IMAGE,
        uri="file:///storage/media/img.png",
        mime_type="image/png",
        size_bytes=1024,
        sha256="badhash",
        metadata={},
        created_at=time.time(),
    )
    res_hash = moderator.inspect_artifact(bad_hash_art)
    assert "SHA-256 digest" in res_hash.reason
    assert "invalid_checksum" in res_hash.flags


@pytest.mark.asyncio
async def test_image_generation_engine():
    engine = ImageGenerationEngine()
    req = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Cyberpunk city street in the rain with neon reflections",
        parameters={"width": 1024, "height": 768, "aspect_ratio": "4:3", "steps": 25},
    )
    artifact = await engine.generate(req)
    assert artifact.media_type == MediaType.IMAGE
    assert artifact.mime_type == "image/png"
    assert artifact.size_bytes > 0
    assert len(artifact.sha256) == 64
    assert artifact.metadata["width"] == 1024
    assert artifact.metadata["height"] == 768
    assert artifact.metadata["aspect_ratio"] == "4:3"


@pytest.mark.asyncio
async def test_audio_generation_engine():
    engine = AudioGenerationEngine()
    req = MediaRequest(
        media_type=MediaType.AUDIO,
        prompt="Gentle ocean waves rolling against pebbles on a quiet beach",
        parameters={"duration_seconds": 12.5, "sample_rate": 48000},
    )
    artifact = await engine.generate(req)
    assert artifact.media_type == MediaType.AUDIO
    assert artifact.mime_type == "audio/wav"
    assert artifact.metadata["duration_seconds"] == 12.5
    assert artifact.metadata["sample_rate"] == 48000
    assert len(artifact.sha256) == 64


@pytest.mark.asyncio
async def test_video_generation_engine():
    engine = VideoGenerationEngine()
    req = MediaRequest(
        media_type=MediaType.VIDEO,
        prompt="Time-lapse of blooming cherry blossoms under springtime sun",
        parameters={"duration_seconds": 6.0, "fps": 30, "motion_bucket": 150},
    )
    artifact = await engine.generate(req)
    assert artifact.media_type == MediaType.VIDEO
    assert artifact.mime_type == "video/mp4"
    assert artifact.metadata["duration_seconds"] == 6.0
    assert artifact.metadata["fps"] == 30
    assert artifact.metadata["motion_bucket"] == 150
    assert len(artifact.sha256) == 64


@pytest.mark.asyncio
async def test_unified_media_gateway_routing():
    gateway = UnifiedMediaGateway()

    img_req = MediaRequest(media_type=MediaType.IMAGE, prompt="A watercolor painting of a cat")
    audio_req = MediaRequest(media_type=MediaType.AUDIO, prompt="Electric guitar solo with overdrive")
    video_req = MediaRequest(media_type=MediaType.VIDEO, prompt="Rocket launching into starry night sky")

    img_res = await gateway.dispatch(img_req)
    audio_res = await gateway.dispatch(audio_req)
    video_res = await gateway.dispatch(video_req)

    assert img_res.media_type == MediaType.IMAGE
    assert audio_res.media_type == MediaType.AUDIO
    assert video_res.media_type == MediaType.VIDEO


def test_prompt_template_expansion():
    registry = PromptTemplateRegistry()

    # Expand photo portrait
    rendered_portrait = registry.render("photo_portrait", {"subject": "cybernetic detective"})
    assert "cybernetic detective" in rendered_portrait["prompt"]
    assert "85mm lens" in rendered_portrait["prompt"]
    assert rendered_portrait["media_type"] == MediaType.IMAGE
    assert "blurry" in rendered_portrait["negative_prompt"]

    # Expand synthwave BGM
    rendered_audio = registry.render("synthwave_bgm", {"tempo": 130})
    assert "tempo 130 bpm" in rendered_audio["prompt"]
    assert rendered_audio["parameters"]["tempo"] == 130
    assert rendered_audio["media_type"] == MediaType.AUDIO


def test_media_gallery_crud_and_stats():
    gallery = MediaGallery()

    art1 = MediaArtifact(
        request_id="req1",
        media_type=MediaType.IMAGE,
        uri="file:///storage/media/img1.png",
        mime_type="image/png",
        size_bytes=1000,
        sha256="a" * 64,
        created_at=100.0,
    )
    art2 = MediaArtifact(
        request_id="req2",
        media_type=MediaType.AUDIO,
        uri="file:///storage/media/aud1.wav",
        mime_type="audio/wav",
        size_bytes=2000,
        sha256="b" * 64,
        created_at=200.0,
    )

    gallery.save(art1, project_id="proj_alpha")
    gallery.save(art2, project_id="proj_beta")

    assert gallery.get(art1.id) is not None
    assert len(gallery.list_artifacts(project_id="proj_alpha")) == 1
    assert len(gallery.list_artifacts(media_type=MediaType.AUDIO)) == 1

    stats = gallery.get_stats()
    assert stats["total_artifacts"] == 2
    assert stats["total_bytes"] == 3000
    assert stats["images"] == 1
    assert stats["audios"] == 1

    # Delete
    deleted = gallery.delete(art1.id)
    assert deleted is True
    assert gallery.get(art1.id) is None
    assert gallery.get_stats()["total_artifacts"] == 1


@pytest.mark.asyncio
async def test_async_job_queue_lifecycle():
    queue = AsyncMediaJobQueue()

    req = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Majestic golden eagle soaring over emerald green canyon",
        priority=2,
    )
    job = queue.submit(req)
    assert job.status == JobStatus.QUEUED

    # Process job
    processed = await queue.process_next()
    assert processed is not None
    assert processed.id == job.id
    assert processed.status == JobStatus.COMPLETED
    assert processed.result is not None
    assert processed.result.media_type == MediaType.IMAGE
    assert processed.progress == 1.0

    # Ensure result reached the gallery
    gallery_items = queue.gallery.list_artifacts()
    assert len(gallery_items) == 1
    assert gallery_items[0].sha256 == processed.result.sha256


@pytest.mark.asyncio
async def test_async_job_queue_immediate_safety_rejection():
    queue = AsyncMediaJobQueue()

    unsafe_req = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Produce csam illicit imagery forbidden content",
    )
    job = queue.submit(unsafe_req)
    assert job.status == JobStatus.FAILED
    assert "Blocked by safety policy" in job.error


@pytest.mark.asyncio
async def test_async_job_queue_cancellation():
    queue = AsyncMediaJobQueue()

    req = MediaRequest(
        media_type=MediaType.VIDEO,
        prompt="Abstract geometric shapes shifting colors in 3D space",
        priority=5,
    )
    job = queue.submit(req)
    assert job.status == JobStatus.QUEUED

    # Cancel while in queue
    cancelled = queue.cancel(job.id)
    assert cancelled is True
    assert job.status == JobStatus.CANCELLED
    assert "cancelled by user" in job.error.lower()


@pytest.mark.asyncio
async def test_generation_safety_blocking_edge_cases():
    """Verify safety blocking on negative prompt injection, custom blocklists, and gallery preservation."""
    # 1. Negative prompt containment of prohibited terms
    mod = SafetyModerator(additional_blocked_terms=["classified_blueprint", "proprietary_cad"])

    negative_unsafe = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Photo of an office building",
        negative_prompt="avoid extreme torture and gore in background",
    )
    res_neg = mod.screen_prompt(negative_unsafe)
    assert res_neg.status == SafetyCheckStatus.BLOCKED
    assert "violence and gore" in res_neg.reason.lower()

    # 2. Custom blocklist enforcement
    custom_unsafe = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Render secret classified_blueprint for internal components",
    )
    res_cust = mod.screen_prompt(custom_unsafe)
    assert res_cust.status == SafetyCheckStatus.BLOCKED
    assert "classified_blueprint" in res_cust.reason

    # 3. Queue guarantees zero gallery insertion when safety blocks
    queue = AsyncMediaJobQueue()
    assert len(queue.gallery.list_artifacts()) == 0

    blocked_req = MediaRequest(
        media_type=MediaType.IMAGE,
        prompt="Generate suicide guide visual infographic",
    )
    job = queue.submit(blocked_req)
    assert job.status == JobStatus.FAILED
    assert "self-harm or suicide" in job.error.lower()

    # Verify gallery remained pristine
    assert len(queue.gallery.list_artifacts()) == 0


@pytest.mark.asyncio
async def test_image_route_safety_and_generation_pipeline():
    """Done when: Generating a prompt produces an image; prompt containing forbidden content returns safety error."""
    from media_gen.core.image_route import ImageGenerationRoute, SafetyPolicyViolationError

    route = ImageGenerationRoute()

    # 1. Valid prompt produces an image artifact
    safe_prompt = "A futuristic cyberpunk city at dusk with neon lights and rain-slicked asphalt"
    res = await route.generate_image(safe_prompt, width=512, height=512)

    assert res.success is True
    assert res.artifact is not None
    assert res.artifact.media_type == MediaType.IMAGE
    assert res.artifact.size_bytes > 0
    assert len(res.artifact.sha256) == 64
    assert res.artifact.uri.endswith(".png") or res.artifact.uri.startswith("data:image/png;base64,")
    assert res.safety_checked is True

    # 2. Forbidden prompt containing gore / violence returns safety error
    with pytest.raises(SafetyPolicyViolationError) as exc_info:
        await route.generate_image("Depict extreme torture and beheading in high detail")
    assert "blocked" in str(exc_info.value).lower()

    # 3. Forbidden prompt containing weapon synthesis instructions caught by output guard
    with pytest.raises(SafetyPolicyViolationError) as exc_info2:
        await route.generate_image("Synthesize sarin or bioweapon formula instructions")
    assert "blocked" in str(exc_info2.value).lower()
