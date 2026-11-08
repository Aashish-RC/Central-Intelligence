"""Unit tests for Source-Grounded Notebooks: cells, citations, and summary export."""

import pytest
from knowledge.core.models import Notebook, NotebookCell, CellType
from knowledge.notebooks.engine import NotebookEngine


@pytest.fixture
def notebook_engine(tmp_path):
    db_path = str(tmp_path / "notebooks_test.db")
    return NotebookEngine(db_path=db_path)


def test_notebook_crud_and_cells(notebook_engine):
    nb = Notebook(
        title="Multi-Model Latency Benchmarks",
        description="Investigation into TTFT across Anthropic and OpenAI",
        project_id="proj_perf",
        tags=["benchmarks", "latency"],
    )
    saved = notebook_engine.save_notebook(nb)
    assert saved.id == nb.id

    # Add Markdown cell
    cell1 = NotebookCell(
        cell_type=CellType.MARKDOWN,
        content="## Methodology\nWe measured Time-To-First-Token under steady load.",
    )
    notebook_engine.add_cell(saved.id, cell1)

    fetched = notebook_engine.get_notebook(saved.id, project_id="proj_perf")
    assert fetched is not None
    assert len(fetched.cells) == 1
    assert fetched.cells[0].content.startswith("## Methodology")


def test_grounded_excerpt_cell_with_citations(notebook_engine):
    nb = Notebook(
        title="Security Compliance Audit",
        project_id="proj_audit",
    )
    saved = notebook_engine.save_notebook(nb)

    # Add grounded excerpt with verifiable file citation
    notebook_engine.add_grounded_excerpt_cell(
        notebook_id=saved.id,
        content="Zero plaintext keys verified on disk under vault tests.",
        quote_text="AES-256-GCM cipher with Argon2id zero-plaintext disk enforcement",
        file_id="blob://vault/keys/active",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        source_name="vault_spec.md",
        chunk_index=2,
    )

    fetched = notebook_engine.get_notebook(saved.id)
    assert len(fetched.cells) == 1
    excerpt_cell = fetched.cells[0]
    assert excerpt_cell.cell_type == CellType.GROUNDED_EXCERPT
    assert len(excerpt_cell.citations) == 1

    citation = excerpt_cell.citations[0]
    assert citation.source_name == "vault_spec.md"
    assert citation.chunk_index == 2
    assert "vault_spec.md" in citation.source_name
    assert citation.sha256.startswith("e3b0c442")


def test_export_grounded_summary(notebook_engine):
    nb = Notebook(
        title="Sprint 4 Synthesis",
        description="Summary of deliverables for Wave 4",
        project_id="proj_sprint",
    )
    saved = notebook_engine.save_notebook(nb)

    # 1. Markdown cell
    notebook_engine.add_cell(
        saved.id,
        NotebookCell(cell_type=CellType.MARKDOWN, content="### Key Takeaways"),
    )

    # 2. Grounded excerpt
    notebook_engine.add_grounded_excerpt_cell(
        notebook_id=saved.id,
        content="MemoryEngine implements project_id isolation across SQLite facts.",
        quote_text="Query SQLite facts filtering on project_id and is_active = 1",
        file_id="memory/engine.py",
        sha256="abc123def456",
        source_name="memory_engine.py",
    )

    # 3. Synthesis cell
    notebook_engine.add_cell(
        saved.id,
        NotebookCell(
            cell_type=CellType.SYNTHESIS,
            content="Wave 4 foundations are ready for Global Search.",
            output="Grounded conclusion: All 13 components passing test integrity.",
        ),
    )

    summary = notebook_engine.export_summary(saved.id)
    assert "# Sprint 4 Synthesis" in summary
    assert "Summary of deliverables for Wave 4" in summary
    assert "memory_engine.py" in summary
    assert "Grounded conclusion:" in summary
