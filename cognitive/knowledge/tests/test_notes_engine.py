"""Unit tests for the Notes Engine: CRUD, wiki-links, backlinks graph, and tags."""

from uuid import uuid4
import pytest
from knowledge.core.models import Note
from knowledge.notes.store import NoteStore
from knowledge.notes.parser import NoteParser
from knowledge.notes.graph import KnowledgeGraph


@pytest.fixture
def note_store(tmp_path):
    db_path = str(tmp_path / "notes_test.db")
    return NoteStore(db_path=db_path)


def test_note_creation_and_slug_generation(note_store):
    note = Note(
        title="Distributed Consensus Architecture",
        content="Overview of Raft and Paxos protocols. #algorithms #consensus",
        project_id="proj_distributed",
    )
    saved = note_store.save_note(note)

    assert saved.id == note.id
    assert saved.slug == "distributed-consensus-architecture"
    assert "algorithms" in saved.tags
    assert "consensus" in saved.tags

    fetched = note_store.get_note(saved.id, project_id="proj_distributed")
    assert fetched is not None
    assert fetched.title == "Distributed Consensus Architecture"


def test_frontmatter_and_inline_tags_parsing():
    content = """---
title: "Vector Embeddings Guide"
tags: [ai, embeddings, rag]
author: Alice
priority: 1
---

This guide covers dense retrieval in [[Model Gateway]].
Also refers to #semantic-search and #python.
"""
    body, meta, tags, links = NoteParser.parse(content)
    assert meta["title"] == "Vector Embeddings Guide"
    assert meta["author"] == "Alice"
    assert meta["priority"] == 1
    assert "ai" in tags
    assert "embeddings" in tags
    assert "rag" in tags
    assert "semantic-search" in tags
    assert "python" in tags
    assert "Model Gateway" in links


def test_wiki_links_and_backlinks_graph(note_store):
    graph = KnowledgeGraph(note_store)
    proj = "proj_ai"

    # Note 1: Architecture
    note_arch = Note(
        title="System Architecture",
        content="Our core architecture depends on [[Model Gateway]] and [[Cryptographic Vault]].",
        project_id=proj,
    )
    note_store.save_note(note_arch)

    # Note 2: Security
    note_sec = Note(
        title="Security Standards",
        content="All secrets are secured by [[Cryptographic Vault]] with zero plaintext.",
        project_id=proj,
    )
    note_store.save_note(note_sec)

    # Note 3: Target note
    note_vault = Note(
        title="Cryptographic Vault",
        content="AES-256-GCM vault with Argon2id key derivation.",
        project_id=proj,
    )
    note_store.save_note(note_vault)

    # Backlinks for Cryptographic Vault
    backlinks = graph.get_backlinks(target_title="Cryptographic Vault", project_id=proj)
    assert len(backlinks) == 2
    sources = [b.source_title for b in backlinks]
    assert "System Architecture" in sources
    assert "Security Standards" in sources

    # Forward links from System Architecture
    fwd = graph.get_forward_links(note_arch.id, project_id=proj)
    fwd_titles = [f.title for f in fwd]
    assert "Cryptographic Vault" in fwd_titles

    # Network topology graph
    network = graph.build_network(project_id=proj)
    assert len(network["nodes"]) == 3
    assert len(network["edges"]) >= 2


def test_project_isolation(note_store):
    n1 = Note(title="Project Alpha Notes", content="Secret Alpha info", project_id="alpha")
    n2 = Note(title="Project Beta Notes", content="Secret Beta info", project_id="beta")
    note_store.save_note(n1)
    note_store.save_note(n2)

    alpha_notes = note_store.list_notes(project_id="alpha")
    beta_notes = note_store.list_notes(project_id="beta")

    assert len(alpha_notes) == 1
    assert alpha_notes[0].title == "Project Alpha Notes"
    assert len(beta_notes) == 1
    assert beta_notes[0].title == "Project Beta Notes"

    assert note_store.get_note(n1.id, project_id="beta") is None


def test_note_tag_filtering_and_deletion(note_store):
    n1 = Note(title="Note 1", content="Text #database #sql", project_id="test")
    n2 = Note(title="Note 2", content="Text #nosql #mongo", project_id="test")
    note_store.save_note(n1)
    note_store.save_note(n2)

    db_notes = note_store.list_notes(project_id="test", tag="database")
    assert len(db_notes) == 1
    assert db_notes[0].title == "Note 1"

    # Delete
    deleted = note_store.delete_note(n1.id)
    assert deleted is True
    assert note_store.get_note(n1.id) is None
