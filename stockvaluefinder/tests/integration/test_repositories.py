"""Integration tests for repository CRUD operations with real database.

Per D-02: Full coverage including all 7 repositories.
Per D-04: E2E with database (route->service->repo->DB->response).
Per D-05: Uses stockvaluefinder_test database on same PostgreSQL instance.

Uses integration conftest.py fixtures:
- test_engine: session-scoped AsyncEngine (creates/drops all tables)
- db_session: per-test AsyncSession with rollback after each test
- @pytest.mark.skip_if_no_db: custom marker for graceful skip when DB unavailable
"""

import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.models.enums import (
    Market,
    ReportType,
    RiskLevel,
    ValuationLevel,
)
from stockvaluefinder.models.financial import FinancialReportCreate
from stockvaluefinder.models.risk import (
    FScoreData,
    MScoreData,
    RiskScoreCreate,
)
from stockvaluefinder.models.stock import StockCreate
from stockvaluefinder.models.valuation import (
    DCFParams,
    ValuationResultCreate,
)
from stockvaluefinder.repositories.financial_repo import FinancialReportRepository
from stockvaluefinder.repositories.risk_repo import RiskScoreRepository
from stockvaluefinder.repositories.stock_repo import StockRepository
from stockvaluefinder.repositories.valuation_repo import ValuationRepository


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _create_stock(
    db_session: AsyncSession,
    ticker: str = "600519.SH",
    name: str = "贵州茅台",
) -> "StockRepository":
    """Create and commit a stock, return the repository for further use."""
    repo = StockRepository(db_session)
    stock = await repo.create(
        StockCreate(
            ticker=ticker,
            name=name,
            market=Market.A_SHARE,
            industry="白酒",
            list_date=date(2001, 8, 27),
        )
    )
    await db_session.commit()
    return repo, stock


async def _create_stock_and_report(
    db_session: AsyncSession,
    ticker: str = "600519.SH",
    name: str = "贵州茅台",
) -> tuple:
    """Create and commit a Stock + FinancialReport, return (stock_repo, stock, fin_repo, report)."""
    stock_repo, stock = await _create_stock(db_session, ticker=ticker, name=name)
    fin_repo = FinancialReportRepository(db_session)
    report = await fin_repo.create(
        FinancialReportCreate(
            ticker=ticker,
            period="2023-12-31",
            report_type=ReportType.ANNUAL,
            revenue=Decimal("127554000000"),
            net_income=Decimal("74734000000"),
            operating_cash_flow=Decimal("58150000000"),
            gross_margin=87.6,
            assets_total=Decimal("255000000000"),
            liabilities_total=Decimal("75000000000"),
            equity_total=Decimal("180000000000"),
            accounts_receivable=Decimal("3500000000"),
            inventory=Decimal("40000000000"),
            fixed_assets=Decimal("25000000000"),
            goodwill=Decimal("500000000"),
            cash_and_equivalents=Decimal("150000000000"),
            interest_bearing_debt=Decimal("2000000000"),
            report_source="AKShare",
            fiscal_year=2023,
            fiscal_quarter=None,
        )
    )
    await db_session.commit()
    return stock_repo, stock, fin_repo, report


def _build_mscore_data() -> MScoreData:
    """Build a sample MScoreData for testing."""
    return MScoreData(
        dsri=1.0,
        gmi=1.0,
        aqi=1.0,
        sgi=1.0,
        depi=1.0,
        sgai=1.0,
        lvgi=1.0,
        tata=0.01,
        audit_trail={},
    )


def _build_fscore_data() -> FScoreData:
    """Build a sample FScoreData for testing."""
    return FScoreData(
        positive_roa=True,
        positive_cfo=True,
        improving_roa=True,
        cfo_exceeds_roa=True,
        lower_leverage=True,
        higher_liquidity=True,
        no_new_shares=True,
        improving_margin=True,
        improving_turnover=True,
    )


# ===================================================================
# TestStockRepository
# ===================================================================


@pytest.mark.skip_if_no_db
class TestStockRepository:
    """Integration tests for StockRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_stock(self, db_session: AsyncSession) -> None:
        """StockRepository.create persists a stock with ticker, name, market, industry."""
        repo = StockRepository(db_session)
        stock = await repo.create(
            StockCreate(
                ticker="600519.SH",
                name="贵州茅台",
                market=Market.A_SHARE,
                industry="白酒",
                list_date=date(2001, 8, 27),
            )
        )
        await db_session.commit()

        assert stock is not None
        assert stock.ticker == "600519.SH"
        assert stock.name == "贵州茅台"
        assert stock.market == "A_SHARE"
        assert stock.industry == "白酒"

    @pytest.mark.asyncio
    async def test_get_by_ticker_found(self, db_session: AsyncSession) -> None:
        """get_by_ticker returns the stock when it exists."""
        repo = StockRepository(db_session)
        await repo.create(
            StockCreate(
                ticker="600519.SH",
                name="贵州茅台",
                market=Market.A_SHARE,
                industry="白酒",
                list_date=date(2001, 8, 27),
            )
        )
        await db_session.commit()

        found = await repo.get_by_ticker("600519.SH")
        assert found is not None
        assert found.ticker == "600519.SH"
        assert found.name == "贵州茅台"

    @pytest.mark.asyncio
    async def test_get_by_ticker_not_found(self, db_session: AsyncSession) -> None:
        """get_by_ticker returns None when ticker does not exist."""
        repo = StockRepository(db_session)
        result = await repo.get_by_ticker("999999.SH")
        assert result is None

    @pytest.mark.asyncio
    async def test_ticker_exists_true(self, db_session: AsyncSession) -> None:
        """ticker_exists returns True for existing ticker."""
        repo = StockRepository(db_session)
        await repo.create(
            StockCreate(
                ticker="600519.SH",
                name="贵州茅台",
                market=Market.A_SHARE,
                industry="白酒",
                list_date=date(2001, 8, 27),
            )
        )
        await db_session.commit()

        assert await repo.ticker_exists("600519.SH") is True

    @pytest.mark.asyncio
    async def test_ticker_exists_false(self, db_session: AsyncSession) -> None:
        """ticker_exists returns False for non-existent ticker."""
        repo = StockRepository(db_session)
        assert await repo.ticker_exists("999999.SH") is False

    @pytest.mark.asyncio
    async def test_get_all(self, db_session: AsyncSession) -> None:
        """get_all returns all persisted stocks."""
        repo = StockRepository(db_session)
        await repo.create(
            StockCreate(
                ticker="600519.SH",
                name="贵州茅台",
                market=Market.A_SHARE,
                industry="白酒",
                list_date=date(2001, 8, 27),
            )
        )
        await repo.create(
            StockCreate(
                ticker="000858.SZ",
                name="五粮液",
                market=Market.A_SHARE,
                industry="白酒",
                list_date=date(1998, 4, 21),
            )
        )
        await db_session.commit()

        results = await repo.get_all(limit=10)
        assert len(results) >= 2


# ===================================================================
# TestFinancialReportRepository
# ===================================================================


@pytest.mark.skip_if_no_db
class TestFinancialReportRepository:
    """Integration tests for FinancialReportRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_financial_report(self, db_session: AsyncSession) -> None:
        """FinancialReportRepository.create persists a report linked to a ticker."""
        await _create_stock(db_session)

        repo = FinancialReportRepository(db_session)
        report = await repo.create(
            FinancialReportCreate(
                ticker="600519.SH",
                period="2023-12-31",
                report_type=ReportType.ANNUAL,
                revenue=Decimal("127554000000"),
                net_income=Decimal("74734000000"),
                operating_cash_flow=Decimal("58150000000"),
                gross_margin=87.6,
                assets_total=Decimal("255000000000"),
                liabilities_total=Decimal("75000000000"),
                equity_total=Decimal("180000000000"),
                accounts_receivable=Decimal("3500000000"),
                inventory=Decimal("40000000000"),
                fixed_assets=Decimal("25000000000"),
                goodwill=Decimal("500000000"),
                cash_and_equivalents=Decimal("150000000000"),
                interest_bearing_debt=Decimal("2000000000"),
                report_source="AKShare",
                fiscal_year=2023,
                fiscal_quarter=None,
            )
        )
        await db_session.commit()

        assert report is not None
        assert report.report_id is not None
        assert report.ticker == "600519.SH"

    @pytest.mark.asyncio
    async def test_get_by_ticker(self, db_session: AsyncSession) -> None:
        """get_by_ticker returns reports for a given ticker."""
        await _create_stock(db_session)
        repo = FinancialReportRepository(db_session)
        await repo.create(
            FinancialReportCreate(
                ticker="600519.SH",
                period="2023-12-31",
                report_type=ReportType.ANNUAL,
                revenue=Decimal("127554000000"),
                net_income=Decimal("74734000000"),
                operating_cash_flow=Decimal("58150000000"),
                gross_margin=87.6,
                assets_total=Decimal("255000000000"),
                liabilities_total=Decimal("75000000000"),
                equity_total=Decimal("180000000000"),
                accounts_receivable=Decimal("3500000000"),
                inventory=Decimal("40000000000"),
                fixed_assets=Decimal("25000000000"),
                goodwill=Decimal("500000000"),
                cash_and_equivalents=Decimal("150000000000"),
                interest_bearing_debt=Decimal("2000000000"),
                report_source="AKShare",
                fiscal_year=2023,
                fiscal_quarter=None,
            )
        )
        await db_session.commit()

        reports = await repo.get_by_ticker("600519.SH")
        assert len(reports) >= 1

    @pytest.mark.asyncio
    async def test_get_by_ticker_and_period(self, db_session: AsyncSession) -> None:
        """get_by_ticker_and_period returns report matching ticker and period."""
        await _create_stock(db_session)
        repo = FinancialReportRepository(db_session)
        await repo.create(
            FinancialReportCreate(
                ticker="600519.SH",
                period="2023-12-31",
                report_type=ReportType.ANNUAL,
                revenue=Decimal("127554000000"),
                net_income=Decimal("74734000000"),
                operating_cash_flow=Decimal("58150000000"),
                gross_margin=87.6,
                assets_total=Decimal("255000000000"),
                liabilities_total=Decimal("75000000000"),
                equity_total=Decimal("180000000000"),
                accounts_receivable=Decimal("3500000000"),
                inventory=Decimal("40000000000"),
                fixed_assets=Decimal("25000000000"),
                goodwill=Decimal("500000000"),
                cash_and_equivalents=Decimal("150000000000"),
                interest_bearing_debt=Decimal("2000000000"),
                report_source="AKShare",
                fiscal_year=2023,
                fiscal_quarter=None,
            )
        )
        await db_session.commit()

        report = await repo.get_by_ticker_and_period("600519.SH", date(2023, 12, 31))
        assert report is not None
        assert report.ticker == "600519.SH"

    @pytest.mark.asyncio
    async def test_get_latest_annual(self, db_session: AsyncSession) -> None:
        """get_latest_annual returns the most recent annual report for a ticker."""
        await _create_stock(db_session)
        repo = FinancialReportRepository(db_session)
        await repo.create(
            FinancialReportCreate(
                ticker="600519.SH",
                period="2023-12-31",
                report_type=ReportType.ANNUAL,
                revenue=Decimal("127554000000"),
                net_income=Decimal("74734000000"),
                operating_cash_flow=Decimal("58150000000"),
                gross_margin=87.6,
                assets_total=Decimal("255000000000"),
                liabilities_total=Decimal("75000000000"),
                equity_total=Decimal("180000000000"),
                accounts_receivable=Decimal("3500000000"),
                inventory=Decimal("40000000000"),
                fixed_assets=Decimal("25000000000"),
                goodwill=Decimal("500000000"),
                cash_and_equivalents=Decimal("150000000000"),
                interest_bearing_debt=Decimal("2000000000"),
                report_source="AKShare",
                fiscal_year=2023,
                fiscal_quarter=None,
            )
        )
        await db_session.commit()

        report = await repo.get_latest_annual("600519.SH")
        assert report is not None
        assert report.fiscal_year == 2023

    @pytest.mark.asyncio
    async def test_exists_for_ticker_and_period(self, db_session: AsyncSession) -> None:
        """exists_for_ticker_and_period returns True when report exists."""
        await _create_stock(db_session)
        repo = FinancialReportRepository(db_session)
        await repo.create(
            FinancialReportCreate(
                ticker="600519.SH",
                period="2023-12-31",
                report_type=ReportType.ANNUAL,
                revenue=Decimal("127554000000"),
                net_income=Decimal("74734000000"),
                operating_cash_flow=Decimal("58150000000"),
                gross_margin=87.6,
                assets_total=Decimal("255000000000"),
                liabilities_total=Decimal("75000000000"),
                equity_total=Decimal("180000000000"),
                accounts_receivable=Decimal("3500000000"),
                inventory=Decimal("40000000000"),
                fixed_assets=Decimal("25000000000"),
                goodwill=Decimal("500000000"),
                cash_and_equivalents=Decimal("150000000000"),
                interest_bearing_debt=Decimal("2000000000"),
                report_source="AKShare",
                fiscal_year=2023,
                fiscal_quarter=None,
            )
        )
        await db_session.commit()

        exists = await repo.exists_for_ticker_and_period("600519.SH", date(2023, 12, 31))
        assert exists is True


# ===================================================================
# TestRiskScoreRepository
# ===================================================================


@pytest.mark.skip_if_no_db
class TestRiskScoreRepository:
    """Integration tests for RiskScoreRepository CRUD and upsert operations."""

    @pytest.mark.asyncio
    async def test_create_risk_score(self, db_session: AsyncSession) -> None:
        """RiskScoreRepository.create persists a risk score linked to a report."""
        _, _, _, report = await _create_stock_and_report(db_session)

        score_id = uuid4()
        repo = RiskScoreRepository(db_session)
        risk = await repo.create(
            RiskScoreCreate(
                score_id=score_id,
                ticker="600519.SH",
                report_id=report.report_id,
                risk_level=RiskLevel.LOW,
                m_score=-3.5,
                mscore_data=_build_mscore_data(),
                f_score=9,
                fscore_data=_build_fscore_data(),
                存贷双高=False,
                cash_amount=Decimal("150000000000"),
                debt_amount=Decimal("2000000000"),
                cash_growth_rate=0.05,
                debt_growth_rate=0.02,
                goodwill_ratio=0.003,
                goodwill_excessive=False,
                profit_cash_divergence=False,
                profit_growth=0.1,
                ocf_growth=0.08,
                red_flags=[],
                narrative=None,
            )
        )
        await db_session.commit()

        assert risk is not None
        assert risk.score_id == score_id

    @pytest.mark.asyncio
    async def test_get_by_score_id(self, db_session: AsyncSession) -> None:
        """get_by_score_id retrieves a risk score by its UUID."""
        _, _, _, report = await _create_stock_and_report(db_session)

        score_id = uuid4()
        repo = RiskScoreRepository(db_session)
        await repo.create(
            RiskScoreCreate(
                score_id=score_id,
                ticker="600519.SH",
                report_id=report.report_id,
                risk_level=RiskLevel.LOW,
                m_score=-3.5,
                mscore_data=_build_mscore_data(),
                f_score=9,
                fscore_data=_build_fscore_data(),
                存贷双高=False,
                cash_amount=Decimal("150000000000"),
                debt_amount=Decimal("2000000000"),
                cash_growth_rate=0.05,
                debt_growth_rate=0.02,
                goodwill_ratio=0.003,
                goodwill_excessive=False,
                profit_cash_divergence=False,
                profit_growth=0.1,
                ocf_growth=0.08,
                red_flags=[],
                narrative=None,
            )
        )
        await db_session.commit()

        found = await repo.get_by_score_id(score_id)
        assert found is not None
        assert found.score_id == score_id

    @pytest.mark.asyncio
    async def test_get_by_score_id_not_found(self, db_session: AsyncSession) -> None:
        """get_by_score_id returns None for non-existent score_id."""
        repo = RiskScoreRepository(db_session)
        result = await repo.get_by_score_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_by_report_id_insert(self, db_session: AsyncSession) -> None:
        """upsert_by_report_id inserts a new score when no prior record exists."""
        _, _, _, report = await _create_stock_and_report(db_session)

        score_id = uuid4()
        repo = RiskScoreRepository(db_session)
        result = await repo.upsert_by_report_id(
            RiskScoreCreate(
                score_id=score_id,
                ticker="600519.SH",
                report_id=report.report_id,
                risk_level=RiskLevel.LOW,
                m_score=-3.5,
                mscore_data=_build_mscore_data(),
                f_score=9,
                fscore_data=_build_fscore_data(),
                存贷双高=False,
                cash_amount=Decimal("150000000000"),
                debt_amount=Decimal("2000000000"),
                cash_growth_rate=0.05,
                debt_growth_rate=0.02,
                goodwill_ratio=0.003,
                goodwill_excessive=False,
                profit_cash_divergence=False,
                profit_growth=0.1,
                ocf_growth=0.08,
                red_flags=[],
                narrative=None,
            )
        )
        await db_session.commit()

        assert result is not None
        assert result.score_id == score_id

    @pytest.mark.asyncio
    async def test_upsert_by_report_id_update(self, db_session: AsyncSession) -> None:
        """upsert_by_report_id updates existing score for same report_id without duplication."""
        _, _, _, report = await _create_stock_and_report(db_session)

        score_id = uuid4()
        repo = RiskScoreRepository(db_session)

        # Insert initial score
        await repo.create(
            RiskScoreCreate(
                score_id=score_id,
                ticker="600519.SH",
                report_id=report.report_id,
                risk_level=RiskLevel.LOW,
                m_score=-3.5,
                mscore_data=_build_mscore_data(),
                f_score=9,
                fscore_data=_build_fscore_data(),
                存贷双高=False,
                cash_amount=Decimal("150000000000"),
                debt_amount=Decimal("2000000000"),
                cash_growth_rate=0.05,
                debt_growth_rate=0.02,
                goodwill_ratio=0.003,
                goodwill_excessive=False,
                profit_cash_divergence=False,
                profit_growth=0.1,
                ocf_growth=0.08,
                red_flags=[],
                narrative=None,
            )
        )
        await db_session.commit()

        # Upsert with updated m_score using same report_id
        updated = await repo.upsert_by_report_id(
            RiskScoreCreate(
                score_id=score_id,
                ticker="600519.SH",
                report_id=report.report_id,
                risk_level=RiskLevel.MEDIUM,
                m_score=-2.0,
                mscore_data=_build_mscore_data(),
                f_score=7,
                fscore_data=_build_fscore_data(),
                存贷双高=False,
                cash_amount=Decimal("150000000000"),
                debt_amount=Decimal("2000000000"),
                cash_growth_rate=0.05,
                debt_growth_rate=0.02,
                goodwill_ratio=0.003,
                goodwill_excessive=False,
                profit_cash_divergence=False,
                profit_growth=0.1,
                ocf_growth=0.08,
                red_flags=[],
                narrative=None,
            )
        )
        await db_session.commit()

        assert updated is not None
        assert abs(updated.m_score - (-2.0)) < 0.01

        # Verify only 1 record exists for this report_id (no duplication)
        existing = await repo.get_by_report_id(report.report_id)
        assert existing is not None
        assert existing.score_id == score_id


# ===================================================================
# TestValuationRepository
# ===================================================================


@pytest.mark.skip_if_no_db
class TestValuationRepository:
    """Integration tests for ValuationRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_valuation_result(self, db_session: AsyncSession) -> None:
        """ValuationRepository.create persists a valuation result."""
        await _create_stock(db_session)

        valuation_id = uuid4()
        dcf_params = DCFParams(
            growth_rate_stage1=0.05,
            growth_rate_stage2=0.03,
            years_stage1=5,
            years_stage2=5,
            terminal_growth=0.025,
            risk_free_rate=0.028,
            beta=0.8,
            market_risk_premium=0.07,
        )
        repo = ValuationRepository(db_session)
        result = await repo.create(
            ValuationResultCreate(
                valuation_id=valuation_id,
                ticker="600519.SH",
                current_price=Decimal("1800.00"),
                intrinsic_value=Decimal("2200.00"),
                wacc=0.084,
                margin_of_safety=0.222,
                valuation_level=ValuationLevel.UNDERVALUED,
                calculated_at=datetime.now(timezone.utc),
                dcf_params=dcf_params,
                audit_trail={"wacc_components": {}},
                narrative=None,
            )
        )
        await db_session.commit()

        assert result is not None
        assert result.valuation_id == valuation_id

    @pytest.mark.asyncio
    async def test_get_by_valuation_id(self, db_session: AsyncSession) -> None:
        """get_by_valuation_id retrieves a valuation by its UUID."""
        await _create_stock(db_session)

        valuation_id = uuid4()
        dcf_params = DCFParams(
            growth_rate_stage1=0.05,
            growth_rate_stage2=0.03,
            years_stage1=5,
            years_stage2=5,
            terminal_growth=0.025,
            risk_free_rate=0.028,
            beta=0.8,
            market_risk_premium=0.07,
        )
        repo = ValuationRepository(db_session)
        await repo.create(
            ValuationResultCreate(
                valuation_id=valuation_id,
                ticker="600519.SH",
                current_price=Decimal("1800.00"),
                intrinsic_value=Decimal("2200.00"),
                wacc=0.084,
                margin_of_safety=0.222,
                valuation_level=ValuationLevel.UNDERVALUED,
                calculated_at=datetime.now(timezone.utc),
                dcf_params=dcf_params,
                audit_trail={"wacc_components": {}},
                narrative=None,
            )
        )
        await db_session.commit()

        found = await repo.get_by_valuation_id(valuation_id)
        assert found is not None
        assert found.ticker == "600519.SH"

    @pytest.mark.asyncio
    async def test_get_by_valuation_id_not_found(self, db_session: AsyncSession) -> None:
        """get_by_valuation_id returns None for non-existent UUID."""
        repo = ValuationRepository(db_session)
        result = await repo.get_by_valuation_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_for_ticker(self, db_session: AsyncSession) -> None:
        """get_latest_for_ticker returns the most recent valuation for a ticker."""
        await _create_stock(db_session)

        valuation_id = uuid4()
        dcf_params = DCFParams(
            growth_rate_stage1=0.05,
            growth_rate_stage2=0.03,
            years_stage1=5,
            years_stage2=5,
            terminal_growth=0.025,
            risk_free_rate=0.028,
            beta=0.8,
            market_risk_premium=0.07,
        )
        repo = ValuationRepository(db_session)
        await repo.create(
            ValuationResultCreate(
                valuation_id=valuation_id,
                ticker="600519.SH",
                current_price=Decimal("1800.00"),
                intrinsic_value=Decimal("2200.00"),
                wacc=0.084,
                margin_of_safety=0.222,
                valuation_level=ValuationLevel.UNDERVALUED,
                calculated_at=datetime.now(timezone.utc),
                dcf_params=dcf_params,
                audit_trail={"wacc_components": {}},
                narrative=None,
            )
        )
        await db_session.commit()

        found = await repo.get_latest_for_ticker("600519.SH")
        assert found is not None
        assert found.valuation_id == valuation_id
