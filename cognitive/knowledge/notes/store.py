"""SQLite-backed Note Store with project isolation, tags filtering, and auto-indexing."""
from typing import Any
import json
from pathlib import Path
import sqlite3
import threading
from typing import List, Optional
from uuid import UUID

from ..core.interfaces import BaseNoteStore
from ..core.models import Note, utc_now
from .parser import NoteParser


class NoteStore(BaseNoteStore):
    """SQLite implementation of the Personal Knowledge Base note store."""

    def __init__(self, db_path: str = "./notes.db"):
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
        from storage.migrations import SchemaMigrator, Migration, add_column_if_missing
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    outgoing_links TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            def _migrate_v1_indexes(c: sqlite3.Connection):
                c.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_project_title
                    ON notes(project_id, title);
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_notes_project_slug
                    ON notes(project_id, slug);
                """)

            def _migrate_v2_tenant(c: sqlite3.Connection):
                add_column_if_missing(c, "notes", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_notes_tenant
                    ON notes(tenant_id);
                """)

            migrator = SchemaMigrator(conn)
            migrator.apply_all([
                Migration(version=1, name="initial_notes_indexes", up=_migrate_v1_indexes),
                Migration(version=2, name="notes_tenant_id", up=_migrate_v2_tenant),
            ])
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def _row_to_note(self, row: sqlite3.Row) -> Note:
        from datetime import datetime
        cols = row.keys()
        return Note(
            id=UUID(row["id"]),
            tenant_id=row["tenant_id"] if "tenant_id" in cols and row["tenant_id"] else "default",
            project_id=row["project_id"],
            title=row["title"],
            slug=row["slug"],
            content=row["content"],
            tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]),
            outgoing_links=json.loads(row["outgoing_links"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_note(self, note: Note) -> Note:
        # Automatically parse wiki-links and tags from body
        body, parsed_meta, parsed_tags, links = NoteParser.parse(note.content)
        
        # Merge tags & metadata
        merged_tags = sorted(list(set(note.tags + parsed_tags)))
        merged_meta = {**note.metadata, **parsed_meta}
        note.tags = merged_tags
        note.metadata = merged_meta
        note.outgoing_links = links
        if not note.slug:
            note.slug = NoteParser.slugify(note.title)
        
        now = utc_now().isoformat()
        note.updated_at = utc_now()

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO notes (
                        id, tenant_id, project_id, title, slug, content, tags,
                        metadata, outgoing_links, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        tenant_id = excluded.tenant_id,
                        project_id = excluded.project_id,
                        title = excluded.title,
                        slug = excluded.slug,
                        content = excluded.content,
                        tags = excluded.tags,
                        metadata = excluded.metadata,
                        outgoing_links = excluded.outgoing_links,
                        updated_at = excluded.updated_at
                    ON CONFLICT(project_id, title) DO UPDATE SET
                        tenant_id = excluded.tenant_id,
                        slug = excluded.slug,
                        content = excluded.content,
                        tags = excluded.tags,
                        metadata = excluded.metadata,
                        outgoing_links = excluded.outgoing_links,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(note.id),
                        getattr(note, "tenant_id", "default") or "default",
                        note.project_id,
                        note.title,
                        note.slug,
                        note.content,
                        json.dumps(note.tags),
                        json.dumps(note.metadata),
                        json.dumps(note.outgoing_links),
                        note.created_at.isoformat(),
                        now,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()
        return note

    def index_document(
        self,
        file_id: str,
        content: Any,
        filename: str,
        project_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> Note:
        """Indexes an uploaded document from storage directly into knowledge base."""
        import uuid
        if isinstance(content, bytes):
            try:
                text_content = content.decode("utf-8")
            except Exception:
                text_content = f"Stored binary asset: {filename} (ID: {file_id}, size: {len(content)} bytes)"
        else:
            text_content = str(content)

        meta = {
            "source": "storage",
            "storage_file_id": file_id,
            "filename": filename,
            **(metadata or {}),
        }
        clean_tags = list(tags or [])
        if "storage" not in clean_tags:
            clean_tags.append("storage")

        note = Note(
            id=uuid.uuid4(),
            project_id=project_id,
            title=filename,
            slug=NoteParser.slugify(filename),
            content=text_content,
            tags=clean_tags,
            metadata=meta,
        )
        return self.save_note(note)

    def get_note(self, note_id: UUID, project_id: Optional[str] = None) -> Optional[Note]:
        query = "SELECT * FROM notes WHERE id = ?"
        params: list = [str(note_id)]
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query, params)
                row = cur.fetchone()
                return self._row_to_note(row) if row else None
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_note_by_title(self, title: str, project_id: str = "default") -> Optional[Note]:
        slug = NoteParser.slugify(title)
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT * FROM notes WHERE project_id = ? AND (title = ? OR slug = ?)",
                    (project_id, title, slug),
                )
                row = cur.fetchone()
                return self._row_to_note(row) if row else None
            finally:
                if self._memory_conn is None:
                    conn.close()

    def list_notes(self, project_id: str = "default", tag: Optional[str] = None) -> List[Note]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "SELECT * FROM notes WHERE project_id = ? ORDER BY updated_at DESC",
                    (project_id,),
                )
                notes = [self._row_to_note(r) for r in cur.fetchall()]
                if tag:
                    tag_clean = tag.lower().strip()
                    notes = [n for n in notes if tag_clean in [t.lower() for t in n.tags]]
                return notes
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_note(self, note_id: UUID) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute("DELETE FROM notes WHERE id = ?", (str(note_id),))
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def index_document(
        self,
        file_id: str,
        content: Any,
        filename: str,
        project_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ) -> Note:
        """Indexes a storage file into the personal knowledge base note store."""
        raw_text = (
            content.decode("utf-8", errors="ignore")
            if isinstance(content, (bytes, bytearray))
            else str(content)
        )
        title = filename or f"Document {file_id}"
        meta = metadata.copy() if metadata else {}
        meta["file_id"] = file_id
        meta["source"] = "storage"
        meta["filename"] = filename

        all_tags = list(tags) if tags else []
        if "storage" not in all_tags:
            all_tags.append("storage")

        note = Note(
            title=title,
            content=raw_text,
            project_id=project_id,
            tags=all_tags,
            metadata=meta,
        )
        return self.save_note(note)
