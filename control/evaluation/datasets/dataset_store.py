"""Evaluation Datasets Store (Layer 11: Evaluation & Quality, Feature 11.01).

Provides:
- Domain-isolated evaluation datasets
- Versioning and metadata tracking
- JSON / Dict import and export
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DatasetSample:
    """Individual test sample in an evaluation dataset."""
    sample_id: str
    input_prompt: str
    expected_output: Optional[str] = None
    domain: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class EvaluationDataset:
    """Domain-specific evaluation dataset with versioning."""
    dataset_id: str
    name: str
    domain: str
    version: str = "1.0.0"
    description: str = ""
    samples: List[DatasetSample] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_sample(self, sample: DatasetSample) -> None:
        self.samples.append(sample)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvaluationDataset:
        samples_data = data.pop("samples", [])
        samples = [DatasetSample(**s) for s in samples_data]
        return cls(samples=samples, **data)


class DatasetStore:
    """CRUD repository for evaluation datasets."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir
        self._datasets: Dict[str, EvaluationDataset] = {}
        if storage_dir:
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self.storage_dir:
            return
        for file in self.storage_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ds = EvaluationDataset.from_dict(data)
                    self._datasets[ds.dataset_id] = ds
            except Exception:
                pass

    def create_dataset(
        self,
        dataset_id: str,
        name: str,
        domain: str,
        version: str = "1.0.0",
        description: str = "",
        samples: Optional[List[DatasetSample]] = None,
    ) -> EvaluationDataset:
        ds = EvaluationDataset(
            dataset_id=dataset_id,
            name=name,
            domain=domain,
            version=version,
            description=description,
            samples=samples or [],
        )
        self._datasets[dataset_id] = ds
        self.save(ds)
        return ds

    def get_dataset(self, dataset_id: str) -> Optional[EvaluationDataset]:
        return self._datasets.get(dataset_id)

    def list_datasets(self, domain: Optional[str] = None) -> List[EvaluationDataset]:
        if domain:
            return [ds for ds in self._datasets.values() if ds.domain == domain]
        return list(self._datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            if self.storage_dir:
                file_path = self.storage_dir / f"{dataset_id}.json"
                if file_path.exists():
                    file_path.unlink()
            return True
        return False

    def save(self, dataset: EvaluationDataset) -> None:
        self._datasets[dataset.dataset_id] = dataset
        if self.storage_dir:
            file_path = self.storage_dir / f"{dataset.dataset_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(dataset.to_dict(), f, indent=2)
