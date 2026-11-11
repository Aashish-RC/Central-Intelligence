"""Tests for L16 model quantization pipeline."""

from pathlib import Path

import pytest

from platform_infra.compute.quantization.quantizer import (
    ModelQuantizer,
    QuantizationConfig,
    QuantizationFormat,
)


def test_quantize_7b_to_4bit_gguf(tmp_path: Path):
    quantizer = ModelQuantizer(output_dir=tmp_path)
    cfg = QuantizationConfig(
        model_id="meta-llama/Llama-3.1-7B",
        params_billions=7.0,
        target_format=QuantizationFormat.GGUF,
        bits=4,
        preset="Q4_K_M",
    )
    res = quantizer.quantize(cfg)

    assert res.bits == 4
    assert res.target_format == QuantizationFormat.GGUF
    assert res.original_size_gb > 12.0
    assert res.quantized_size_gb < 4.5
    assert res.compression_ratio >= 3.0
    assert quantizer.fits_edge_budget(res, available_vram_gb=6.0)
    assert not quantizer.fits_edge_budget(res, available_vram_gb=3.0)
    assert res.artifact_path and Path(res.artifact_path).exists()


def test_quantize_awq_and_gptq_and_validation():
    quantizer = ModelQuantizer()
    for fmt in (QuantizationFormat.AWQ, QuantizationFormat.GPTQ):
        res = quantizer.quantize(
            QuantizationConfig(model_id="qwen-7b", params_billions=7.0, target_format=fmt, bits=4)
        )
        assert res.quantized_size_gb < res.original_size_gb

    with pytest.raises(ValueError):
        QuantizationConfig(model_id="bad", params_billions=7.0, bits=7)

