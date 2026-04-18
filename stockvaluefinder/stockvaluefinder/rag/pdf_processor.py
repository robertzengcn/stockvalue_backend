"""PDF processing module for RAG pipeline.

Extracts structured content from PDF documents with page references,
splits content into parent-child chunks, and preserves tables as
atomic units for financial report analysis.

Uses PyMuPDF (fitz) for extraction and tiktoken for token counting.
"""

import logging
import uuid
from typing import Any

import tiktoken

from stockvaluefinder.models.document import ChunkMetadata, DocumentChunk
from stockvaluefinder.utils.errors import DataValidationError

logger = logging.getLogger(__name__)

# Module-level token encoder (cl100k_base for approximate bge-m3 alignment)
_encoding = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    """Count tokens in text using cl100k_base encoding.

    Args:
        text: Input text to count tokens for.

    Returns:
        Number of tokens in the text.
    """
    return len(_encoding.encode(text))


def extract_pdf_content(pdf_bytes: bytes) -> list[dict[str, Any]]:
    """Extract structured content from a PDF with page references.

    Parses a PDF document and returns a list of content blocks, each
    containing type (text or table), content text, page number (1-based),
    and bounding box coordinates.

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        List of dicts with keys: type, content, page, bbox.

    Raises:
        DataValidationError: If the PDF is invalid or cannot be parsed.
    """
    import pymupdf

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise DataValidationError(
            "Invalid or corrupted PDF file",
            field="pdf_bytes",
            value=f"<{len(pdf_bytes)} bytes>",
        ) from exc

    blocks: list[dict[str, Any]] = []

    try:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            seen_table_bboxes: list[tuple[float, ...]] = []

            # Extract tables first (preserve as atomic units)
            tables = page.find_tables()
            for table in tables:
                table_md = table.to_markdown()
                if table_md.strip():
                    bbox = tuple(table.bbox)
                    seen_table_bboxes.append(bbox)
                    blocks.append(
                        {
                            "type": "table",
                            "content": table_md,
                            "page": page_num + 1,
                            "bbox": bbox,
                        }
                    )

            # Extract text blocks with structure
            text_dict = page.get_text("dict", sort=True)
            for block in text_dict["blocks"]:
                if block["type"] == 0:  # Text block
                    text = "".join(
                        span["text"]
                        for line in block["lines"]
                        for span in line["spans"]
                    ).strip()
                    if text:
                        block_bbox = tuple(block["bbox"])
                        # Skip text blocks that overlap with detected tables
                        if not _bbox_overlaps_any(block_bbox, seen_table_bboxes):
                            blocks.append(
                                {
                                    "type": "text",
                                    "content": text,
                                    "page": page_num + 1,
                                    "bbox": block_bbox,
                                }
                            )
    finally:
        doc.close()

    return blocks


def _bbox_overlaps_any(
    bbox: tuple[float, ...], table_bboxes: list[tuple[float, ...]]
) -> bool:
    """Check if a bounding box overlaps with any table bounding box.

    Args:
        bbox: Bounding box to check (x1, y1, x2, y2).
        table_bboxes: List of table bounding boxes.

    Returns:
        True if bbox significantly overlaps with any table bbox.
    """
    x1, y1, x2, y2 = bbox
    for tb in table_bboxes:
        tx1, ty1, tx2, ty2 = tb
        # Check for overlap
        overlap_x = max(0, min(x2, tx2) - max(x1, tx1))
        overlap_y = max(0, min(y2, ty2) - max(y1, ty1))
        area_a = (x2 - x1) * (y2 - y1)
        if area_a > 0:
            overlap_area = overlap_x * overlap_y
            if overlap_area / area_a > 0.5:
                return True
    return False


def chunk_into_parents(
    content_blocks: list[dict[str, Any]],
    target_tokens: int = 2000,
) -> list[DocumentChunk]:
    """Group content blocks into parent chunks of approximately target_tokens.

    Blocks from consecutive pages are grouped together until the target
    token count is exceeded. Tables are always preserved as atomic units
    even if they exceed the target size.

    Args:
        content_blocks: List of content block dicts from extract_pdf_content.
        target_tokens: Target token count per parent chunk (default 2000).

    Returns:
        List of DocumentChunk objects with chunk_type='parent'.
    """
    if not content_blocks:
        return []

    parents: list[DocumentChunk] = []
    current_blocks: list[dict[str, Any]] = []
    current_tokens = 0

    for block in content_blocks:
        block_text = block.get("content", "")
        block_tokens = _count_tokens(block_text)
        is_table = block.get("type") == "table"

        # Start a new parent chunk if:
        # 1. Current chunk is already at target, OR
        # 2. Adding this block would exceed target AND we already have content
        #    (but tables always fit in current chunk as atomic units)
        would_exceed = (
            current_tokens + block_tokens
        ) > target_tokens and current_tokens > 0

        if would_exceed and not is_table:
            # Flush current parent
            if current_blocks:
                parents.append(_build_parent_chunk(current_blocks))
            current_blocks = [block]
            current_tokens = block_tokens
        else:
            current_blocks.append(block)
            current_tokens += block_tokens

    # Flush remaining blocks
    if current_blocks:
        parents.append(_build_parent_chunk(current_blocks))

    return parents


def _build_parent_chunk(blocks: list[dict[str, Any]]) -> DocumentChunk:
    """Build a parent DocumentChunk from a list of content blocks.

    Args:
        blocks: Content blocks to combine into a parent chunk.

    Returns:
        DocumentChunk with chunk_type='parent'.
    """
    combined_content = "\n\n".join(block.get("content", "") for block in blocks)
    # Use the page from the first block
    first_page = blocks[0].get("page", 1) if blocks else 1

    return DocumentChunk(
        chunk_id=str(uuid.uuid4()),
        content=combined_content,
        metadata=ChunkMetadata(
            document_id="",
            parent_id=None,
            page_number=first_page,
            section="",
            ticker="",
            year=0,
            report_type="",
            company_name="",
            filing_date="",
            chunk_type="parent",
            token_count=_count_tokens(combined_content),
        ),
    )


def chunk_parents_into_children(
    parent_chunks: list[DocumentChunk],
    target_tokens: int = 500,
) -> list[DocumentChunk]:
    """Split parent chunks into smaller child chunks.

    Parent chunks are split at sentence/paragraph boundaries to
    approximately target_tokens. Tables within parent chunks are
    preserved as atomic child chunks even if they exceed the target.

    Args:
        parent_chunks: List of parent DocumentChunk objects.
        target_tokens: Target token count per child chunk (default 500).

    Returns:
        List of DocumentChunk objects with chunk_type='child'.
    """
    children: list[DocumentChunk] = []

    for parent in parent_chunks:
        parent_children = _split_parent_into_children(parent, target_tokens)
        children.extend(parent_children)

    return children


def _split_parent_into_children(
    parent: DocumentChunk,
    target_tokens: int,
) -> list[DocumentChunk]:
    """Split a single parent chunk into child chunks.

    Args:
        parent: Parent DocumentChunk to split.
        target_tokens: Target token count per child.

    Returns:
        List of child DocumentChunk objects referencing the parent.
    """
    content = parent.content
    token_count = _count_tokens(content)

    # If content fits in one child chunk, return as-is
    if token_count <= target_tokens:
        return [_create_child_chunk(content, parent)]

    # Split into paragraphs/sentences
    paragraphs = _split_into_paragraphs(content)

    children: list[DocumentChunk] = []
    current_text = ""
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        # Check if this paragraph is a table (starts with |)
        is_table = para.strip().startswith("|") and "|" in para.strip()[1:]

        would_exceed = (
            current_tokens + para_tokens
        ) > target_tokens and current_tokens > 0

        if would_exceed and not is_table:
            if current_text:
                children.append(_create_child_chunk(current_text.strip(), parent))
            current_text = para
            current_tokens = para_tokens
        else:
            if current_text:
                current_text += "\n\n" + para
            else:
                current_text = para
            current_tokens += para_tokens

    # Flush remaining text
    if current_text:
        children.append(_create_child_chunk(current_text.strip(), parent))

    # If we only produced one child from a large parent, it means no good
    # split points were found; that is acceptable.
    return children


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs at double-newline boundaries.

    Args:
        text: Text to split.

    Returns:
        List of paragraph strings.
    """
    paragraphs = text.split("\n\n")
    # Filter empty paragraphs
    return [p for p in paragraphs if p.strip()]


def _create_child_chunk(content: str, parent: DocumentChunk) -> DocumentChunk:
    """Create a child DocumentChunk inheriting metadata from parent.

    Args:
        content: Text content for the child chunk.
        parent: Parent DocumentChunk to inherit metadata from.

    Returns:
        DocumentChunk with chunk_type='child'.
    """
    return DocumentChunk(
        chunk_id=str(uuid.uuid4()),
        content=content,
        metadata=ChunkMetadata(
            document_id=parent.metadata.document_id,
            parent_id=parent.chunk_id,
            page_number=parent.metadata.page_number,
            section=parent.metadata.section,
            ticker=parent.metadata.ticker,
            year=parent.metadata.year,
            report_type=parent.metadata.report_type,
            company_name=parent.metadata.company_name,
            filing_date=parent.metadata.filing_date,
            chunk_type="child",
            token_count=_count_tokens(content),
        ),
    )


def detect_tables_and_preserve(
    content_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify and preserve table boundaries in content blocks.

    Table blocks are passed through as-is (atomic units). Text blocks
    are also passed through unchanged. This function serves as a
    validation/normalization step that ensures tables are properly tagged.

    Args:
        content_blocks: List of content block dicts with type/content/page/bbox.

    Returns:
        List of content blocks with tables preserved as atomic units.
    """
    result: list[dict[str, Any]] = []

    for block in content_blocks:
        block_type = block.get("type", "text")

        if block_type == "table":
            # Tables are always preserved as atomic units
            result.append(
                {
                    "type": "table",
                    "content": block.get("content", ""),
                    "page": block.get("page", 1),
                    "bbox": block.get("bbox", (0, 0, 0, 0)),
                }
            )
        else:
            result.append(
                {
                    "type": "text",
                    "content": block.get("content", ""),
                    "page": block.get("page", 1),
                    "bbox": block.get("bbox", (0, 0, 0, 0)),
                }
            )

    return result


__all__ = [
    "extract_pdf_content",
    "chunk_into_parents",
    "chunk_parents_into_children",
    "detect_tables_and_preserve",
    "DocumentChunk",
    "ChunkMetadata",
]
