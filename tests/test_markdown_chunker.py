"""
Unit tests for the Intelligent Hierarchical Markdown Chunker.
"""

from indexer.markdown_chunker import MarkdownChunker


def test_markdown_chunker_basic_hierarchy():
    markdown = """# My Project

This is a general overview of the project.

## Installation

### Windows
Run the following command for Windows:
```bash
winget install myproject
```

### Linux
Run apt install:
```bash
sudo apt install myproject
```

## Features
- Feature A: High speed
- Feature B: Low memory
- Feature C: Open source
"""
    chunker = MarkdownChunker(chunk_size=500, chunk_overlap=50)
    chunks = chunker.chunk_markdown(markdown)

    assert len(chunks) >= 3
    
    paths = [c.section_path for c in chunks]
    assert any("Installation > Windows" in p for p in paths)
    assert any("Installation > Linux" in p for p in paths)
    assert any("Features" in p for p in paths)

    # Check code block preservation
    win_chunk = next(c for c in chunks if "Windows" in c.section_path)
    assert "winget install myproject" in win_chunk.content
    assert "```bash" in win_chunk.content


def test_markdown_chunker_table_preservation():
    markdown = """# API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | /api/health | Server health |
| POST | /api/chat | Chat with README |
| GET | /api/projects/:id | Project details |

Additional details about the API.
"""
    chunker = MarkdownChunker(chunk_size=400, chunk_overlap=50)
    chunks = chunker.chunk_markdown(markdown)

    assert len(chunks) >= 1
    table_chunk = chunks[0]
    assert "| Method | Endpoint | Description |" in table_chunk.content
    assert "| POST | /api/chat | Chat with README |" in table_chunk.content


def test_markdown_chunker_oversized_split():
    long_paragraph = "Word " * 300  # 1500 chars
    markdown = f"# Architecture\n\n{long_paragraph}"

    chunker = MarkdownChunker(chunk_size=400, chunk_overlap=50)
    chunks = chunker.chunk_markdown(markdown)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.section_title == "Architecture"
        assert chunk.section_path == "Architecture"
        assert len(chunk.content) <= 500


def test_markdown_chunker_empty_input():
    chunker = MarkdownChunker()
    assert chunker.chunk_markdown("") == []
    assert chunker.chunk_markdown("   \n\n  ") == []
