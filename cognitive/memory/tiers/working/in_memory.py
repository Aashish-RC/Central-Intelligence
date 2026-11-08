"""Tier 1: Local In-Memory Working Buffer with Write-Ahead Logging (WAL)."""

import json
import os
from pathlib import Path
from typing import Dict, List
import threading

from memory.core.interfaces import BaseWorkingMemory
from memory.core.models import Turn


class InMemoryWorkingMemory(BaseWorkingMemory):
    """Local in-memory working memory buffer backed by asynchronous or synchronous WAL logging."""

    def __init__(self, wal_dir: str = "./wal", enable_wal: bool = True):
        self._wal_dir = Path(wal_dir)
        self._enable_wal = enable_wal
        self._sessions: Dict[str, List[Turn]] = {}
        self._lock = threading.Lock()

        if self._enable_wal:
            self._wal_dir.mkdir(parents=True, exist_ok=True)
            self._replay_wal()

    def _get_wal_path(self, session_id: str) -> Path:
        # Sanitize session_id for filesystem
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return self._wal_dir / f"{safe_id}.jsonl"

    def _replay_wal(self) -> None:
        """Recover state from existing WAL files upon startup."""
        if not self._wal_dir.exists():
            return

        with self._lock:
            for file_path in self._wal_dir.glob("*.jsonl"):
                session_id = file_path.stem
                self._sessions[session_id] = []
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                data = json.loads(line)
                                turn = Turn.model_validate(data)
                                self._sessions[session_id].append(turn)
                except Exception:
                    # Ignore corrupted log lines gracefully
                    pass

    def _append_to_wal(self, session_id: str, turn: Turn) -> None:
        if not self._enable_wal:
            return
        wal_file = self._get_wal_path(session_id)
        try:
            line = turn.model_dump_json() + "\n"
            with open(wal_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def append_turn(self, turn: Turn) -> None:
        """Append an ephemeral turn to the session buffer and write to WAL."""
        with self._lock:
            if turn.session_id not in self._sessions:
                self._sessions[turn.session_id] = []
            self._sessions[turn.session_id].append(turn)

        self._append_to_wal(turn.session_id, turn)

    def get_active_window(self, session_id: str, limit: int = 10) -> List[Turn]:
        """Retrieve the most recent N turns for the active prompt window."""
        with self._lock:
            turns = self._sessions.get(session_id, [])
            return turns[-limit:] if limit > 0 else turns

    def get_session_turns(self, session_id: str) -> List[Turn]:
        """Retrieve all recorded turns in working memory for this session."""
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def clear(self, session_id: str) -> None:
        """Clear memory buffer and delete or rotate the WAL log."""
        with self._lock:
            self._sessions.pop(session_id, None)

        if self._enable_wal:
            wal_file = self._get_wal_path(session_id)
            if wal_file.exists():
                try:
                    wal_file.unlink()
                except Exception:
                    pass
