"""Market scanner domain models (Pydantic).

This module defines all Pydantic models for the Market Index Value Scanner,
covering scan runs, index constituents, scan candidates, and scan rules.

Key model groups:
    - MarketScanRun*: Scan run lifecycle (create, update, result)
    - IndexConstituent*: Index membership tracking (create, update)
    - MarketScanCandidate*: Per-stock screening results (create, update)
    - MarketScanRule*: Screening rule definitions (create, update)
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from stockvaluefinder.models.api import PaginationMeta
from stockvaluefinder.models.enums import ScanStatus, ScanType


# ---------------------------------------------------------------------------
# Market Scan Run models
# ---------------------------------------------------------------------------


class MarketScanRunCreate(BaseModel):
    """Model for creating a new market scan run.

    Attributes:
        run_id: Unique identifier for this scan run.
        index_codes: Tuple of index pool identifiers to scan.
        scan_type: Frequency type (daily or weekly).
        status: Current lifecycle status (defaults to PENDING).
        rules_version: Version of screening rules snapshot.
        total_count: Total number of stocks in the scan pool.
        screened_count: Number of stocks that passed coarse screening.
        candidate_count: Number of stocks that passed all screening layers.
        error_summary: JSONB summary of errors encountered during scan.
        started_at: Timestamp when the scan started processing.
        completed_at: Timestamp when the scan finished processing.
    """

    run_id: UUID
    index_codes: tuple[str, ...]
    scan_type: ScanType
    status: ScanStatus = ScanStatus.PENDING
    rules_version: str
    total_count: int = 0
    screened_count: int = 0
    candidate_count: int = 0
    error_summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "run_id": "00000000-0000-0000-0000-000000000001",
                    "index_codes": ["CSI300"],
                    "scan_type": "daily",
                    "rules_version": "v1",
                },
            ]
        }


class MarketScanRunUpdate(BaseModel):
    """Model for updating a market scan run. All fields optional.

    Attributes:
        status: Updated lifecycle status.
        total_count: Updated total stock count.
        screened_count: Updated screened stock count.
        candidate_count: Updated candidate stock count.
        error_summary: Updated error summary.
        started_at: Updated start timestamp.
        completed_at: Updated completion timestamp.
    """

    status: ScanStatus | None = None
    total_count: int | None = None
    screened_count: int | None = None
    candidate_count: int | None = None
    error_summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MarketScanRunResult(BaseModel):
    """Frozen result model for a completed market scan run.

    Attributes:
        run_id: Unique identifier for this scan run.
        index_codes: Tuple of index pool identifiers that were scanned.
        scan_type: Frequency type used for this run.
        status: Final lifecycle status.
        rules_version: Version of screening rules applied.
        total_count: Total number of stocks evaluated.
        screened_count: Number of stocks passing coarse screen.
        candidate_count: Number of final candidates.
        error_summary: JSONB summary of errors (if any).
        started_at: Timestamp when processing began.
        completed_at: Timestamp when processing completed.
        created_at: Record creation timestamp.
        updated_at: Record last-update timestamp.
    """

    model_config = {"frozen": True}

    run_id: UUID
    index_codes: tuple[str, ...]
    scan_type: ScanType
    status: ScanStatus
    rules_version: str
    total_count: int
    screened_count: int
    candidate_count: int
    error_summary: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Index Constituent models
# ---------------------------------------------------------------------------


class IndexConstituentCreate(BaseModel):
    """Model for creating an index constituent record.

    Attributes:
        constituent_id: Unique identifier for this constituent record.
        index_code: Index pool identifier (e.g., CSI300, CSI500).
        ticker: Stock code matching pattern NNNNNN.{SH|SZ}.
        name: Company name in Chinese or English.
        effective_date: Date when this constituent became active in the index.
        is_active: Whether this constituent is currently in the index.
        removed_date: Date when this constituent was removed (None if still active).
    """

    constituent_id: UUID
    index_code: str
    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ)$",
        description="Stock code (e.g., 600519.SH)",
    )
    name: str
    effective_date: date
    is_active: bool = True
    removed_date: date | None = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "constituent_id": "00000000-0000-0000-0000-000000000001",
                    "index_code": "CSI300",
                    "ticker": "600519.SH",
                    "name": "Kweichow Moutai",
                    "effective_date": "2024-01-01",
                },
            ]
        }


class IndexConstituentUpdate(BaseModel):
    """Model for updating an index constituent. All fields optional.

    Attributes:
        is_active: Updated active status.
        removed_date: Updated removal date.
    """

    is_active: bool | None = None
    removed_date: date | None = None


# ---------------------------------------------------------------------------
# Market Scan Candidate models
# ---------------------------------------------------------------------------


class MarketScanCandidateCreate(BaseModel):
    """Model for creating a scan candidate (stock that passed screening).

    Attributes:
        candidate_id: Unique identifier for this candidate record.
        run_id: Foreign key to the scan run that produced this candidate.
        ticker: Stock code matching pattern NNNNNN.{SH|SZ|HK}.
        index_code: Index pool identifier where this stock was found.
        passed: Whether this stock passed all screening layers.
        composite_score: Overall ranking score (0-100).
        screening_snapshot: JSONB snapshot of all screening results.
    """

    candidate_id: UUID
    run_id: UUID
    ticker: str
    index_code: str
    passed: bool
    composite_score: float
    screening_snapshot: dict[str, Any]

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "candidate_id": "00000000-0000-0000-0000-000000000001",
                    "run_id": "00000000-0000-0000-0000-000000000001",
                    "ticker": "600519.SH",
                    "index_code": "CSI300",
                    "passed": True,
                    "composite_score": 85.5,
                    "screening_snapshot": {
                        "margin_of_safety": 0.45,
                        "risk_level": "LOW",
                    },
                },
            ]
        }


class MarketScanCandidateUpdate(BaseModel):
    """Model for updating a scan candidate. All fields optional.

    Attributes:
        passed: Updated pass/fail status.
        composite_score: Updated composite score.
    """

    passed: bool | None = None
    composite_score: float | None = None


# ---------------------------------------------------------------------------
# Market Scan Rule models
# ---------------------------------------------------------------------------


class MarketScanRuleCreate(BaseModel):
    """Model for creating a screening rule definition.

    Attributes:
        rule_id: Unique identifier for this rule.
        rule_name: Human-readable rule name (must be unique).
        rule_type: Rule category (e.g., risk, valuation, yield, composite).
        is_active: Whether this rule is currently active.
        parameters: JSONB rule parameters (thresholds, weights, etc.).
        priority: Execution priority (lower = runs first).
    """

    rule_id: UUID
    rule_name: str
    rule_type: str
    is_active: bool = True
    parameters: dict[str, Any]
    priority: int = 0

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "rule_id": "00000000-0000-0000-0000-000000000001",
                    "rule_name": "min_margin_of_safety",
                    "rule_type": "valuation",
                    "is_active": True,
                    "parameters": {"threshold": 0.30},
                    "priority": 1,
                },
            ]
        }


class MarketScanRuleUpdate(BaseModel):
    """Model for updating a screening rule. All fields optional.

    Attributes:
        is_active: Updated active status.
        parameters: Updated rule parameters.
        priority: Updated execution priority.
    """

    is_active: bool | None = None
    parameters: dict[str, Any] | None = None
    priority: int | None = None


# ---------------------------------------------------------------------------
# API Response Models for Scanner REST Endpoints
# ---------------------------------------------------------------------------


class ScanRunResponse(BaseModel):
    """API response model for a scan run summary.

    Attributes:
        run_id: Unique identifier for this scan run.
        index_codes: List of index pool identifiers that were scanned.
        scan_type: Frequency type used for this run.
        status: Final lifecycle status.
        rules_version: Version of screening rules applied.
        total_count: Total number of stocks evaluated.
        screened_count: Number of stocks passing coarse screen.
        candidate_count: Number of final candidates.
        started_at: Timestamp when processing began.
        completed_at: Timestamp when processing completed.
        created_at: Record creation timestamp.
    """

    model_config = {"frozen": True}

    run_id: UUID
    index_codes: list[str]
    scan_type: str
    status: str
    rules_version: str
    total_count: int
    screened_count: int
    candidate_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class ScanRunListResponse(BaseModel):
    """Paginated list of scan run summaries.

    Attributes:
        runs: List of scan run summaries.
        pagination: Pagination metadata.
    """

    model_config = {"frozen": True}

    runs: list[ScanRunResponse]
    pagination: PaginationMeta


class CandidateListItemResponse(BaseModel):
    """Summary model for candidate in a list view.

    Attributes:
        candidate_id: Unique identifier for this candidate record.
        run_id: Foreign key to the scan run.
        ticker: Stock code.
        index_code: Index pool identifier.
        composite_score: Overall ranking score.
        safety_margin: Margin of safety extracted from screening_snapshot.
        intrinsic_value: Intrinsic value extracted from screening_snapshot.
        risk_level: Risk level extracted from screening_snapshot.
        created_at: Record creation timestamp.
    """

    model_config = {"frozen": True}

    candidate_id: UUID
    run_id: UUID
    ticker: str
    index_code: str
    composite_score: float
    safety_margin: float | None = None
    intrinsic_value: float | None = None
    risk_level: str | None = None
    created_at: datetime


class CandidateListResponse(BaseModel):
    """Paginated list of candidate summaries.

    Attributes:
        candidates: List of candidate summaries.
        pagination: Pagination metadata.
    """

    model_config = {"frozen": True}

    candidates: list[CandidateListItemResponse]
    pagination: PaginationMeta


class CandidateDetailResponse(BaseModel):
    """Full detail model for a single candidate.

    Attributes:
        candidate_id: Unique identifier for this candidate record.
        run_id: Foreign key to the scan run.
        ticker: Stock code.
        index_code: Index pool identifier.
        composite_score: Overall ranking score.
        screening_snapshot: Full JSONB snapshot of all screening results.
        created_at: Record creation timestamp.
    """

    model_config = {"frozen": True}

    candidate_id: UUID
    run_id: UUID
    ticker: str
    index_code: str
    composite_score: float
    screening_snapshot: dict[str, Any]
    created_at: datetime
