"""Unit tests for Document API routes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stockvaluefinder.api.documents_routes import router
from stockvaluefinder.models.document import (
    DocumentSearchRequest,
    DocumentUploadResponse,
)


@pytest.fixture
def app():
    """Create test FastAPI application with document routes."""
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def client(app):
    """Create synchronous test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_document_service():
    """Create mock DocumentService."""
    service = AsyncMock()
    service.process_upload.return_value = DocumentUploadResponse(
        document_id="test-doc-uuid",
        status="completed",
        chunk_count=42,
        page_count=200,
    )
    service.get_document_status.return_value = {
        "status": "completed",
        "page_count": 200,
        "chunk_count": 42,
    }
    service.delete_document.return_value = True
    return service


@pytest.fixture
def mock_retriever():
    """Create mock SemanticRetriever."""
    retriever = AsyncMock()
    retriever.search.return_value = []
    retriever.search_with_multi_query_expansion.return_value = []
    return retriever


class TestDocumentUploadValidation:
    """Tests for document upload validation."""

    def test_upload_rejects_non_pdf_file(self, client):
        """Upload endpoint should reject non-PDF files."""
        response = client.post(
            "/api/v1/documents/upload",
            data={"ticker": "600519.SH", "year": "2023"},
            files={"file": ("test.docx", b"fake content", "application/msword")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert "PDF" in body["error"]

    def test_upload_rejects_missing_filename(self, client):
        """Upload endpoint should reject files without a filename.

        FastAPI returns 422 for invalid form data (empty filename triggers
        python-multipart validation error).
        """
        response = client.post(
            "/api/v1/documents/upload",
            data={"ticker": "600519.SH", "year": "2023"},
            files={"file": ("", b"%PDF-1.4 fake", "application/pdf")},
        )
        # FastAPI returns 422 for form validation errors
        assert response.status_code == 422

    def test_upload_rejects_invalid_ticker_format(self, client):
        """Upload endpoint should reject invalid ticker formats."""
        response = client.post(
            "/api/v1/documents/upload",
            data={"ticker": "INVALID", "year": "2023"},
            files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert "ticker" in body["error"].lower()

    def test_upload_rejects_oversized_file(self, client):
        """Upload endpoint should reject files exceeding size limit."""
        # Patch the MAX_FILE_SIZE_MB to 0 for this test
        with patch("stockvaluefinder.api.documents_routes.rag_config") as mock_config:
            mock_config.MAX_FILE_SIZE_MB = 0
            response = client.post(
                "/api/v1/documents/upload",
                data={"ticker": "600519.SH", "year": "2023"},
                files={
                    "file": (
                        "report.pdf",
                        b"%PDF-1.4 fake content that is too large",
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False


class TestDocumentSearchRequest:
    """Tests for DocumentSearchRequest validation."""

    def test_valid_search_request(self):
        """Valid DocumentSearchRequest should pass validation."""
        request = DocumentSearchRequest(query="test query")
        assert request.query == "test query"
        assert request.ticker is None
        assert request.year is None
        assert request.limit == 10
        assert request.score_threshold == 0.7

    def test_search_request_with_all_fields(self):
        """DocumentSearchRequest with all optional fields."""
        request = DocumentSearchRequest(
            query="revenue",
            ticker="600519.SH",
            year=2023,
            limit=5,
            score_threshold=0.8,
            use_multi_query=False,
        )
        assert request.ticker == "600519.SH"
        assert request.year == 2023
        assert request.limit == 5
        assert request.score_threshold == 0.8
        assert request.use_multi_query is False

    def test_search_request_empty_query_rejected(self):
        """Empty query should be rejected."""
        with pytest.raises(ValueError):
            DocumentSearchRequest(query="")

    def test_search_request_invalid_ticker_rejected(self):
        """Invalid ticker should be rejected."""
        with pytest.raises(ValueError):
            DocumentSearchRequest(query="test", ticker="INVALID")

    def test_search_request_limit_bounds(self):
        """Limit outside bounds should be rejected."""
        with pytest.raises(ValueError):
            DocumentSearchRequest(query="test", limit=0)
        with pytest.raises(ValueError):
            DocumentSearchRequest(query="test", limit=100)


class TestGetDocumentStatus:
    """Tests for GET /{document_id}/status endpoint."""

    def test_status_returns_not_found_for_unknown_document(self, client):
        """Status endpoint should return error for unknown document IDs."""
        with patch(
            "stockvaluefinder.api.documents_routes.DocumentService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.get_document_status = AsyncMock(return_value=None)
            mock_instance.document_repo = AsyncMock()

            with patch(
                "stockvaluefinder.api.documents_routes.get_db",
                return_value=AsyncMock(),
            ):
                response = client.get("/api/v1/documents/nonexistent-id/status")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False


class TestDeleteDocument:
    """Tests for DELETE /{document_id} endpoint."""

    def test_delete_returns_success(self, client):
        """Delete endpoint should return success for existing documents."""
        with patch(
            "stockvaluefinder.api.documents_routes.DocumentService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.delete_document = AsyncMock(return_value=True)
            mock_instance.document_repo = AsyncMock()

            with patch(
                "stockvaluefinder.api.documents_routes.get_db",
                return_value=AsyncMock(),
            ):
                response = client.delete("/api/v1/documents/test-doc-uuid")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_delete_returns_not_found_for_missing(self, client):
        """Delete endpoint should return error for missing documents."""
        with patch(
            "stockvaluefinder.api.documents_routes.DocumentService"
        ) as MockService:
            mock_instance = MockService.return_value
            mock_instance.delete_document = AsyncMock(return_value=False)
            mock_instance.document_repo = AsyncMock()

            with patch(
                "stockvaluefinder.api.documents_routes.get_db",
                return_value=AsyncMock(),
            ):
                response = client.delete("/api/v1/documents/nonexistent-id")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False


class TestSearchDocuments:
    """Tests for POST /search endpoint."""

    def test_search_validates_request_body(self, client):
        """Search endpoint should validate request body."""
        response = client.post(
            "/api/v1/documents/search",
            json={"query": ""},
        )
        assert response.status_code == 422

    def test_search_accepts_valid_request(self, client):
        """Search endpoint should accept valid search request."""
        with patch(
            "stockvaluefinder.api.documents_routes.SemanticRetriever"
        ) as MockRetriever:
            mock_instance = MockRetriever.return_value
            mock_instance.search_with_multi_query_expansion = AsyncMock(return_value=[])

            response = client.post(
                "/api/v1/documents/search",
                json={
                    "query": "贵州茅台2023年营业收入",
                    "ticker": "600519.SH",
                    "year": 2023,
                    "limit": 5,
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
