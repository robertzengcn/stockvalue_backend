"""Tushare Pro API client with retry logic and error handling."""

import logging
from datetime import date
from typing import Any

import httpx

from stockvaluefinder.utils.errors import ExternalAPIError

logger = logging.getLogger(__name__)


class TushareClient:
    """Async client for Tushare Pro API with retry logic."""

    def __init__(
        self,
        token: str,
        base_url: str = "http://api.tushare.pro",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Tushare client.

        Args:
            token: Tushare Pro API token
            base_url: API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.token = token
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "TushareClient":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, raising error if not initialized."""
        if self._client is None:
            raise ExternalAPIError(
                "HTTP client not initialized. Use async context manager."
            )
        return self._client

    async def _request(
        self,
        api_name: str,
        params: dict[str, Any],
        fields: str | None = None,
    ) -> list[dict[str, Any]]:
        """Make API request with retry logic.

        Args:
            api_name: Tushare API name
            params: API parameters
            fields: Comma-separated list of fields to retrieve

        Returns:
            List of data items from API response

        Raises:
            ExternalAPIError: If all retry attempts fail
        """
        import asyncio

        payload = {
            "api_name": api_name,
            "token": self.token,
            "params": params,
            "fields": fields,
        }

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self.client.post("/", json=payload)
                response.raise_for_status()

                data = response.json()
                if data.get("code") != 0:
                    error_msg = data.get("msg", "Unknown error")
                    raise ExternalAPIError(f"Tushare API error: {error_msg}")

                # Extract data and convert list format to dict format
                data_obj = data.get("data", {})
                items = data_obj.get("items", [])
                field_names = data_obj.get("fields", [])

                # Convert list-based items to dict-based items
                if items and isinstance(items[0], list):
                    if field_names:
                        # Map list values to field names
                        result = [
                            dict(zip(field_names, item))
                            for item in items
                        ]
                    else:
                        # No field names provided, use the requested fields
                        if fields:
                            field_list = fields.split(",")
                            result = [
                                dict(zip(field_list, item))
                                for item in items
                            ]
                        else:
                            # No field information, convert to generic dict
                            result = [{"values": item} for item in items]
                else:
                    # Items are already dicts
                    result = items  # type: ignore[assignment]

                logger.debug(
                    f"Tushare API '{api_name}' returned {len(result)} items (attempt {attempt + 1})"
                )
                return result  # type: ignore[no-any-return]

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Server error, retry with backoff
                    wait_time = 2**attempt
                    logger.warning(
                        f"Tushare API server error (attempt {attempt + 1}), retrying in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Client error, don't retry
                    raise ExternalAPIError(f"Tushare API client error: {e}") from e

            except httpx.RequestError as e:
                last_error = e
                wait_time = 2**attempt
                logger.warning(
                    f"Tushare API request error (attempt {attempt + 1}), retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                last_error = e
                logger.error(f"Tushare API unexpected error: {e}")
                raise ExternalAPIError(f"Tushare API unexpected error: {e}") from e

        # All retries exhausted
        raise ExternalAPIError(
            f"Tushare API failed after {self.max_retries} attempts: {last_error}"
        )

    async def get_stock_basic(
        self,
        ts_code: str | None = None,
        list_status: str = "L",
    ) -> list[dict[str, Any]]:
        """Get stock basic information.

        Args:
            ts_code: Stock code (e.g., '600519.SH')
            list_status: Listing status (L=listed, D=delisted, P=suspended)

        Returns:
            List of stock basic information
        """
        params: dict[str, Any] = {"list_status": list_status}
        if ts_code:
            params["ts_code"] = ts_code

        return await self._request(
            api_name="stock_basic",
            params=params,
            fields="ts_code,symbol,name,area,industry,market,list_date",
        )

    async def get_daily(
        self,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get daily market data.

        Args:
            ts_code: Stock code
            start_date: Start date
            end_date: End date

        Returns:
            List of daily market data
        """
        return await self._request(
            api_name="daily",
            params={
                "ts_code": ts_code,
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
            },
            fields="ts_code,trade_date,open,high,low,close,pre_close,vol,amount",
        )

    async def get_income(
        self,
        ts_code: str,
        period: str,
        report_type: str = "annual",
    ) -> list[dict[str, Any]]:
        """Get income statement data.

        Args:
            ts_code: Stock code
            period: Reporting period (e.g., '20231231')
            report_type: Report type

        Returns:
            List of income statement data
        """
        return await self._request(
            api_name="income",
            params={
                "ts_code": ts_code,
                "period": period,
                "report_type": report_type,
            },
            fields="ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,basic_eps,diluted_eps,total_revenue,revenue,int_oper_income,total_oper_cost,oper_cost,oper_exp,oper_profit,total_profit,n_income,n_income_attr_p",
        )

    async def get_balancesheet(
        self,
        ts_code: str,
        period: str,
    ) -> list[dict[str, Any]]:
        """Get balance sheet data.

        Args:
            ts_code: Stock code
            period: Reporting period (e.g., '20231231')

        Returns:
            List of balance sheet data
        """
        return await self._request(
            api_name="balancesheet",
            params={
                "ts_code": ts_code,
                "period": period,
            },
            fields="ts_code,ann_date,f_ann_date,end_date,total_share,cap_reserve,undistr_profit,surplus_rever,total_assets,total_hldr_eqy_exc_min_int,total_hldr_eqy_inc_min_int",
        )

    async def get_cashflow(
        self,
        ts_code: str,
        period: str,
    ) -> list[dict[str, Any]]:
        """Get cash flow statement data.

        Args:
            ts_code: Stock code
            period: Reporting period (e.g., '20231231')

        Returns:
            List of cash flow data
        """
        return await self._request(
            api_name="cashflow",
            params={
                "ts_code": ts_code,
                "period": period,
            },
            fields="ts_code,ann_date,f_ann_date,end_date,n_cashflow_act,cf_sales_slct,cfrl_sale_sg",
        )

    async def get_dividend(
        self,
        ts_code: str,
    ) -> list[dict[str, Any]]:
        """Get dividend data.

        Args:
            ts_code: Stock code

        Returns:
            List of dividend data
        """
        return await self._request(
            api_name="dividend",
            params={"ts_code": ts_code},
            fields="ts_code,ann_date,div_operate,stk_div,stk_bo_rate,stk_co_rate,record_date,ex_date",
        )
