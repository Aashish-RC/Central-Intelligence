"""Knowledge Graph: Bidirectional link analysis, backlink resolution, and network mapping."""

import re
from typing import Any, Dict, List
from uuid import UUID

from ..core.models import BacklinkRef, Note
from .store import NoteStore
from .parser import NoteParser


class KnowledgeGraph:
    """Computes bidirectional relationships and backlinks across notes in a project."""

    def __init__(self, store: NoteStore):
        self._store = store

    def get_backlinks(self, target_title: str, project_id: str = "default") -> List[BacklinkRef]:
        """Find all notes referencing target_title via [[wiki-links]]."""
        notes = self._store.list_notes(project_id=project_id)
        target_slug = NoteParser.slugify(target_title)
        backlinks: List[BacklinkRef] = []

        pattern = re.compile(
            r"\[\[(" + re.escape(target_title) + r"|" + re.escape(target_slug) + r")(?:\s*\|[^\\]]+)?\]\]",
            re.IGNORECASE,
        )

        for n in notes:
            # Check outgoing links
            matches_link = any(
                NoteParser.slugify(link) == target_slug or link.lower() == target_title.lower()
                for link in n.outgoing_links
            )
            if matches_link:
                # Extract snippet around link
                snippet = ""
                match = pattern.search(n.content)
                if match:
                    start = max(0, match.start() - 40)
                    end = min(len(n.content), match.end() + 40)
                    snippet = n.content[start:end].strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(n.content):
                        snippet = snippet + "..."

                backlinks.append(
                    BacklinkRef(
                        source_note_id=str(n.id),
                        source_title=n.title,
                        target_title=target_title,
                        context_snippet=snippet,
                    )
                )

        return backlinks

    def get_forward_links(self, note_id: UUID, project_id: str = "default") -> List[Note]:
        """Find all existing notes linked out from the given note."""
        note = self._store.get_note(note_id=note_id, project_id=project_id)
        if not note:
            return []

        resolved: List[Note] = []
        for link in note.outgoing_links:
            target = self._store.get_note_by_title(title=link, project_id=project_id)
            if target and target.id != note.id:
                resolved.append(target)
        return resolved

    def build_network(self, project_id: str = "default") -> Dict[str, Any]:
        """Construct a complete nodes & edges graph for visualization."""
        notes = self._store.list_notes(project_id=project_id)
        title_to_id = {NoteParser.slugify(n.title): str(n.id) for n in notes}

        nodes = []
        for n in notes:
            nodes.append({
                "id": str(n.id),
                "title": n.title,
                "slug": n.slug,
                "tags": n.tags,
            })

        edges = []
        for n in notes:
            for link in n.outgoing_links:
                link_slug = NoteParser.slugify(link)
                target_id = title_to_id.get(link_slug)
                if target_id and target_id != str(n.id):
                    edges.append({
                        "source": str(n.id),
                        "target": target_id,
                        "label": link,
                    })

        return {"nodes": nodes, "edges": edges}
