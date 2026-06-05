"""Unit tests for equity pledge Pydantic models."""

import pytest
from datetime import date, datetime
from decimal import Decimal

from pydantic import ValidationError

from stockvaluefinder.models.enums import DataFreshness
from stockvaluefinder.models.equity_pledge import (
    EquityPledgeDataQuality,
    EquityPledgeDetail,
    EquityPledgeSnapshot,
)


class TestDataFreshnessEnum:
    """Tests for DataFreshness enum."""

    def test_has_exactly_three_members(self) -> None:
        """DataFreshness should have exactly CURRENT, STALE, UNAVAILABLE."""
        members = list(DataFreshness)
        assert len(members) == 3
        assert DataFreshness.CURRENT in members
        assert DataFreshness.STALE in members
        assert DataFreshness.UNAVAILABLE in members

    def test_string_values(self) -> None:
        """Enum values should be uppercase strings."""
        assert DataFreshness.CURRENT.value == "CURRENT"
        assert DataFreshness.STALE.value == "STALE"
        assert DataFreshness.UNAVAILABLE.value == "UNAVAILABLE"


class TestEquityPledgeSnapshot:
    """Tests for EquityPledgeSnapshot model."""

    def _make_quality(self) -> EquityPledgeDataQuality:
        """Create a minimal EquityPledgeDataQuality for tests."""
        return EquityPledgeDataQuality(freshness=DataFreshness.CURRENT)

    def test_create_with_required_fields(self) -> None:
        """Should create with required fields only."""
        quality = self._make_quality()
        snapshot = EquityPledgeSnapshot(
            ticker="600519.SH",
            data_quality=quality,
        )
        assert snapshot.ticker == "600519.SH"
        assert snapshot.data_quality == quality
        assert snapshot.company_pledge_ratio is None
        assert snapshot.pledged_shares is None

    def test_frozen_model_raises_on_mutation(self) -> None:
        """Frozen model should raise ValidationError on field assignment."""
        quality = self._make_quality()
        snapshot = EquityPledgeSnapshot(
            ticker="600519.SH",
            data_quality=quality,
        )
        with pytest.raises(ValidationError):
            snapshot.ticker = "000002.SZ"  # type: ignore[misc]

    def test_zero_pledge_snapshot(self) -> None:
        """Should accept all-zero/None fields for zero-pledge stocks."""
        quality = EquityPledgeDataQuality(
            freshness=DataFreshness.CURRENT,
            warnings=["No pledge data found for ticker"],
        )
        snapshot = EquityPledgeSnapshot(
            ticker="600519.SH",
            latest_date=date(2024, 6, 5),
            company_pledge_ratio=0.0,
            pledged_shares=Decimal("0"),
            pledge_market_value=Decimal("0"),
            pledge_count=0,
            unrestricted_pledged_shares=Decimal("0"),
            restricted_pledged_shares=Decimal("0"),
            one_year_price_change=-5.2,
            industry="白酒",
            data_quality=quality,
        )
        assert snapshot.company_pledge_ratio == 0.0
        assert snapshot.pledge_count == 0

    def test_company_pledge_ratio_stored_as_percentage(self) -> None:
        """Ratio should be stored as percentage (e.g., 35.5 means 35.5%)."""
        quality = self._make_quality()
        snapshot = EquityPledgeSnapshot(
            ticker="600519.SH",
            company_pledge_ratio=35.5,
            data_quality=quality,
        )
        assert snapshot.company_pledge_ratio == 35.5

    def test_has_twelve_fields(self) -> None:
        """Snapshot should have 12 fields including data_quality."""
        quality = self._make_quality()
        snapshot = EquityPledgeSnapshot(
            ticker="600519.SH",
            data_quality=quality,
        )
        expected_fields = {
            "ticker",
            "latest_date",
            "company_pledge_ratio",
            "pledged_shares",
            "pledge_market_value",
            "pledge_count",
            "unrestricted_pledged_shares",
            "restricted_pledged_shares",
            "one_year_price_change",
            "industry",
            "data_quality",
        }
        actual_fields = set(snapshot.model_fields.keys())
        assert expected_fields.issubset(actual_fields)


class TestEquityPledgeDetail:
    """Tests for EquityPledgeDetail model."""

    def test_create_with_required_fields(self) -> None:
        """Should create with required fields only."""
        detail = EquityPledgeDetail(
            ticker="600519.SH",
            holder_name="XX投资集团",
            source="akshare",
        )
        assert detail.ticker == "600519.SH"
        assert detail.holder_name == "XX投资集团"
        assert detail.source == "akshare"
        assert detail.is_controlling_holder is False

    def test_frozen_model_raises_on_mutation(self) -> None:
        """Frozen model should raise ValidationError on field assignment."""
        detail = EquityPledgeDetail(
            ticker="600519.SH",
            holder_name="XX投资集团",
            source="akshare",
        )
        with pytest.raises(ValidationError):
            detail.ticker = "000002.SZ"  # type: ignore[misc]

    def test_all_optional_fields(self) -> None:
        """Should accept all optional fields."""
        detail = EquityPledgeDetail(
            ticker="600519.SH",
            stock_name="贵州茅台",
            holder_name="XX投资集团",
            is_controlling_holder=True,
            pledge_amount=Decimal("1000000"),
            pledged_to_holding_ratio=80.5,
            pledged_to_total_share_ratio=12.3,
            pledgee="中国银行",
            latest_price=1800.0,
            pledge_date_close_price=1750.0,
            estimated_closeout_price=1200.0,
            start_date=date(2024, 1, 15),
            announcement_date=date(2024, 1, 16),
            source="akshare",
        )
        assert detail.is_controlling_holder is True
        assert detail.pledge_amount == Decimal("1000000")
        assert detail.pledged_to_holding_ratio == 80.5
        assert detail.pledgee == "中国银行"

    def test_has_fourteen_fields(self) -> None:
        """Detail should have 14 fields."""
        detail = EquityPledgeDetail(
            ticker="600519.SH",
            holder_name="XX投资集团",
            source="akshare",
        )
        assert len(detail.model_fields) == 14


class TestEquityPledgeDataQuality:
    """Tests for EquityPledgeDataQuality model."""

    def test_create_with_freshness_enum(self) -> None:
        """Should create with freshness enum value."""
        quality = EquityPledgeDataQuality(freshness=DataFreshness.CURRENT)
        assert quality.freshness == DataFreshness.CURRENT
        assert quality.source is None
        assert quality.warnings == []

    def test_defaults_for_optional_fields(self) -> None:
        """Optional fields should default to None or empty list."""
        quality = EquityPledgeDataQuality(freshness=DataFreshness.STALE)
        assert quality.source is None
        assert quality.latest_date is None
        assert quality.fetched_at is None
        assert quality.warnings == []

    def test_with_all_fields(self) -> None:
        """Should accept all fields populated."""
        now = datetime(2024, 6, 5, 12, 0, 0)
        quality = EquityPledgeDataQuality(
            source="akshare",
            latest_date=date(2024, 6, 4),
            fetched_at=now,
            freshness=DataFreshness.CURRENT,
            warnings=["Data may be delayed"],
        )
        assert quality.source == "akshare"
        assert quality.latest_date == date(2024, 6, 4)
        assert quality.fetched_at == now
        assert quality.warnings == ["Data may be delayed"]

    def test_frozen_model(self) -> None:
        """Frozen model should raise on mutation."""
        quality = EquityPledgeDataQuality(freshness=DataFreshness.CURRENT)
        with pytest.raises(ValidationError):
            quality.source = "other"  # type: ignore[misc]
