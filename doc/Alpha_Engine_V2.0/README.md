# API Update Guide for Frontend (since commit 858b3c3)

> **Scope**: All new endpoints added across milestones v1.1 (Pipeline Foundation) and v1.2 (Alpha Engine V2.0).
> **Existing endpoints** (`/api/v1/analyze/risk`, `/api/v1/analyze/dcf`, `/api/v1/analyze/yield`) are **unchanged**.

---

## Table of Contents

1. [Overview of New API Groups](#1-overview-of-new-api-groups)
2. [Pipeline Management APIs](#2-pipeline-management-apis)
3. [ROIC-WACC Spread Analysis API](#3-roic-wacc-spread-analysis-api)
4. [Capital Allocation Scorecard API](#4-capital-allocation-scorecard-api)
5. [Policy Resonance Engine APIs](#5-policy-resonance-engine-apis)
6. [Alpha Composite Score API](#6-alpha-composite-score-api)
7. [Frontend UI Recommendations](#7-frontend-ui-recommendations)

---

## 1. Overview of New API Groups

| # | API Group | Base Path | Purpose | New Endpoints |
|---|-----------|-----------|---------|---------------|
| 1 | Pipeline Management | `/api/v1/pipeline` | Report processing pipeline (download, parse, analyze) | 7 endpoints |
| 2 | ROIC-WACC Spread | `/api/v1/analyze/roic` | Capital efficiency analysis | 1 endpoint |
| 3 | Capital Allocation | `/api/v1/analyze/capex` | Management capital deployment quality | 1 endpoint |
| 4 | Policy Resonance | `/api/v1/analyze/policy` | Government policy alignment analysis | 2 endpoints |
| 5 | Alpha Composite | `/api/v1/analyze/alpha` | Aggregate forward-looking score | 1 endpoint |

---

## 2. Pipeline Management APIs

### What It Does
The pipeline manages the **end-to-end lifecycle** of financial report processing:
1. Download annual/quarterly PDF reports from data sources
2. Parse PDF into structured data
3. Run all analyses (risk, valuation, yield, ROIC, etc.)
4. Stream real-time progress via SSE

### 2.1 Health Check

```
GET /api/v1/pipeline/health
```

**Purpose**: Check if the pipeline subsystem (Redis, PostgreSQL, worker) is operational.

**Response**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "components": {
      "redis": "healthy",
      "postgresql": "healthy",
      "worker": "healthy",
      "watcher": "not_configured"
    },
    "checked_at": "2026-05-07T12:00:00+00:00"
  }
}
```

**Frontend Usage**: Show a pipeline status indicator (green/yellow/red dot) in the header or settings page. Display component breakdown on hover or in a status panel.

---

### 2.2 Watchlist CRUD

#### Add Stock to Watchlist

```
POST /api/v1/pipeline/watchlist
```

**Request Body**:
```json
{
  "ticker": "600519.SH",
  "name": "Kweichow Moutai"
}
```

**Response** (200):
```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "name": "Kweichow Moutai",
    "added_at": "2026-05-07T12:00:00+00:00",
    "is_active": true
  }
}
```

**Error** (400 - already in watchlist):
```json
{
  "success": false,
  "error": "Stock already in watchlist"
}
```

---

#### List Watchlist

```
GET /api/v1/pipeline/watchlist?active_only=true
```

**Query Params**: `active_only` (bool, default `true`)

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "ticker": "600519.SH",
      "name": "Kweichow Moutai",
      "added_at": "2026-05-07T12:00:00+00:00",
      "is_active": true
    },
    {
      "ticker": "000858.SZ",
      "name": "Wuliangye Yibin",
      "added_at": "2026-05-06T10:00:00+00:00",
      "is_active": true
    }
  ]
}
```

---

#### Remove Stock from Watchlist

```
DELETE /api/v1/pipeline/watchlist/{ticker}
```

**Path Param**: `ticker` (e.g., `600519.SH`)

**Response** (200):
```json
{
  "success": true,
  "data": null,
  "meta": { "removed_ticker": "600519.SH" }
}
```

**Error** (404 - not found):
```json
{
  "success": false,
  "error": "Stock not found in watchlist"
}
```

**Frontend Usage**: A "Watchlist" page or sidebar showing monitored stocks with add/remove buttons. Auto-adds when user triggers analysis.

---

### 2.3 Pipeline Status

```
GET /api/v1/pipeline/status
```

**Purpose**: Get aggregate task counts per pipeline state and watcher scheduling info.

**Response**:
```json
{
  "success": true,
  "data": {
    "counts": {
      "PENDING": 2,
      "DOWNLOADING": 1,
      "PARSING": 0,
      "ANALYZING": 0,
      "DONE": 15,
      "FAILED": 1
    },
    "last_poll_time": "2026-05-07T10:00:00+00:00",
    "next_poll_time": "2026-05-07T22:00:00+00:00",
    "total_tasks": 19
  }
}
```

**Frontend Usage**: Dashboard pipeline overview. Show a progress funnel or stacked bar chart of task states. Display last/next poll time for the auto-watcher.

---

### 2.4 List Tasks

```
GET /api/v1/pipeline/tasks?state=DONE&ticker=600519.SH&page=1&limit=20
```

**Query Params**:
| Param | Type | Description |
|-------|------|-------------|
| `state` | string (optional) | Filter by state: PENDING, DOWNLOADING, PARSING, ANALYZING, DONE, FAILED |
| `ticker` | string (optional) | Filter by ticker |
| `created_after` | datetime (optional) | Filter tasks created after |
| `created_before` | datetime (optional) | Filter tasks created before |
| `page` | int (default 1) | Page number |
| `limit` | int (default 20, max 100) | Items per page |

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "ticker": "600519.SH",
      "business_key": "600519.SH:2025:annual",
      "state": "DONE",
      "current_stage": "analysis_complete",
      "error_message": null,
      "created_at": "2026-05-07T10:00:00+00:00",
      "updated_at": "2026-05-07T10:05:00+00:00"
    }
  ],
  "meta": {
    "total": 1,
    "page": 1,
    "limit": 20
  }
}
```

**Frontend Usage**: Task list table with filtering and pagination. Click a task to see its analysis results.

---

### 2.5 Trigger Pipeline

```
POST /api/v1/pipeline/trigger?force=false
```

**Request Body**:
```json
{
  "ticker": "600519.SH",
  "fiscal_year": 2024,
  "report_type": "annual"
}
```

**Query Params**: `force` (bool, default `false`) - bypass dedup for already-completed tasks.

**Response** (200):
```json
{
  "success": true,
  "data": {
    "task_id": "660e8400-e29b-41d4-a716-446655440001"
  }
}
```

**Error** (200 - dedup):
```json
{
  "success": false,
  "error": "Task already completed for 600519.SH:2024:annual. Use force=true to reprocess."
}
```

**Frontend Usage**: "Analyze" button on stock detail page. After trigger, redirect to task status or auto-poll via SSE.

---

### 2.6 SSE Event Stream

```
GET /api/v1/pipeline/events
```

**Purpose**: Real-time streaming of pipeline task lifecycle events via Server-Sent Events.

**Event Types**:
| Event | Data Fields |
|-------|-------------|
| `task_created` | `{ id, type, task_id, ticker, state, timestamp }` |
| `task_completed` | `{ id, type, task_id, ticker, state, timestamp }` |
| `task_failed` | `{ id, type, task_id, ticker, state, error, timestamp }` |
| `ping` | (heartbeat, empty data) |

**Reconnect**: Send `Last-Event-ID` header to replay missed events.

**Frontend Usage**: Use `EventSource` API. Show a toast/notification when tasks complete or fail. Update task list in real-time without polling.

```javascript
const source = new EventSource('/api/v1/pipeline/events');
source.addEventListener('task_completed', (e) => {
  const data = JSON.parse(e.data);
  showNotification(`${data.ticker} analysis complete!`);
});
source.addEventListener('task_failed', (e) => {
  const data = JSON.parse(e.data);
  showError(`${data.ticker} analysis failed: ${data.error}`);
});
```

---

## 3. ROIC-WACC Spread Analysis API

### What It Does
Measures **capital efficiency** by computing:
- **NOPAT** (Net Operating Profit After Tax)
- **Invested Capital** (equity + debt - excess cash)
- **ROIC** (Return on Invested Capital) = NOPAT / Invested Capital
- **WACC** (Weighted Average Cost of Capital) with real debt cost
- **Spread** = ROIC - WACC (positive = value creating)
- **Moat Trend** = 3-year linear regression on spread (improving/stable/deteriorating)

```
POST /api/v1/analyze/roic/
```

**Request Body**:
```json
{
  "ticker": "600519.SH",
  "year": 2024
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "fiscal_year": 2024,
    "roic": 0.245,
    "negative_invested_capital": false,
    "nopat": 74820000000,
    "invested_capital": 305400000000,
    "wacc_breakdown": {
      "ke": 0.095,
      "kd": 0.035,
      "equity_weight": 0.85,
      "debt_weight": 0.15,
      "de_ratio": 0.176,
      "tax_rate": 0.25,
      "wacc": 0.086
    },
    "spread": 0.159,
    "spread_classification": "Value Creating",
    "moat_trend": {
      "trend": "Competitive Advantage",
      "slope": 0.012,
      "p_value": 0.03,
      "data_points": 3
    },
    "is_financial_sector": false,
    "audit_trail": {
      "nopat": { "operating_profit": 95000000000, "tax_rate": 0.25 },
      "invested_capital": { "value": 305400000000, "negative_ic": false },
      "wacc": { "ke": 0.095, "kd": 0.035, "wacc": 0.086 },
      "sector": { "industry": "Food & Beverage", "is_financial": false }
    },
    "calculated_at": "2026-05-07T12:00:00+00:00"
  }
}
```

**Key Fields for Frontend**:

| Field | Type | Display As |
|-------|------|-----------|
| `roic` | decimal | Percentage (e.g., "24.5%") |
| `spread` | decimal | Percentage, color-coded: green > 0, red < 0 |
| `spread_classification` | enum | Badge: "Value Creating" (green), "Value Destroying" (red), "Insufficient Data" (gray) |
| `moat_trend.trend` | enum | Badge: "Competitive Advantage" (green), "Stable" (yellow), "Deteriorating" (red), "Insufficient Data" (gray) |
| `moat_trend.slope` | decimal | Small trend arrow indicator |
| `moat_trend.p_value` | decimal | Show as confidence level if < 0.05 |
| `wacc_breakdown` | object | Expandable accordion with ke, kd, weights, D/E ratio |

**Frontend Usage**: ROIC-WACC card on stock analysis page. Show spread as a big number with trend arrow. Expandable WACC breakdown section.

---

## 4. Capital Allocation Scorecard API

### What It Does
Evaluates **management's capital deployment quality** across three dimensions:
1. **Buyback Yield**: Is the company buying back shares? (repurchase amount / market cap)
2. **Dividend Stability**: Is the dividend per share growing, stable, or declining? (5-year linregress)
3. **Expansion Discipline**: Is the company expanding while ROIC < WACC? (blind expansion detection)

Each dimension gets an A/B/C/D grade, combined into an overall grade.

```
POST /api/v1/analyze/capex/
```

**Request Body**:
```json
{
  "ticker": "600519.SH",
  "year": 2024
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "fiscal_year": 2024,
    "buyback_yield": {
      "buyback_yield": 0.015,
      "repurchase_amount": 5000000000,
      "market_cap": 2000000000000,
      "data_quality": "COMPLETE",
      "grade": "B"
    },
    "dividend_stability": {
      "classification": "Growth",
      "slope": 0.52,
      "p_value": 0.01,
      "data_points": 5,
      "dpu_values": [21.0, 21.5, 22.0, 25.0, 30.0],
      "grade": "A"
    },
    "expansion_discipline": {
      "alert": false,
      "roic_wacc_spread": 0.159,
      "capex_yoy_growth": 0.05,
      "capex_current": 3200000000,
      "capex_previous": 3050000000,
      "reason": "roic_above_wacc",
      "grade": "A"
    },
    "overall_grade": "A",
    "weighting": {
      "buyback": 0.333,
      "dividend": 0.333,
      "expansion": 0.333
    },
    "audit_trail": {
      "buyback_data_source": "COMPLETE",
      "dividend_data_source": "db",
      "roic_data_source": "phase9_db",
      "capex_data_points": 2
    },
    "calculated_at": "2026-05-07T12:00:00+00:00"
  }
}
```

**Key Fields for Frontend**:

| Field | Type | Display As |
|-------|------|-----------|
| `overall_grade` | A/B/C/D | Large letter grade badge (A=green, B=blue, C=yellow, D=red) |
| `buyback_yield.grade` | A/B/C/D | Small badge per dimension |
| `buyback_yield.buyback_yield` | decimal | Percentage (e.g., "1.5%") or "N/A" |
| `dividend_stability.classification` | enum | "Growth" (green), "Stable" (yellow), "Decline" (red) |
| `dividend_stability.dpu_values` | number[] | Mini line chart (sparkline) |
| `expansion_discipline.alert` | bool | Warning icon if true ("Blind Expansion Alert!") |
| `expansion_discipline.capex_yoy_growth` | decimal | Percentage with up/down arrow |
| `weighting` | object | Show as pie chart or stacked bar (actual weights used) |

**Frontend Usage**: Capital Allocation Scorecard section with three sub-cards (Buyback, Dividend, Expansion) and an overall grade badge. Use sparkline chart for DPU trend.

---

## 5. Policy Resonance Engine APIs

### What It Does
Measures **how well a stock aligns with government policy direction**:
1. Upload government policy PDFs (chunked, embedded into Qdrant vector DB)
2. Match stock's business description against policy documents via semantic search
3. LLM verifies each match for relevance
4. Compute resonance score (0-100) and DCF terminal growth adjustment

### 5.1 Upload Policy Document

```
POST /api/v1/analyze/policy/upload
```

**Request**: `multipart/form-data` with file field named `file` (PDF only).

**Response**:
```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "新能源汽车产业发展规划",
    "chunk_count": 42,
    "page_count": 15,
    "status": "completed"
  }
}
```

**Frontend Usage**: File upload drag-and-drop area. Show upload progress, then display document title and chunk count after success.

---

### 5.2 Analyze Policy Resonance

```
POST /api/v1/analyze/policy/resonance
```

**Request Body**:
```json
{
  "ticker": "600519.SH",
  "terminal_growth": 0.025
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "resonance_score": 72.5,
    "tier": "supportive",
    "matched_policies": [
      {
        "chunk_content": "推动食品饮料行业高质量发展...",
        "chunk_id": "chunk_001",
        "document_id": "550e8400-e29b-41d4-a716-446655440000",
        "score": 0.85,
        "relevant": true,
        "confidence": 0.9,
        "reason": "该政策直接提到食品饮料行业高质量发展，与贵州茅台主营业务高度相关"
      }
    ],
    "dcf_adjustment": {
      "tier": "supportive",
      "adjustment_pct": 0.005,
      "adjusted_terminal_growth": 0.03,
      "original_terminal_growth": 0.025
    },
    "policy_count": 3,
    "analyzed_at": "2026-05-07T12:00:00+00:00"
  }
}
```

**Key Fields for Frontend**:

| Field | Type | Display As |
|-------|------|-----------|
| `resonance_score` | float (0-100) | Gauge chart or circular progress bar |
| `tier` | enum | Badge: "strongly_supportive" (green), "supportive" (blue), "neutral" (gray) |
| `matched_policies` | array | List of matched policy excerpts with relevance badges |
| `matched_policies[].score` | float | Similarity percentage bar |
| `matched_policies[].reason` | string | Chinese text explanation from LLM |
| `dcf_adjustment.adjustment_pct` | decimal | "+0.5%" or "-0.5%" badge showing impact on DCF |
| `dcf_adjustment.adjusted_terminal_growth` | decimal | Show vs. original in a comparison |

**Frontend Usage**: Policy Resonance card showing gauge chart for score, list of matched policies with expandable content, and DCF impact summary.

---

## 6. Alpha Composite Score API

### What It Does
Aggregates all four forward-looking analysis dimensions into a **single 0-100 score** with fixed transparent weights:
- ROIC-WACC Spread (40%)
- Capital Allocation (30%)
- Policy Resonance (20%)
- Moat Trend (10%)

This is the **"one number to rule them all"** that users see first.

```
POST /api/v1/analyze/alpha/
```

**Request Body**:
```json
{
  "ticker": "600519.SH",
  "year": 2024
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "fiscal_year": 2024,
    "component_scores": {
      "roic_wacc_score": 85.0,
      "roic_wacc_raw": 0.159,
      "capex_score": 100.0,
      "capex_raw_grade": "A",
      "policy_score": 72.5,
      "policy_raw_score": 72.5,
      "moat_score": 100.0,
      "moat_raw_trend": "Competitive Advantage"
    },
    "alpha_score": 88.25,
    "alpha_level": "EXCELLENT",
    "weights_used": {
      "roic_wacc": 0.4,
      "capex": 0.3,
      "policy": 0.2,
      "moat": 0.1
    },
    "dcf_adjustment_summary": {
      "tier": "supportive",
      "adjustment_pct": 0.005,
      "adjusted_terminal_growth": 0.03,
      "original_terminal_growth": 0.025
    },
    "audit_trail": {
      "roic_fiscal_year": 2024,
      "capex_fiscal_year": 2024,
      "spread": 0.159,
      "moat_trend": "Competitive Advantage",
      "overall_grade": "A",
      "resonance_score": 72.5,
      "normalization": {
        "roic_wacc": "linear_clamp_pm10",
        "capex": "grade_map_ABCD_100_75_50_25",
        "policy": "pass_through",
        "moat": "tier_map_100_50_0"
      }
    },
    "calculated_at": "2026-05-07T12:00:00+00:00"
  }
}
```

**Key Fields for Frontend**:

| Field | Type | Display As |
|-------|------|-----------|
| `alpha_score` | float (0-100) | **Hero number** - large gauge/radial chart |
| `alpha_level` | enum | Color-coded label: EXCELLENT (green), GOOD (blue), FAIR (yellow), WEAK (orange), POOR (red) |
| `component_scores.roic_wacc_score` | float | Bar segment (40% weight) |
| `component_scores.capex_score` | float | Bar segment (30% weight) |
| `component_scores.policy_score` | float | Bar segment (20% weight) |
| `component_scores.moat_score` | float | Bar segment (10% weight) |
| `weights_used` | dict | Show as weighted breakdown chart |
| `dcf_adjustment_summary` | dict | Impact badge on DCF valuation |

**Alpha Level Thresholds**:
| Level | Score Range | Color |
|-------|-------------|-------|
| EXCELLENT | >= 80 | Green |
| GOOD | >= 60 | Blue |
| FAIR | >= 40 | Yellow |
| WEAK | >= 20 | Orange |
| POOR | < 20 | Red |

**Frontend Usage**: This is the **primary score** displayed on the stock analysis page. Show as a large circular gauge at the top, with the four component bars below. The "one glance" summary for the user.

---

## 7. Frontend UI Recommendations

### 7.1 Recommended Page Structure

```
/stocks/{ticker}
  +-- Overview (Alpha Score Hero + basic info)
  +-- Risk Analysis (M-Score, F-Score - existing)
  +-- Valuation (DCF - existing)
  +-- Yield Gap (Dividend vs. Bond - existing)
  +-- Capital Efficiency (ROIC-WACC - NEW)
  +-- Capital Allocation (Scorecard - NEW)
  +-- Policy Resonance (Policy alignment - NEW)

/pipeline
  +-- Dashboard (status, task funnel)
  +-- Watchlist (CRUD list)
  +-- Tasks (filterable table)

/policy-docs
  +-- Upload (drag-and-drop PDF)
  +-- Library (uploaded documents list)
```

### 7.2 Data Flow for Stock Analysis Page

```
User navigates to /stocks/600519.SH
  |
  +-- Call POST /api/v1/analyze/alpha/  (triggers all sub-analyses)
  |     |
  |     +-- Internally calls ROIC, CapEx, Policy endpoints
  |     +-- Returns composite score + all component data
  |
  +-- Render:
       +-- Hero section: Alpha Score gauge (88.25 / EXCELLENT)
       +-- 4 component bars: ROIC-WACC (85), CapEx (100), Policy (72.5), Moat (100)
       +-- Tab panels for detailed views:
            +-- ROIC-WACC: spread chart, WACC breakdown, moat trend
            +-- CapEx: 3 dimension cards (Buyback/Dividend/Expansion)
            +-- Policy: score gauge + matched policy list
```

### 7.3 Real-time Pipeline Updates

```
User clicks "Analyze" button
  |
  +-- POST /api/v1/pipeline/trigger  ->  get task_id
  |
  +-- Open EventSource: /api/v1/pipeline/events
  |     |
  |     +-- Show progress steps: Downloading -> Parsing -> Analyzing -> Done
  |     +-- Toast notification on completion
  |
  +-- On "task_completed" event:
       +-- Navigate to analysis results page
       +-- Or auto-refresh the stock detail view
```

### 7.4 Color and Icon Convention

| Concept | Color | Icon |
|---------|-------|------|
| Value Creating / A Grade / EXCELLENT | Green | TrendingUp |
| Value Neutral / B Grade / GOOD | Blue | Minus |
| Value Destroying / D Grade / POOR | Red | TrendingDown |
| Insufficient Data / NEUTRAL | Gray | HelpCircle |
| Blind Expansion Alert | Red + Warning | AlertTriangle |
| Policy strongly_supportive | Green | Shield |
| Policy supportive | Blue | Shield |
| Policy neutral | Gray | ShieldOff |

### 7.5 Component Score Normalization Reference

For frontend display of raw values alongside normalized 0-100 scores:

| Component | Raw Input | Normalization Method | 0-100 Mapping |
|-----------|-----------|---------------------|---------------|
| ROIC-WACC | spread (decimal) | Linear clamp at +/-10% | 0 at -10%, 100 at +10% |
| CapEx | letter grade (A/B/C/D) | Grade map | A=100, B=75, C=50, D=25 |
| Policy | resonance_score (0-100) | Pass-through | Same as input |
| Moat | trend enum | Tier map | Competitive Advantage=100, Stable=50, others=0 |

---

## Quick Reference: All New Endpoints

| Method | Endpoint | Section |
|--------|----------|---------|
| GET | `/api/v1/pipeline/health` | Pipeline Health |
| GET | `/api/v1/pipeline/status` | Pipeline Status |
| GET | `/api/v1/pipeline/tasks` | List Tasks |
| POST | `/api/v1/pipeline/trigger` | Trigger Pipeline |
| GET | `/api/v1/pipeline/events` | SSE Events |
| POST | `/api/v1/pipeline/watchlist` | Add to Watchlist |
| GET | `/api/v1/pipeline/watchlist` | List Watchlist |
| DELETE | `/api/v1/pipeline/watchlist/{ticker}` | Remove from Watchlist |
| POST | `/api/v1/analyze/roic/` | ROIC-WACC Analysis |
| POST | `/api/v1/analyze/capex/` | Capital Allocation Analysis |
| POST | `/api/v1/analyze/policy/upload` | Upload Policy PDF |
| POST | `/api/v1/analyze/policy/resonance` | Policy Resonance Analysis |
| POST | `/api/v1/analyze/alpha/` | Alpha Composite Score |

All endpoints follow the standard `ApiResponse` envelope:
```json
{
  "success": true | false,
  "data": <T> | null,
  "error": <string> | null,
  "meta": <object> | null
}
```
