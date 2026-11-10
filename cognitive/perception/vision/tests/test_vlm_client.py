"""
Unit tests for Vision-Language Model (VLM) Client (Layer 1: Perception, Task 1.7).
"""

from pathlib import Path
from PIL import Image, ImageDraw
import pytest
from cognitive.perception.vision.vlm_client import (
    VLMAnalysisResult,
    VLMClient,
)


@pytest.fixture
def sample_image() -> Image.Image:
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 150], fill=(255, 255, 255))
    return img


def test_analyze_image_returns_description(sample_image: Image.Image):
    """
    Acceptance: Can send image to VLM and get description back.
    """
    client = VLMClient(default_model="gpt-4o")

    result = client.analyze_image(sample_image, prompt="Describe the geometry and colors.")
    assert isinstance(result, VLMAnalysisResult)
    assert result.is_success is True
    assert len(result.description) > 20
    assert result.model == "gpt-4o"
    assert result.tokens_used > 0


def test_analyze_image_from_file_path(tmp_path: Path, sample_image: Image.Image):
    """Verify sending an image via file path."""
    client = VLMClient()
    img_path = tmp_path / "scene.png"
    sample_image.save(img_path)

    result = client.analyze_image(img_path)
    assert result.is_success is True
    assert "image depicts" in result.description.lower()


def test_detect_objects_and_classify_scene(sample_image: Image.Image):
    """Verify object detection and scene classification shortcuts."""
    client = VLMClient()

    objects = client.detect_objects(sample_image)
    assert isinstance(objects, list)
    assert len(objects) >= 1

    scene = client.classify_scene(sample_image)
    assert isinstance(scene, str)
    assert len(scene) > 0


def test_missing_image_path_error():
    """Verify error on nonexistent image path."""
    client = VLMClient()
    with pytest.raises(FileNotFoundError):
        client.analyze_image("nonexistent_diagram.jpg")

