"""Full-Parameter Supervised Fine-Tuning Job Orchestrator (L7 Feature 7.19)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List
from uuid import uuid4


@dataclass
class FullTuneConfig:
    """Configuration for distributed full-weight fine-tuning."""

    base_model: str
    params_billions: float
    dataset_size: int
    epochs: int = 3
    global_batch_size: int = 64
    learning_rate: float = 1e-5
    precision: str = "bf16"
    distributed_strategy: str = "fsdp"
    num_gpus: int = 8
    min_dataset_size: int = 500

    def __post_init__(self) -> None:
        if self.dataset_size < self.min_dataset_size:
            raise ValueError(
                f"Full fine-tuning requires >= {self.min_dataset_size} examples (got {self.dataset_size}); "
                "use PEFT/LoRA for smaller datasets."
            )
        if self.num_gpus <= 0 or self.global_batch_size <= 0:
            raise ValueError("num_gpus and global_batch_size must be positive")


@dataclass
class FullTuneJobSpec:
    """Scheduled/configured full fine-tuning job specification & resource plan."""

    job_id: str
    base_model: str
    distributed_strategy: str
    total_steps: int
    estimated_vram_gb_per_gpu: float
    checkpoint_interval_steps: int
    status: str = "configured"
    env_vars: Dict[str, str] = field(default_factory=dict)


class FullFineTuningOrchestrator:
    """Validates, sizes, and submits distributed full fine-tuning jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, FullTuneJobSpec] = {}

    def configure_job(self, config: FullTuneConfig) -> FullTuneJobSpec:
        """Validate dataset thresholds, size FSDP/DeepSpeed memory, and enqueue job."""
        steps_per_epoch = max(1, math.ceil(config.dataset_size / config.global_batch_size))
        total_steps = steps_per_epoch * config.epochs

        # Approximate full training memory: weights(bf16=2B) + grads(2B) + AdamW states(8B) -> ~14 bytes/param + activations
        total_cluster_mem_gb = (config.params_billions * 1e9 * 14.0) / (1024**3)
        per_gpu_gb = round((total_cluster_mem_gb / config.num_gpus) * 1.15, 2)
        ckpt_interval = max(10, total_steps // 4)

        job_id = f"ftjob_{uuid4().hex[:10]}"
        spec = FullTuneJobSpec(
            job_id=job_id,
            base_model=config.base_model,
            distributed_strategy=config.distributed_strategy,
            total_steps=total_steps,
            estimated_vram_gb_per_gpu=per_gpu_gb,
            checkpoint_interval_steps=ckpt_interval,
            status="configured",
            env_vars={
                "TRAIN_PRECISION": config.precision,
                "DIST_STRATEGY": config.distributed_strategy.upper(),
                "WORLD_SIZE": str(config.num_gpus),
            },
        )
        self._jobs[job_id] = spec
        return spec

    def list_jobs(self) -> List[FullTuneJobSpec]:
        return list(self._jobs.values())

