"""Tests for market scanner Pydantic models and enums.

TDD RED phase: Tests written before implementation.
Covers: ScanStatus/ScanType enums, MarketScanRunCreate, IndexConstituentCreate,
MarketScanRunUpdate, MarketScanCandidateCreate, MarketScanRuleCreate.
"""

import pytest
from pydantic import ValidationError

from stockvaluefinder.models.enums import ScanStatus, ScanType
from stockvaluefinder.models.market_scanner import (
    IndexConstituentCreate,
    IndexConstituentUpdate,
    MarketScanCandidateCreate,
    MarketScanCandidateUpdate,
    MarketScanRuleCreate,
    MarketScanRuleUpdate,
    MarketScanRunCreate,
    MarketScanRunResult,
    MarketScanRunUpdate,
)


class TestScanStatusEnum:
    """Test ScanStatus enum values."""

    def test_has_pending(self) -> None:
        """ScanStatus must have 'pending' value."""
        assert ScanStatus.PENDING == "pending"

    def test_has_running(self) -> None:
        """ScanStatus must have 'running' value."""
        assert ScanStatus.RUNNING == "running"

    def test_has_completed(self) -> None:
        """ScanStatus must have 'completed' value."""
        assert ScanStatus.COMPLETED == "completed"

    def test_has_partial_failed(self) -> None:
        """ScanStatus must have 'partial_failed' value."""
        assert ScanStatus.PARTIAL_FAILED == "partial_failed"

    def test_has_exactly_four_values(self) -> None:
        """ScanStatus must have exactly 4 values."""
        assert len(ScanStatus) == 4


class TestScanTypeEnum:
    """Test ScanType enum values."""

    def test_has_daily(self) -> None:
        """ScanType must have 'daily' value."""
        assert ScanType.DAILY == "daily"

    def test_has_weekly(self) -> None:
        """ScanType must have 'weekly' value."""
        assert ScanType.WEEKLY == "weekly"

    def test_has_exactly_two_values(self) -> None:
        """ScanType must have exactly 2 values."""
        assert len(ScanType) == 2


class TestMarketScanRunCreate:
    """Test MarketScanRunCreate Pydantic model."""

    def test_validates_required_fields(self) -> None:
        """MarketScanRunCreate must validate required fields."""
        from uuid import uuid4

        run = MarketScanRunCreate(
            run_id=uuid4(),
            index_codes=("CSI300",),
            scan_type=ScanType.DAILY,
            rules_version="v1",
        )
        assert run.index_codes == ("CSI300",)
        assert run.scan_type == ScanType.DAILY
        assert run.status == ScanStatus.PENDING

    def test_rejects_missing_index_codes(self) -> None:
        """MarketScanRunCreate must reject missing index_codes."""
        from uuid import uuid4

        with pytest.raises(ValidationError):
            MarketScanRunCreate(
                run_id=uuid4(),
                scan_type=ScanType.DAILY,
                rules_version="v1",
                # index_codes intentionally omitted to test validation
            )  # type: ignore[call-arg]

    def test_rejects_missing_rules_version(self) -> None:
        """MarketScanRunCreate must reject missing rules_version."""
        from uuid import uuid4

        with pytest.raises(ValidationError):
            MarketScanRunCreate(
                run_id=uuid4(),
                index_codes=("CSI300",),
                scan_type=ScanType.DAILY,
                # rules_version intentionally omitted to test validation
            )  # type: ignore[call-arg]


class TestMarketScanRunUpdate:
    """Test MarketScanRunUpdate Pydantic model."""

    def test_allows_partial_update_status_only(self) -> None:
        """MarketScanRunUpdate should allow updating status only."""
        update = MarketScanRunUpdate(status=ScanStatus.RUNNING)
        assert update.status == ScanStatus.RUNNING
        assert update.total_count is None
        assert update.screened_count is None

    def test_allows_partial_update_counts_only(self) -> None:
        """MarketScanRunUpdate should allow updating counts only."""
        update = MarketScanRunUpdate(total_count=300, screened_count=250)
        assert update.total_count == 300
        assert update.screened_count == 250
        assert update.status is None

    def test_allows_empty_update(self) -> None:
        """MarketScanRunUpdate should allow creating with all None."""
        update = MarketScanRunUpdate()
        assert update.status is None
        assert update.total_count is None
        assert update.candidate_count is None


class TestMarketScanRunResult:
    """Test MarketScanRunResult frozen model."""

    def test_frozen_model(self) -> None:
        """MarketScanRunResult must be frozen."""
        from datetime import datetime, timezone
        from uuid import uuid4

        result = MarketScanRunResult(
            run_id=uuid4(),
            index_codes=("CSI300",),
            scan_type=ScanType.DAILY,
            status=ScanStatus.COMPLETED,
            rules_version="v1",
            total_count=300,
            screened_count=250,
            candidate_count=30,
            error_summary=None,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert result.total_count == 300

        with pytest.raises(ValidationError):
            result.total_count = 999  # type: ignore[misc]


class TestIndexConstituentCreate:
    """Test IndexConstituentCreate Pydantic model."""

    def test_validates_valid_ticker(self) -> None:
        """IndexConstituentCreate must accept valid ticker format."""
        from datetime import date
        from uuid import uuid4

        ic = IndexConstituentCreate(
            constituent_id=uuid4(),
            index_code="CSI300",
            ticker="600519.SH",
            name="Kweichow Moutai",
            effective_date=date(2024, 1, 1),
        )
        assert ic.ticker == "600519.SH"

    def test_rejects_invalid_ticker_format(self) -> None:
        """IndexConstituentCreate must reject invalid ticker format."""
        from datetime import date
        from uuid import uuid4

        with pytest.raises(ValidationError):
            IndexConstituentCreate(
                constituent_id=uuid4(),
                index_code="CSI300",
                ticker="INVALID",
                name="Bad Ticker",
                effective_date=date(2024, 1, 1),
            )

    def test_rejects_ticker_without_suffix(self) -> None:
        """IndexConstituentCreate must reject bare 6-digit codes."""
        from datetime import date
        from uuid import uuid4

        with pytest.raises(ValidationError):
            IndexConstituentCreate(
                constituent_id=uuid4(),
                index_code="CSI300",
                ticker="600519",
                name="No Suffix",
                effective_date=date(2024, 1, 1),
            )

    def test_default_is_active_true(self) -> None:
        """IndexConstituentCreate must default is_active to True."""
        from datetime import date
        from uuid import uuid4

        ic = IndexConstituentCreate(
            constituent_id=uuid4(),
            index_code="CSI300",
            ticker="600519.SH",
            name="Kweichow Moutai",
            effective_date=date(2024, 1, 1),
        )
        assert ic.is_active is True

    def test_default_removed_date_none(self) -> None:
        """IndexConstituentCreate must default removed_date to None."""
        from datetime import date
        from uuid import uuid4

        ic = IndexConstituentCreate(
            constituent_id=uuid4(),
            index_code="CSI300",
            ticker="600519.SH",
            name="Kweichow Moutai",
            effective_date=date(2024, 1, 1),
        )
        assert ic.removed_date is None


class TestIndexConstituentUpdate:
    """Test IndexConstituentUpdate Pydantic model."""

    def test_allows_updating_is_active(self) -> None:
        """IndexConstituentUpdate should allow updating is_active."""
        from datetime import date

        update = IndexConstituentUpdate(is_active=False, removed_date=date(2024, 6, 1))
        assert update.is_active is False
        assert update.removed_date == date(2024, 6, 1)

    def test_allows_empty_update(self) -> None:
        """IndexConstituentUpdate should allow creating with all None."""
        update = IndexConstituentUpdate()
        assert update.is_active is None
        assert update.removed_date is None


class TestMarketScanCandidateCreate:
    """Test MarketScanCandidateCreate Pydantic model."""

    def test_validates_required_fields(self) -> None:
        """MarketScanCandidateCreate must validate required fields."""
        from uuid import uuid4

        candidate = MarketScanCandidateCreate(
            candidate_id=uuid4(),
            run_id=uuid4(),
            ticker="600519.SH",
            index_code="CSI300",
            passed=True,
            composite_score=85.5,
            screening_snapshot={"margin_of_safety": 0.45, "risk_level": "LOW"},
        )
        assert candidate.passed is True
        assert candidate.composite_score == pytest.approx(85.5)
        assert candidate.screening_snapshot["margin_of_safety"] == pytest.approx(0.45)


class TestMarketScanCandidateUpdate:
    """Test MarketScanCandidateUpdate Pydantic model."""

    def test_allows_partial_update(self) -> None:
        """MarketScanCandidateUpdate should allow partial updates."""
        update = MarketScanCandidateUpdate(passed=False)
        assert update.passed is False
        assert update.composite_score is None


class TestMarketScanRuleCreate:
    """Test MarketScanRuleCreate Pydantic model."""

    def test_validates_required_fields(self) -> None:
        """MarketScanRuleCreate must validate required fields."""
        from uuid import uuid4

        rule = MarketScanRuleCreate(
            rule_id=uuid4(),
            rule_name="min_margin_of_safety",
            rule_type="valuation",
            is_active=True,
            parameters={"threshold": 0.30},
            priority=1,
        )
        assert rule.rule_name == "min_margin_of_safety"
        assert rule.rule_type == "valuation"
        assert rule.parameters["threshold"] == pytest.approx(0.30)

    def test_default_is_active_true(self) -> None:
        """MarketScanRuleCreate must default is_active to True."""
        from uuid import uuid4

        rule = MarketScanRuleCreate(
            rule_id=uuid4(),
            rule_name="test_rule",
            rule_type="risk",
            parameters={},
        )
        assert rule.is_active is True

    def test_default_priority_zero(self) -> None:
        """MarketScanRuleCreate must default priority to 0."""
        from uuid import uuid4

        rule = MarketScanRuleCreate(
            rule_id=uuid4(),
            rule_name="test_rule",
            rule_type="risk",
            parameters={},
        )
        assert rule.priority == 0


class TestMarketScanRuleUpdate:
    """Test MarketScanRuleUpdate Pydantic model."""

    def test_allows_partial_update(self) -> None:
        """MarketScanRuleUpdate should allow partial updates."""
        update = MarketScanRuleUpdate(is_active=False)
        assert update.is_active is False
        assert update.parameters is None
        assert update.priority is None
