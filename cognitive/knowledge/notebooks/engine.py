"""Source-Grounded Notebook Engine: Multi-cell sessions, file citations, and synthesis."""

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional
from uuid import UUID

from ..core.interfaces import BaseNotebookStore
from ..core.models import (
    CellType,
    CitationAnchor,
    Notebook,
    NotebookCell,
    utc_now,
)


class NotebookEngine(BaseNotebookStore):
    """Manages multi-cell interactive notebooks with verifiable source file citations."""

    def __init__(self, db_path: str = "./notebooks.db"):
        self._db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row

        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notebooks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    description TEXT,
                    cells TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_notebooks_project
                ON notebooks(project_id);
            """)
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def _row_to_notebook(self, row: sqlite3.Row) -> Notebook:
        from datetime import datetime
        raw_cells = json.loads(row["cells"])
        cells = [NotebookCell(**c) for c in raw_cells]
        return Notebook(
            id=UUID(row["id"]),
            project_id=row["project_id"],
            title=row["title"],
            description=row["description"],
            cells=cells,
            tags=json.loads(row["tags"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_notebook(self, notebook: Notebook) -> Notebook:
        now = utc_now().isoformat()
        notebook.updated_at = utc_now()
        cells_json = json.dumps([c.model_dump(mode="json") for c in notebook.cells])

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO notebooks (
                        id, project_id, title, description, cells, tags, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        project_id = excluded.project_id,
                        title = excluded.title,
                        description = excluded.description,
                        cells = excluded.cells,
                        tags = excluded.tags,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(notebook.id),
                        notebook.project_id,
                        notebook.title,
                        notebook.description,
                        cells_json,
                        json.dumps(notebook.tags),
                        notebook.created_at.isoformat(),
                        now,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()
        return notebook

    def get_notebook(self, notebook_id: UUID, project_id: Optional[str] = None) -> Optional[Notebook]:
        query = "SELECT * FROM notebooks WHERE id = ?"
        params: list = [str(notebook_id)]
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query, params)
                row = cur.fetchone()
                return self._row_to_notebook(row) if row else None
            finally:
                if self._memory_conn is None:
                    conn.close()

    def list_notebooks(self, project_id: str = "default") -> List[Notebook]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT * FROM notebooks WHERE project_id = ? ORDER BY updated_at DESC",
                    (project_id,),
                )
                return [self._row_to_notebook(r) for r in cur.fetchall()]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_notebook(self, notebook_id: UUID) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute("DELETE FROM notebooks WHERE id = ?", (str(notebook_id),))
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def add_cell(self, notebook_id: UUID, cell: NotebookCell) -> Notebook:
        nb = self.get_notebook(notebook_id)
        if not nb:
            raise KeyError(f"Notebook {notebook_id} not found")
        nb.cells.append(cell)
        return self.save_notebook(nb)

    def add_grounded_excerpt_cell(
        self,
        notebook_id: UUID,
        content: str,
        quote_text: str,
        file_id: str,
        sha256: str,
        source_name: str,
        chunk_index: int = 0,
    ) -> Notebook:
        """Helper to append a cell with verified source citation grounding."""
        citation = CitationAnchor(
            quote_text=quote_text,
            file_id=file_id,
            sha256=sha256,
            source_name=source_name,
            chunk_index=chunk_index,
        )
        cell = NotebookCell(
            cell_type=CellType.GROUNDED_EXCERPT,
            content=content,
            citations=[citation],
        )
        return self.add_cell(notebook_id, cell)

    def export_summary(self, notebook_id: UUID) -> str:
        """Renders the notebook cells into a cohesive grounded markdown document."""
        nb = self.get_notebook(notebook_id)
        if not nb:
            raise KeyError(f"Notebook {notebook_id} not found")

        lines = [f"# {nb.title}", ""]
        if nb.description:
            lines.extend([nb.description, ""])

        for i, cell in enumerate(nb.cells, 1):
            if cell.cell_type == CellType.MARKDOWN:
                lines.extend([cell.content, ""])
            elif cell.cell_type == CellType.GROUNDED_EXCERPT:
                lines.extend([f"### Source Grounding {i}", f"> {cell.content}", ""])
                for cit in cell.citations:
                    lines.append(f"- **Source**: `{cit.source_name}` (`{cit.sha256[:8] if cit.sha256 else 'sha'}`)")
                    lines.append(f"- **Quote**: *\"{cit.quote_text}\"*")
                lines.append("")
            elif cell.cell_type == CellType.SYNTHESIS:
                lines.extend(["### Synthesis", cell.output or cell.content, ""])

        return "\n".join(lines).strip()
