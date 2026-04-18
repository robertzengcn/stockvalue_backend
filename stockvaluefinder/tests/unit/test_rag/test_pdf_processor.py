"""Tests for PDF processor module.

Tests PDF content extraction, parent-child chunking, and table preservation.
"""

import pytest

from stockvaluefinder.rag.pdf_processor import (
    DocumentChunk,
    ChunkMetadata,
    chunk_into_parents,
    chunk_parents_into_children,
    detect_tables_and_preserve,
    extract_pdf_content,
)


def _create_simple_pdf() -> bytes:
    """Create a minimal valid PDF with text content for testing.

    Returns:
        Bytes of a simple PDF document.
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Hello World from page 1")
    page.insert_text((72, 100), "Second paragraph with more text content for testing.")
    result = doc.tobytes()
    doc.close()
    return result


def _create_multi_page_pdf() -> bytes:
    """Create a multi-page PDF with text content for testing.

    Returns:
        Bytes of a multi-page PDF document.
    """
    import pymupdf

    doc = pymupdf.open()
    for i in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), f"Page {i + 1} title")
        for j in range(10):
            page.insert_text(
                (72, 100 + j * 20),
                f"Paragraph {j + 1} on page {i + 1} with some content.",
            )
    result = doc.tobytes()
    doc.close()
    return result


def _create_pdf_with_table() -> bytes:
    """Create a PDF with a table-like structure for testing.

    Returns:
        Bytes of a PDF document with tabular content.
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Financial Summary")

    # Insert a simple table using tab stops
    table_text = (
        "Item\t2022\t2023\nRevenue\t1000\t1200\nProfit\t200\t300\nAssets\t5000\t5500"
    )
    page.insert_text((72, 100), table_text)
    result = doc.tobytes()
    doc.close()
    return result


class TestExtractPdfContent:
    """Tests for extract_pdf_content function."""

    def test_returns_list_of_dicts(self) -> None:
        """extract_pdf_content returns a list of dicts."""
        pdf_bytes = _create_simple_pdf()
        result = extract_pdf_content(pdf_bytes)

        assert isinstance(result, list)
        assert len(result) > 0
        for block in result:
            assert isinstance(block, dict)

    def test_content_blocks_have_required_keys(self) -> None:
        """Each content block has type, text/content, page, and bbox."""
        pdf_bytes = _create_simple_pdf()
        result = extract_pdf_content(pdf_bytes)

        for block in result:
            assert "type" in block
            assert block["type"] in ("text", "table")
            assert "page" in block
            assert isinstance(block["page"], int)
            assert "bbox" in block

    def test_page_numbers_are_one_indexed(self) -> None:
        """Page numbers start from 1 (not 0)."""
        pdf_bytes = _create_simple_pdf()
        result = extract_pdf_content(pdf_bytes)

        pages = {block["page"] for block in result}
        assert min(pages) >= 1

    def test_multi_page_pdf_has_multiple_pages(self) -> None:
        """Multi-page PDF extracts content from all pages."""
        pdf_bytes = _create_multi_page_pdf()
        result = extract_pdf_content(pdf_bytes)

        pages = {block["page"] for block in result}
        assert len(pages) == 5

    def test_invalid_pdf_raises_error(self) -> None:
        """Invalid PDF bytes raise DataValidationError."""
        from stockvaluefinder.utils.errors import DataValidationError

        with pytest.raises(DataValidationError):
            extract_pdf_content(b"not a pdf")

    def test_empty_page_pdf_returns_empty_list(self) -> None:
        """PDF with an empty page (no text) returns empty list."""
        import pymupdf

        doc = pymupdf.open()
        doc.new_page(width=612, height=792)  # Empty page, no text inserted
        pdf_bytes = doc.tobytes()
        doc.close()

        result = extract_pdf_content(pdf_bytes)
        assert isinstance(result, list)


class TestChunkIntoParents:
    """Tests for chunk_into_parents function."""

    def test_returns_list_of_document_chunks(self) -> None:
        """chunk_into_parents returns list of DocumentChunk objects."""
        blocks = [
            {
                "type": "text",
                "content": "Short text.",
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
        ]
        result = chunk_into_parents(blocks)

        assert isinstance(result, list)
        for chunk in result:
            assert isinstance(chunk, DocumentChunk)

    def test_single_small_block_creates_one_chunk(self) -> None:
        """A single small text block produces one parent chunk."""
        blocks = [
            {
                "type": "text",
                "content": "Short text.",
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
        ]
        result = chunk_into_parents(blocks)

        assert len(result) == 1
        assert result[0].metadata.chunk_type == "parent"
        assert result[0].metadata.parent_id is None

    def test_large_blocks_split_into_multiple_parents(self) -> None:
        """Many large text blocks split into multiple parent chunks."""
        # Create multiple blocks that together exceed target_tokens
        blocks = [
            {
                "type": "text",
                "content": " ".join(["word"] * 200),
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
            {
                "type": "text",
                "content": " ".join(["word"] * 200),
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
            {
                "type": "text",
                "content": " ".join(["word"] * 200),
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
        ]
        result = chunk_into_parents(blocks, target_tokens=300)

        assert len(result) > 1

    def test_page_references_preserved(self) -> None:
        """Page numbers from content blocks are preserved in chunks."""
        # Use small target_tokens to force splitting across pages
        blocks = [
            {
                "type": "text",
                "content": " ".join(["page1"] * 200),
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
            {
                "type": "text",
                "content": " ".join(["page2"] * 200),
                "page": 2,
                "bbox": (0, 0, 100, 10),
            },
        ]
        result = chunk_into_parents(blocks, target_tokens=200)

        pages = {chunk.metadata.page_number for chunk in result}
        assert 1 in pages
        assert 2 in pages

    def test_empty_blocks_return_empty_list(self) -> None:
        """Empty input returns empty list."""
        result = chunk_into_parents([])
        assert result == []

    def test_default_target_tokens_is_2000(self) -> None:
        """Default target_tokens is 2000 per function signature."""
        import inspect

        sig = inspect.signature(chunk_into_parents)
        default = sig.parameters["target_tokens"].default
        assert default == 2000


class TestChunkParentsIntoChildren:
    """Tests for chunk_parents_into_children function."""

    def _make_parent(self, content: str, chunk_id: str = "parent-1") -> DocumentChunk:
        """Helper to create a parent DocumentChunk."""
        return DocumentChunk(
            chunk_id=chunk_id,
            content=content,
            metadata=ChunkMetadata(
                document_id="doc-1",
                parent_id=None,
                page_number=1,
                section="",
                ticker="600519.SH",
                year=2023,
                report_type="annual",
                company_name="Test",
                filing_date="2024-01-01",
                chunk_type="parent",
                token_count=0,
            ),
        )

    def test_returns_list_of_document_chunks(self) -> None:
        """chunk_parents_into_children returns list of DocumentChunk."""
        parent = self._make_parent("Short text.")
        result = chunk_parents_into_children([parent])

        assert isinstance(result, list)
        for chunk in result:
            assert isinstance(chunk, DocumentChunk)

    def test_children_reference_parent_id(self) -> None:
        """Child chunks have parent_id set to their parent's chunk_id."""
        parent = self._make_parent("Short text.", chunk_id="parent-abc")
        result = chunk_parents_into_children([parent])

        for child in result:
            assert child.metadata.parent_id == "parent-abc"

    def test_children_have_chunk_type_child(self) -> None:
        """Child chunks have chunk_type='child'."""
        parent = self._make_parent("Some text content for chunking.")
        result = chunk_parents_into_children([parent])

        for child in result:
            assert child.metadata.chunk_type == "child"

    def test_small_parent_creates_single_child(self) -> None:
        """A parent smaller than target_tokens produces one child."""
        parent = self._make_parent("Short text.")
        result = chunk_parents_into_children([parent], target_tokens=500)

        assert len(result) == 1

    def test_large_parent_splits_into_multiple_children(self) -> None:
        """A large parent produces multiple child chunks."""
        # Use paragraph-separated text so the splitter can find boundaries
        paragraphs = [" ".join(["word"] * 100) for _ in range(20)]
        long_text = "\n\n".join(paragraphs)
        parent = self._make_parent(long_text)
        result = chunk_parents_into_children([parent], target_tokens=200)

        assert len(result) > 1

    def test_empty_parents_returns_empty_list(self) -> None:
        """Empty input returns empty list."""
        result = chunk_parents_into_children([])
        assert result == []

    def test_default_target_tokens_is_500(self) -> None:
        """Default target_tokens is 500 per function signature."""
        import inspect

        sig = inspect.signature(chunk_parents_into_children)
        default = sig.parameters["target_tokens"].default
        assert default == 500


class TestDetectTablesAndPreserve:
    """Tests for detect_tables_and_preserve function."""

    def test_returns_list_of_content_blocks(self) -> None:
        """detect_tables_and_preserve returns list of content blocks."""
        text_content = [
            {
                "type": "text",
                "content": "Some text.",
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
        ]
        result = detect_tables_and_preserve(text_content)

        assert isinstance(result, list)

    def test_table_blocks_preserved(self) -> None:
        """Table blocks are preserved as-is (atomic units)."""
        blocks = [
            {
                "type": "table",
                "content": "| a | b |",
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
            {
                "type": "text",
                "content": "Some text.",
                "page": 1,
                "bbox": (0, 0, 100, 10),
            },
        ]
        result = detect_tables_and_preserve(blocks)

        table_blocks = [b for b in result if b.get("type") == "table"]
        assert len(table_blocks) == 1
        assert table_blocks[0]["content"] == "| a | b |"

    def test_text_blocks_pass_through(self) -> None:
        """Text blocks pass through unchanged."""
        blocks = [
            {"type": "text", "content": "Hello.", "page": 1, "bbox": (0, 0, 100, 10)},
        ]
        result = detect_tables_and_preserve(blocks)

        assert len(result) == 1
        assert result[0]["content"] == "Hello."


class TestDocumentChunk:
    """Tests for DocumentChunk and ChunkMetadata dataclasses."""

    def test_document_chunk_is_frozen(self) -> None:
        """DocumentChunk is immutable (frozen)."""
        chunk = DocumentChunk(
            chunk_id="test-1",
            content="test",
            metadata=ChunkMetadata(
                document_id="doc-1",
                parent_id=None,
                page_number=1,
                section="",
                ticker="600519.SH",
                year=2023,
                report_type="annual",
                company_name="Test",
                filing_date="2024-01-01",
                chunk_type="parent",
                token_count=5,
            ),
        )

        with pytest.raises(AttributeError):
            chunk.content = "modified"  # type: ignore[misc]

    def test_chunk_metadata_is_frozen(self) -> None:
        """ChunkMetadata is immutable (frozen)."""
        meta = ChunkMetadata(
            document_id="doc-1",
            parent_id=None,
            page_number=1,
            section="",
            ticker="600519.SH",
            year=2023,
            report_type="annual",
            company_name="Test",
            filing_date="2024-01-01",
            chunk_type="parent",
            token_count=5,
        )

        with pytest.raises(AttributeError):
            meta.page_number = 99  # type: ignore[misc]
