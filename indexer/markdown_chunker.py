"""
Intelligent Markdown-Aware Hierarchical Chunker.

Parses Markdown documents into structured sections based on heading hierarchy (#, ##, ###),
preserves code blocks, tables, and lists intact without mid-structure truncation,
and applies overlapping windowing when individual sections exceed the maximum chunk size.
"""

from dataclasses import dataclass
import re
from typing import List, Dict, Any, Optional


@dataclass
class MarkdownChunk:
    chunk_index: int
    section_title: str
    section_path: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "section_title": self.section_title,
            "section_path": self.section_path,
            "content": self.content,
        }


class MarkdownChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        """
        Initializes the hierarchical Markdown chunker.
        
        Args:
            chunk_size: Target maximum character length for each chunk.
            chunk_overlap: Number of characters to overlap between consecutive split chunks.
        """
        self.chunk_size = max(200, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size // 2))

    def parse_sections(self, markdown_text: str) -> List[Dict[str, Any]]:
        """
        Parses Markdown text into a hierarchy of sections based on headings.
        Returns a flat list of sections with breadcrumb paths and content blocks.
        """
        lines = markdown_text.splitlines()
        sections: List[Dict[str, Any]] = []
        
        # State tracking
        current_heading_level = 0
        heading_stack: List[str] = []  # Stack of heading titles by level
        current_section_title = "Overview"
        current_lines: List[str] = []
        in_code_block = False

        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            # Check for fenced code block toggle
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block

            heading_match = heading_pattern.match(line) if not in_code_block else None

            if heading_match:
                # Flush previous section if it has content
                section_content = "\n".join(current_lines).strip()
                if section_content:
                    path = " > ".join(heading_stack) if heading_stack else current_section_title
                    sections.append({
                        "section_title": current_section_title,
                        "section_path": path,
                        "content": section_content,
                    })
                    current_lines = []

                # Process new heading
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Clean title (remove markdown links, bold, tags)
                cleaned_title = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", title)
                cleaned_title = re.sub(r"[*_`]", "", cleaned_title).strip()

                # Adjust heading stack for hierarchy
                if level > len(heading_stack):
                    heading_stack.append(cleaned_title)
                else:
                    heading_stack = heading_stack[:level - 1]
                    heading_stack.append(cleaned_title)

                current_heading_level = level
                current_section_title = cleaned_title
            else:
                current_lines.append(line)

        # Flush final section
        final_content = "\n".join(current_lines).strip()
        if final_content:
            path = " > ".join(heading_stack) if heading_stack else current_section_title
            sections.append({
                "section_title": current_section_title,
                "section_path": path,
                "content": final_content,
            })

        return sections

    def _split_into_atomic_blocks(self, text: str) -> List[str]:
        """
        Splits text into atomic units (code blocks, tables, list groups, paragraphs)
        that should preferably remain unsplit.
        """
        lines = text.splitlines()
        blocks: List[str] = []
        current_block: List[str] = []
        in_code_block = False
        in_table = False

        for line in lines:
            stripped = line.strip()

            # Handle Code Blocks
            if stripped.startswith("```"):
                if in_code_block:
                    # Closing code block
                    current_block.append(line)
                    blocks.append("\n".join(current_block))
                    current_block = []
                    in_code_block = False
                    continue
                else:
                    # Opening code block: flush preceding block
                    if current_block:
                        blocks.append("\n".join(current_block))
                        current_block = []
                    in_code_block = True
                    current_block.append(line)
                    continue

            if in_code_block:
                current_block.append(line)
                continue

            # Handle Markdown Tables
            if stripped.startswith("|") and stripped.endswith("|"):
                if not in_table:
                    if current_block:
                        blocks.append("\n".join(current_block))
                        current_block = []
                    in_table = True
                current_block.append(line)
                continue
            elif in_table:
                # End of table
                in_table = False
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []

            # Handle Blank lines as paragraph separators
            if not stripped:
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                continue

            # Regular text line / list item
            current_block.append(line)

        if current_block:
            blocks.append("\n".join(current_block))

        return [b.strip() for b in blocks if b.strip()]

    def _split_oversized_block(self, block: str) -> List[str]:
        """Splits a single block that exceeds chunk_size with overlap."""
        if len(block) <= self.chunk_size:
            return [block]

        chunks = []
        start = 0
        while start < len(block):
            end = start + self.chunk_size
            if end >= len(block):
                chunks.append(block[start:].strip())
                break
            
            # Find nearest newline or space backwards to avoid splitting words
            split_at = block.rfind("\n", start, end)
            if split_at == -1 or split_at <= start:
                split_at = block.rfind(" ", start, end)
            if split_at == -1 or split_at <= start:
                split_at = end

            chunks.append(block[start:split_at].strip())
            start = max(start + 1, split_at - self.chunk_overlap)

        return [c for c in chunks if c]

    def chunk_markdown(self, markdown_text: str) -> List[MarkdownChunk]:
        """
        Performs full hierarchical chunking on a Markdown document.
        
        Returns:
            List of MarkdownChunk objects with section path, title, index, and content.
        """
        if not markdown_text or not markdown_text.strip():
            return []

        raw_sections = self.parse_sections(markdown_text)
        all_chunks: List[MarkdownChunk] = []
        chunk_idx = 0

        for section in raw_sections:
            sec_title = section["section_title"]
            sec_path = section["section_path"]
            sec_content = section["content"]

            atomic_blocks = self._split_into_atomic_blocks(sec_content)
            if not atomic_blocks:
                continue

            current_chunk_blocks: List[str] = []
            current_len = 0

            for block in atomic_blocks:
                # If block alone is larger than chunk_size, handle it separately
                if len(block) > self.chunk_size:
                    # Flush current accumulator
                    if current_chunk_blocks:
                        body_str = "\n\n".join(current_chunk_blocks).strip()
                        content_str = f"## Section: {sec_path}\n{body_str}"
                        all_chunks.append(MarkdownChunk(
                            chunk_index=chunk_idx,
                            section_title=sec_title,
                            section_path=sec_path,
                            content=content_str,
                        ))
                        chunk_idx += 1
                        current_chunk_blocks = []
                        current_len = 0

                    sub_chunks = self._split_oversized_block(block)
                    for sub in sub_chunks:
                        sub_content = f"## Section: {sec_path}\n{sub}"
                        all_chunks.append(MarkdownChunk(
                            chunk_index=chunk_idx,
                            section_title=sec_title,
                            section_path=sec_path,
                            content=sub_content,
                        ))
                        chunk_idx += 1
                    continue

                # Check if adding this block exceeds target chunk size
                potential_len = current_len + (2 if current_chunk_blocks else 0) + len(block)
                if potential_len <= self.chunk_size:
                    current_chunk_blocks.append(block)
                    current_len = potential_len
                else:
                    # Flush current chunk
                    if current_chunk_blocks:
                        content_str = "\n\n".join(current_chunk_blocks).strip()
                        all_chunks.append(MarkdownChunk(
                            chunk_index=chunk_idx,
                            section_title=sec_title,
                            section_path=sec_path,
                            content=content_str,
                        ))
                        chunk_idx += 1

                    current_chunk_blocks = [block]
                    current_len = len(block)

            # Flush accumulated blocks with section context header
            if current_chunk_blocks:
                body_str = "\n\n".join(current_chunk_blocks).strip()
                content_str = f"## Section: {sec_path}\n{body_str}"
                all_chunks.append(MarkdownChunk(
                    chunk_index=chunk_idx,
                    section_title=sec_title,
                    section_path=sec_path,
                    content=content_str,
                ))
                chunk_idx += 1

        return all_chunks
