---
phase: 29-pledge-data-foundation
reviewed: 2026-06-06T03:25:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - stockvaluefinder/stockvaluefinder/models/equity_pledge.py
  - stockvaluefinder/stockvaluefinder/models/enums.py
  - stockvaluefinder/stockvaluefinder/utils/validators.py
  - stockvaluefinder/stockvaluefinder/external/akshare_client.py
  - stockvaluefinder/stockvaluefinder/external/data_service.py
  - stockvaluefinder/tests/unit/test_models/test_equity_pledge.py
  - stockvaluefinder/tests/unit/test_utils/test_validators.py
  - stockvaluefinder/tests/unit/test_external/test_akshare_equity_pledge.py
  - stockvaluefinder/tests/unit/test_external/test_data_service_pledge.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-06-06T03:25:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed 9 files comprising the equity pledge data foundation layer: Pydantic domain models (`equity_pledge.py`, `enums.py`), validators (`validators.py`), AKShare client pledge methods, data service pledge orchestration with caching, and their corresponding test suites. The models and enum are clean. The AKShare client and data service pledge methods are well-structured with proper NaN normalization and freshness classification. However, one critical bug exists: the `_map_pledge_detail_record` method can construct `EquityPledgeDetail` with an empty string for the required `holder_name` field, bypassing the field's semantic intent. Several warnings address unused constants, misleading zero defaults, and a deprecated asyncio API call.

## Critical Issues

### CR-01: Empty-string holder_name bypasses required-field semantic contract

**File:** `stockvaluefinder/stockvaluefinder/external/data_service.py:2213`
**Issue:** The `_map_pledge_detail_record` method passes `str(record.get("股东名称", ""))` to `EquityPledgeDetail.holder_name`, which is declared as `str = Field(...)` (required). If the upstream AKShare record is missing the "股东名称" key or has it set to None, the resulting `holder_name` will be an empty string `""`. This violates the semantic intent of a "required" field -- the caller has no way to distinguish between a valid shareholder name and a missing one. Downstream risk scoring logic that relies on `holder_name` to identify controlling shareholders will silently operate on garbage data.

**Fix:**
```python
# In _map_pledge_detail_record (data_service.py:2213):
holder_name_raw = record.get("股东名称")
if not holder_name_raw or not str(holder_name_raw).strip():
    return None  # or skip this record entirely
holder_name = str(holder_name_raw).strip()
```
And at the call site (line 2365), filter out None returns:
```python
details = []
for record in matching:
    detail = self._map_pledge_detail_record(ticker, record)
    if detail is not None:
        details.append(detail)
return details
```

## Warnings

### WR-01: PLEDGE_RATIO_FIELD_MAP and PLEDGE_DETAIL_FIELD_MAP are unused dead code

**File:** `stockvaluefinder/stockvaluefinder/external/data_service.py:126-153`
**Issue:** These two module-level constants define the Chinese-to-English field mappings, but the actual mapping logic in `_map_pledge_ratio_record` (line 2061) and `_map_pledge_detail_record` (line 2183) hardcodes all Chinese field names inline via `record.get("质押比例")`, `self._normalize_pledge_decimal(record, "质押股数")`, etc. The constants serve no functional purpose. If a field name changes, the constant would be updated by a conscientious developer while the hardcoded references in the mapping methods would be missed, causing a silent mismatch.

**Fix:** Either refactor the mapping methods to iterate over the field map constants, or remove the constants entirely and update the test `TestFieldMapConstants` to test the actual mapping behavior instead.

### WR-02: _build_zero_pledge_snapshot sets misleading one_year_price_change=0.0

**File:** `stockvaluefinder/stockvaluefinder/external/data_service.py:2159`
**Issue:** When a stock has no pledge records, `_build_zero_pledge_snapshot` defaults `one_year_price_change` to `0.0`. A stock with zero pledges almost certainly still has a non-zero price change. Downstream consumers (risk scoring, dashboards) will display "0.0% price change" for these stocks, which is factually incorrect and could mask real volatility risk. The correct value should be `None` (unknown/not applicable for this context).

**Fix:**
```python
# Line 2159: Change from
one_year_price_change=0.0,
# To
one_year_price_change=None,
```

### WR-03: Deprecated asyncio.get_event_loop() in AKShareClient._run_sync

**File:** `stockvaluefinder/stockvaluefinder/external/akshare_client.py:121`
**Issue:** `asyncio.get_event_loop()` has been deprecated since Python 3.10 and emits a DeprecationWarning when called from an async context. The project targets Python 3.12+. The correct replacement is `asyncio.get_running_loop()`.

**Fix:**
```python
# Line 121: Change from
loop = asyncio.get_event_loop()
# To
loop = asyncio.get_running_loop()
```

### WR-04: Naive datetime used for fetched_at timestamp in pledge mapping

**File:** `stockvaluefinder/stockvaluefinder/external/data_service.py:2096`
**Issue:** `_map_pledge_ratio_record` sets `fetched_at=dt.now()` using a timezone-naive datetime. The `_build_zero_pledge_snapshot` method at line 2146 has the same issue. In a production system with multiple servers or timezone-aware consumers, naive datetimes lead to ambiguous timestamps. The rest of the codebase (e.g., `_cache_get_or_set` at line 287) correctly uses `datetime.now(timezone.utc).isoformat()`.

**Fix:**
```python
# Line 2077: Add timezone import
from datetime import datetime as dt, timezone

# Line 2096 and 2146: Change from
fetched_at=dt.now(),
# To
fetched_at=dt.now(timezone.utc),
```

## Info

### IN-01: Redundant inner import of datetime in _map_pledge_ratio_record

**File:** `stockvaluefinder/stockvaluefinder/external/data_service.py:2077`
**Issue:** The method imports `from datetime import datetime as dt` at the top of the function body, but the module already imports `from datetime import date, timedelta` at line 16. This pattern is repeated in `_build_zero_pledge_snapshot` (line 2136) and `_map_pledge_detail_record` (line 2197). While not harmful, it adds unnecessary clutter and inconsistency with the module-level imports.

**Fix:** Move `datetime` to the module-level import: `from datetime import date, datetime, timedelta` and use `datetime` directly in method bodies.

### IN-02: Test asserts broad Exception instead of ValidationError for frozen models

**File:** `stockvaluefinder/tests/unit/test_models/test_equity_pledge.py:59,140,212`
**Issue:** Three tests use `with pytest.raises(Exception)` to verify that frozen models reject mutation. Pydantic raises `ValidationError` for this case, and asserting the specific exception type would catch regressions if the frozen configuration were accidentally removed (a broader Exception catch would still pass even if the model became mutable and raised something else).

**Fix:** Change `with pytest.raises(Exception)` to `with pytest.raises(ValidationError)` and add `from pydantic import ValidationError` to imports.

### IN-03: _map_pledge_detail_record does not set is_controlling_holder

**File:** `stockvaluefinder/stockvaluefinder/external/data_service.py:2210-2232`
**Issue:** The `EquityPledgeDetail` model has an `is_controlling_holder` field that defaults to `False`, but `_map_pledge_detail_record` never populates it from any upstream data. The AKShare detail API does not appear to provide this information. This means all detail records will always have `is_controlling_holder=False`, which could mislead downstream risk scoring into underestimating controlling-shareholder pledge risk. This is not a bug per se (the default is explicit), but it is a gap that should be documented or addressed with a supplementary data source.

**Fix:** Add a comment noting that this field requires supplementary data (e.g., CNInfo controlling shareholder identification) and consider adding a warning to the `data_quality` context when this field is left as default.

---

_Reviewed: 2026-06-06T03:25:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
