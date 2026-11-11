"""Tests for L6 media extensions (A6.1-A6.7) and AudioOverviewGenerator (A6.8)."""

import pytest
from PIL import Image

from cognitive.output.media_gen.core.models import MediaRequest, MediaType
from cognitive.output.media_gen.engines.image_to_image import ImageToImageEngine
from cognitive.output.media_gen.engines.inpainting import InpaintingEngine
from cognitive.output.media_gen.engines.outpainting import OutpaintingEngine
from cognitive.output.media_gen.engines.style_transfer import StyleTransferEngine
from cognitive.output.media_gen.engines.upscaling import UpscalingEngine
from cognitive.output.media_gen.engines.variations import ImageVariationsEngine
from cognitive.output.media_gen.engines.vector_gen import VectorGenerationEngine
from cognitive.output.voice_speech.audio_overview import AudioOverviewGenerator


@pytest.mark.asyncio
async def test_image_editing_engines_end_to_end():
    src = Image.new("RGB", (64, 64), color=(80, 120, 200))

    # A6.1 Image-to-image
    i2i = ImageToImageEngine()
    art1 = await i2i.generate(MediaRequest(media_type=MediaType.IMAGE, prompt="warm sunset", parameters={"source_image": src}))
    assert art1.metadata["engine"] == "image_to_image"
    assert art1.size_bytes > 0

    # A6.2 Inpainting
    inp = InpaintingEngine()
    art2 = await inp.generate(MediaRequest(media_type=MediaType.IMAGE, prompt="remove box", parameters={"source_image": src, "mask_bbox": (16, 16, 48, 48)}))
    assert art2.metadata["engine"] == "inpainting"

    # A6.3 Outpainting (512x512 -> 768x768 simulation with 64x64 test & exact params check)
    outp = OutpaintingEngine()
    art3 = await outp.generate(MediaRequest(media_type=MediaType.IMAGE, prompt="extend scene", parameters={"source_image": Image.new("RGB", (512, 512), color=(40, 60, 80)), "target_width": 768, "target_height": 768}))
    assert art3.metadata["width"] == 768 and art3.metadata["height"] == 768

    # A6.4 4 Variations
    var_eng = ImageVariationsEngine()
    variants = await var_eng.generate_variations(MediaRequest(media_type=MediaType.IMAGE, prompt="vars", parameters={"source_image": src}), count=4)
    assert len(variants) == 4
    assert len({v.sha256 for v in variants}) == 4

    # A6.5 Style Transfer (Van Gogh)
    st = StyleTransferEngine()
    art5 = await st.generate(MediaRequest(media_type=MediaType.IMAGE, prompt="style", parameters={"source_image": src, "style_name": "van_gogh"}))
    assert art5.metadata["style_name"] == "van_gogh"

    # A6.6 Upscaling (256x256 -> 1024x1024)
    up = UpscalingEngine()
    art6 = await up.generate(MediaRequest(media_type=MediaType.IMAGE, prompt="upscale", parameters={"source_image": Image.new("RGB", (256, 256), color=(90, 90, 90)), "scale_factor": 4}))
    assert art6.metadata["width"] == 1024 and art6.metadata["height"] == 1024

    # A6.7 SVG Vector generation
    vec = VectorGenerationEngine()
    art7 = await vec.generate(MediaRequest(media_type=MediaType.IMAGE, prompt="Quantum Leaf AI Logo"))
    assert art7.mime_type == "image/svg+xml"
    assert art7.uri.endswith(".svg")


def test_audio_overview_two_host_research_paper():
    gen = AudioOverviewGenerator()
    paper = [
        "Transformers scale quadratically with context length unless sparse attention is used.",
        "Ring attention distributes long sequences across multiple devices with near-linear speedup.",
        "Evaluation shows 99% recall on 1 million token needle-in-a-haystack benchmarks.",
    ]
    overview = gen.generate_overview(sources=paper, title="Ring Attention Paper", target_duration_seconds=120)
    speakers = {turn.speaker for turn in overview.script}
    assert speakers == {"Host A", "Host B"}
    assert overview.audio_bytes[:4] == b"RIFF"
    assert overview.estimated_duration_seconds > 1.0

