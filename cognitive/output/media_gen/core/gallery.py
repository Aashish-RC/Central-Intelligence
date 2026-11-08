"""
Media gallery and artifact cataloging subsystem.
Provides querying, filtering, storage tracking, and provenance metadata.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from media_gen.core.models import MediaArtifact, MediaType


class MediaGallery:
    """In-memory and persistent catalog of generated media artifacts."""

    def __init__(self):
        self._artifacts: Dict[str, MediaArtifact] = {}
        self._project_index: Dict[str, List[str]] = {}

    def save(self, artifact: MediaArtifact, project_id: str = "default") -> None:
        self._artifacts[artifact.id] = artifact
        if project_id not in self._project_index:
            self._project_index[project_id] = []
        if artifact.id not in self._project_index[project_id]:
            self._project_index[project_id].append(artifact.id)

    def get(self, artifact_id: str) -> Optional[MediaArtifact]:
        return self._artifacts.get(artifact_id)

    def list_artifacts(
        self,
        project_id: Optional[str] = None,
        media_type: Optional[MediaType] = None,
        limit: int = 50,
    ) -> List[MediaArtifact]:
        items: List[MediaArtifact] = []

        if project_id:
            ids = self._project_index.get(project_id, [])
            for aid in ids:
                art = self._artifacts.get(aid)
                if art:
                    if media_type is None or art.media_type == media_type:
                        items.append(art)
        else:
            for art in self._artifacts.values():
                if media_type is None or art.media_type == media_type:
                    items.append(art)

        items.sort(key=lambda a: a.created_at, reverse=True)
        return items[:limit]

    def delete(self, artifact_id: str) -> bool:
        if artifact_id in self._artifacts:
            del self._artifacts[artifact_id]
            for plist in self._project_index.values():
                if artifact_id in plist:
                    plist.remove(artifact_id)
            return True
        return False

    def get_stats(self) -> Dict[str, int]:
        stats = {
            "total_artifacts": len(self._artifacts),
            "total_bytes": sum(a.size_bytes for a in self._artifacts.values()),
            "images": sum(1 for a in self._artifacts.values() if a.media_type == MediaType.IMAGE),
            "audios": sum(1 for a in self._artifacts.values() if a.media_type == MediaType.AUDIO),
            "videos": sum(1 for a in self._artifacts.values() if a.media_type == MediaType.VIDEO),
        }
        return stats
