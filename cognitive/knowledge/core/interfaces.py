"""Abstract Base Classes for Knowledge and Docs component."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from .models import Note, Notebook


class BaseNoteStore(ABC):
    """Abstract store for notes management."""

    @abstractmethod
    def save_note(self, note: Note) -> Note:
        """Create or update a note with automatic slug and timestamp updates."""
        pass

    @abstractmethod
    def get_note(self, note_id: UUID, project_id: Optional[str] = None) -> Optional[Note]:
        """Retrieve a note by its UUID."""
        pass

    @abstractmethod
    def get_note_by_title(self, title: str, project_id: str = "default") -> Optional[Note]:
        """Fetch a note by its exact or slug title within a project."""
        pass

    @abstractmethod
    def list_notes(self, project_id: str = "default", tag: Optional[str] = None) -> List[Note]:
        """List notes for a project, optionally filtered by tag."""
        pass

    @abstractmethod
    def delete_note(self, note_id: UUID) -> bool:
        """Permanently delete a note."""
        pass


class BaseNotebookStore(ABC):
    """Abstract store for interactive source-grounded notebooks."""

    @abstractmethod
    def save_notebook(self, notebook: Notebook) -> Notebook:
        """Create or update a notebook."""
        pass

    @abstractmethod
    def get_notebook(self, notebook_id: UUID, project_id: Optional[str] = None) -> Optional[Notebook]:
        """Retrieve a notebook by UUID."""
        pass

    @abstractmethod
    def list_notebooks(self, project_id: str = "default") -> List[Notebook]:
        """List all notebooks within a project."""
        pass

    @abstractmethod
    def delete_notebook(self, notebook_id: UUID) -> bool:
        """Permanently delete a notebook."""
        pass


class BaseKnowledgeMemoryBridge(ABC):
    """Bridge for ingesting notes and notebook syntheses into the Memory Layer."""

    @abstractmethod
    def ingest_note_to_memory(self, note: Note, user_id: str) -> Dict[str, Any]:
        """Extract and store persistent facts & archival vectors from a note."""
        pass

    @abstractmethod
    def ingest_notebook_to_memory(self, notebook: Notebook, user_id: str) -> Dict[str, Any]:
        """Extract and store synthesis cells and citations from a notebook."""
        pass
