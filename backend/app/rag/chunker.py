import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TextChunk:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: Optional[str] = None


class MarkdownHeadingChunker:
    """
    Heading-aware Markdown chunker that preserves document hierarchy,
    guarantees code block integrity, and attaches rich metadata.
    """

    def __init__(self, max_chunk_size: int = 800, chunk_overlap: int = 100):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_markdown(
        self,
        markdown_text: str,
        repository: str,
        file: str = "README.md",
        branch: str = "main",
    ) -> List[TextChunk]:
        if not markdown_text or not markdown_text.strip():
            return []

        lines = markdown_text.splitlines()
        sections: List[Dict[str, Any]] = []

        current_heading = "Overview"
        current_level = 1
        current_lines: List[str] = []
        in_code_block = False

        heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

        for line in lines:
            stripped = line.strip()
            # Check for fenced code block toggle
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue

            # Check for markdown heading (only outside code blocks)
            if not in_code_block:
                heading_match = heading_pattern.match(line)
                if heading_match:
                    # Flush previous section if it has content
                    if current_lines:
                        section_text = "\n".join(current_lines).strip()
                        if section_text:
                            sections.append({
                                "section": current_heading,
                                "heading_level": current_level,
                                "text": section_text,
                            })
                    current_level = len(heading_match.group(1))
                    current_heading = heading_match.group(2).strip()
                    current_lines = [line]
                    continue

            current_lines.append(line)

        # Flush final section
        if current_lines:
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append({
                    "section": current_heading,
                    "heading_level": current_level,
                    "text": section_text,
                })

        # Process each section into appropriately sized chunks
        all_chunks: List[TextChunk] = []
        chunk_idx = 0

        for sec in sections:
            sec_name = sec["section"]
            sec_level = sec["heading_level"]
            sec_text = sec["text"]

            if len(sec_text) <= self.max_chunk_size:
                meta = {
                    "source": "github",
                    "repository": repository,
                    "file": file,
                    "section": sec_name,
                    "heading_level": sec_level,
                    "branch": branch,
                }
                all_chunks.append(TextChunk(
                    text=sec_text,
                    metadata=meta,
                    chunk_id=f"{repository}_{file}_{chunk_idx}",
                ))
                chunk_idx += 1
            else:
                # Split large sections preserving code blocks
                sub_chunks = self._split_large_section(sec_text, sec_name)
                for sub_text in sub_chunks:
                    meta = {
                        "source": "github",
                        "repository": repository,
                        "file": file,
                        "section": sec_name,
                        "heading_level": sec_level,
                        "branch": branch,
                    }
                    all_chunks.append(TextChunk(
                        text=sub_text,
                        metadata=meta,
                        chunk_id=f"{repository}_{file}_{chunk_idx}",
                    ))
                    chunk_idx += 1

        return all_chunks

    def _split_large_section(self, section_text: str, section_title: str) -> List[str]:
        """
        Splits a long section into smaller chunks while avoiding breaking inside code blocks.
        """
        lines = section_text.splitlines()
        chunks: List[str] = []
        current_chunk_lines: List[str] = []
        current_len = 0
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block

            current_chunk_lines.append(line)
            current_len += len(line) + 1

            # Only split on paragraph/empty lines or when size exceeds threshold AND not inside code block
            if current_len >= self.max_chunk_size and not in_code_block:
                chunk_str = "\n".join(current_chunk_lines).strip()
                if chunk_str:
                    # Prepend section context if not present
                    if not chunk_str.startswith("#"):
                        chunk_str = f"## {section_title} (cont.)\n" + chunk_str
                    chunks.append(chunk_str)
                current_chunk_lines = []
                current_len = 0

        if current_chunk_lines:
            chunk_str = "\n".join(current_chunk_lines).strip()
            if chunk_str:
                if not chunk_str.startswith("#") and len(chunks) > 0:
                    chunk_str = f"## {section_title} (cont.)\n" + chunk_str
                chunks.append(chunk_str)

        return chunks if chunks else [section_text]
