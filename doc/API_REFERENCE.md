# StockValueFinder API Reference

> Generated from commits `2133faa..dec9ecc` covering Phases 13-16 (Auth, Admin, Access Control, Usage Analytics) and updated analysis endpoints.

**Base URL**: `http://localhost:8000`

---

## Table of Contents

- [Authentication](#authentication)
- [Admin - User Management](#admin---user-management)
- [Admin - Stock Access Control](#admin---stock-access-control)
- [Admin - Rate Limit Overrides](#admin---rate-limit-overrides)
- [Admin - Usage Analytics](#admin---usage-analytics)
- [Analysis - Risk](#analysis---risk)
- [Analysis - DCF Valuation](#analysis---dcf-valuation)
- [Analysis - Yield Gap](#analysis---yield-gap)
- [Analysis - ROIC-WACC](#analysis---roic-wacc)
- [Analysis - Capital Allocation](#analysis---capital-allocation)
- [Analysis - Policy Resonance](#analysis---policy-resonance)
- [Analysis - Alpha Composite](#analysis---alpha-composite)
- [Pipeline](#pipeline)
- [Documents](#documents)
- [Common Patterns](#common-patterns)

---

## Authentication

### Register a New User

```
POST /api/v1/auth/register
```

Creates a new user account. The **first** registered user automatically gets the `admin` role; all subsequent users get the `user` role.

**Request Body:**

| Field | Type | Rules | Description |
|-------|------|-------|-------------|
| `email` | string | required, valid email, unique | User email address |
| `password` | string | required, min 8 chars | User password |

```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

**Error responses:**
- `success: false, error: "Email already registered"` — duplicate email
- `success: false, error: "Registration failed. Please try again."` — server error

---

### Login

```
POST /api/v1/auth/login
```

Authenticates a user with email and password, returns a fresh JWT token pair.

**Request Body:**

| Field | Type | Rules | Description |
|-------|------|-------|-------------|
| `email` | string | required | User email address |
| `password` | string | required | User password |

```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

**Error responses:**
- `success: false, error: "Invalid email or password"` — wrong credentials
- HTTP `403` — account disabled by admin

---

### Refresh Token

```
POST /api/v1/auth/refresh
```

Exchanges a valid refresh token for a new access + refresh token pair. The user's active status and current role are re-verified from the database — disabled or deleted users cannot refresh.

**Request Body:**

| Field | Type | Rules | Description |
|-------|------|-------|-------------|
| `refresh_token` | string | required | JWT refresh token |

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):** Same shape as login/register.

**Error responses:**
- `success: false, error: "Refresh token has expired. Please login again."`
- `success: false, error: "Invalid refresh token"`

---

### Logout

```
POST /api/v1/auth/logout
```

JWT is stateless so logout is client-side only. The client should discard both tokens immediately.

**Auth:** Bearer token required.

**Response (200):**

```json
{
  "success": true,
  "data": null
}
```

---

## Admin - User Management

All admin endpoints require `Authorization: Bearer <admin_token>` and will return `403` if the authenticated user is not an admin.

### List All Users

```
GET /api/v1/admin/users?page=1&limit=20
```

Returns a paginated list of all registered users.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (1-based) |
| `limit` | int | 20 | Items per page (max 100) |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "users": [
      {
        "id": "a1b2c3d4-...",
        "email": "admin@example.com",
        "role": "admin",
        "is_active": true,
        "created_at": "2026-05-01T10:00:00Z",
        "updated_at": "2026-05-01T10:00:00Z"
      }
    ],
    "pagination": {
      "total": 15,
      "page": 1,
      "limit": 20
    }
  }
}
```

---

### Get User Detail

```
GET /api/v1/admin/users/{user_id}
```

Returns extended user details including the `deleted_at` timestamp (present only if the user was soft-deleted).

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "a1b2c3d4-...",
    "email": "user@example.com",
    "role": "user",
    "is_active": true,
    "created_at": "2026-05-01T10:00:00Z",
    "updated_at": "2026-05-01T10:00:00Z",
    "deleted_at": null
  }
}
```

**Error:** `404` — User not found.

---

### Enable / Disable User

```
PATCH /api/v1/admin/users/{user_id}/status
```

Sets a user's `is_active` flag. Disabled users cannot login, refresh tokens, or access any protected endpoints.

**Request Body:**

```json
{
  "is_active": false
}
```

**Response (200):** Returns the updated `UserResponse` object (same shape as list item).

---

### Change User Role

```
PATCH /api/v1/admin/users/{user_id}/role
```

Changes a user's role between `admin` and `user`.

**Request Body:**

```json
{
  "role": "admin"
}
```

**Response (200):** Returns the updated `UserResponse` object.

**Error:** `400` — Cannot change your own role.

---

### Soft-Delete User

```
DELETE /api/v1/admin/users/{user_id}
```

Soft-deletes a user by setting `deleted_at` timestamp. The user record is retained but the account is permanently disabled.

**Response (200):** Returns the user data as it was before deletion.

**Errors:**
- `400` — Cannot delete your own account.
- `404` — User not found or already deleted.

---

## Admin - Stock Access Control

Controls which stock tickers each user is allowed to analyze.

**Access logic:**
- **Admins** bypass all stock access checks — they can analyze any ticker.
- **Users with no access entries** (empty list) can access **all** stocks (default open).
- **Users with access entries** can only analyze tickers in their list.

### Get User Stock Access

```
GET /api/v1/admin/users/{user_id}/stock-access
```

Returns the list of stock tickers a user is allowed to analyze.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "user_id": "a1b2c3d4-...",
    "tickers": [
      { "ticker": "600519.SH", "created_at": "2026-05-01T10:00:00Z" },
      { "ticker": "000001.SZ", "created_at": "2026-05-01T10:00:00Z" }
    ]
  }
}
```

---

### Add Stock Access

```
POST /api/v1/admin/users/{user_id}/stock-access
```

Adds a single ticker to a user's access list.

**Request Body:**

```json
{
  "ticker": "600519.SH"
}
```

The ticker must match the pattern `NNNNNN.(SH|SZ|HK)`.

**Response (201):** Returns the full updated stock access list (same shape as GET).

**Error:** `404` — User not found.

---

### Remove Stock Access

```
DELETE /api/v1/admin/users/{user_id}/stock-access
```

Removes a single ticker from a user's access list.

**Request Body:**

```json
{
  "ticker": "600519.SH"
}
```

**Response (200):** Returns the full updated stock access list.

**Error:** `404` — Ticker not found in user's access list.

---

### Replace All Stock Access

```
PUT /api/v1/admin/users/{user_id}/stock-access
```

Replaces the entire access list for a user with the provided tickers.

**Request Body:**

```json
{
  "tickers": ["600519.SH", "000001.SZ", "0700.HK"]
}
```

**Response (200):** Returns the new stock access list.

---

## Admin - Rate Limit Overrides

Per-user rate limit overrides. System defaults are **100 requests per hour**. Admins bypass rate limiting entirely.

### Get User Rate Limit

```
GET /api/v1/admin/users/{user_id}/rate-limit
```

Returns the user's current rate limit. If no override is set, returns system defaults.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "user_id": "a1b2c3d4-...",
    "limit": 100,
    "window_seconds": 3600
  }
}
```

---

### Set User Rate Limit Override

```
PUT /api/v1/admin/users/{user_id}/rate-limit
```

Sets a per-user rate limit override. The override is written to both Redis (for fast lookup) and PostgreSQL (for persistence).

**Request Body:**

```json
{
  "limit": 200,
  "window_seconds": 7200
}
```

| Field | Type | Rules | Description |
|-------|------|-------|-------------|
| `limit` | int | must be > 0 | Maximum requests per window |
| `window_seconds` | int | must be > 0 | Window duration in seconds |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "user_id": "a1b2c3d4-...",
    "limit": 200,
    "window_seconds": 7200
  }
}
```

**Error:** `404` — User not found.

---

### Remove Rate Limit Override

```
DELETE /api/v1/admin/users/{user_id}/rate-limit
```

Removes the per-user override from Redis and DB. The user reverts to system defaults (100/3600).

**Response (200):**

```json
{
  "success": true,
  "data": {
    "message": "Rate limit override removed for user a1b2c3d4-..."
  }
}
```

---

## Admin - Usage Analytics

### Get User Usage Summary

```
GET /api/v1/admin/analytics/users/{user_id}
```

Returns a usage summary for a specific user, including per-endpoint call counts and last activity timestamp. Data is read from Redis (hot data).

**Response (200):**

```json
{
  "success": true,
  "data": {
    "user_id": "a1b2c3d4-...",
    "total_calls": 42,
    "total_errors": 1,
    "last_active": "2026-05-10T14:30:00Z",
    "endpoints": [
      { "endpoint": "/api/v1/analyze/risk", "call_count": 15, "error_count": 0 },
      { "endpoint": "/api/v1/analyze/dcf", "call_count": 27, "error_count": 1 }
    ]
  }
}
```

**Error:** `404` — User not found.

---

### Get Aggregate Statistics

```
GET /api/v1/admin/analytics/aggregate
```

Returns system-wide usage statistics. Queries PostgreSQL for historical data. Returns the top 10 users by usage.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "total_calls": 1234,
    "total_errors": 12,
    "top_users": [
      { "user_id": "a1b2c3d4-...", "email": "user@example.com", "total_calls": 500 }
    ],
    "error_rate": 0.0097
  }
}
```

---

## Analysis - Risk

### Analyze Financial Risk

```
POST /api/v1/analyze/risk
```

Performs comprehensive financial risk analysis including **Beneish M-Score** (8-factor manipulation detection, threshold -1.78), **Piotroski F-Score** (9-point financial strength), and additional red flags (high cash + high debt anomaly, goodwill ratio, profit-cash divergence).

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | yes | Format: `NNNNNN.(SH|SZ|HK)`, e.g. `600519.SH` |
| `year` | int | no | Fiscal year (defaults to most recent available) |
| `document_ids` | string[] | no | Document UUIDs to retrieve RAG context passages |

```json
{
  "ticker": "600519.SH",
  "year": 2024,
  "document_ids": ["doc-uuid-1"]
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "risk_level": "LOW",
    "m_score": -2.54,
    "mscore_data": {
      "DSRI": 1.02, "GMI": 0.98, "AQI": 0.89,
      "SGI": 1.05, "DEPI": 1.01, "SGAI": 0.15,
      "LVGI": 0.95, "TATA": -0.03
    },
    "f_score": 7,
    "fscore_data": {
      "profitability": { "roa": true, "ocf": true, "net_income": true, "ocf_to_net": true },
      "leverage_liquidity": { "debt_lower": true, "current_ratio": true, "no_equity_offer": true },
      "operating_efficiency": { "gross_margin": false, "asset_turnover": true }
    },
    "red_flags": [],
    "narrative": "贵州茅台的M-Score为-2.54，远低于-1.78的阈值..."
  },
  "meta": {
    "document_context": [
      {
        "chunk_id": "chunk-uuid",
        "content": "相关段落内容...",
        "parent_content": "完整父段落...",
        "page_number": 12,
        "section": "管理层讨论与分析",
        "score": 0.89
      }
    ]
  }
}
```

**Error responses:**
- `success: false, error: "..."` — data validation error or external API failure

---

## Analysis - DCF Valuation

### DCF Valuation

```
POST /api/v1/analyze/dcf
```

Performs a **two-stage Discounted Cash Flow** analysis to estimate a stock's intrinsic value. Uses a Gordon Growth terminal value model. WACC is computed with a live 10-year treasury yield hook. Returns a margin of safety calculation and full audit trail.

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ticker` | string | yes | — | Stock ticker |
| `growth_rate_stage1` | float | no | 0.05 | Stage 1 annual growth rate (e.g. 0.08 = 8%) |
| `growth_rate_stage2` | float | no | 0.03 | Stage 2 annual growth rate |
| `years_stage1` | int | no | 5 | Number of years in stage 1 |
| `years_stage2` | int | no | 5 | Number of years in stage 2 |
| `terminal_growth` | float | no | 0.025 | Perpetual growth rate after stage 2 |
| `risk_free_rate` | float | no | live 10Y treasury | Risk-free rate (Rf in WACC = Rf + beta * ERP) |
| `beta` | float | no | config default | Stock beta |
| `market_risk_premium` | float | no | config default | Market risk premium (ERP) |
| `document_ids` | string[] | no | null | Document UUIDs for RAG context |

```json
{
  "ticker": "600519.SH",
  "growth_rate_stage1": 0.08,
  "growth_rate_stage2": 0.04,
  "years_stage1": 5,
  "years_stage2": 5,
  "terminal_growth": 0.025
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "valuation_id": "v1b2c3d4-...",
    "ticker": "600519.SH",
    "stock_name": "贵州茅台",
    "current_price": 1800.00,
    "intrinsic_value": 2150.00,
    "wacc": 0.085,
    "margin_of_safety": 0.16,
    "valuation_level": "UNDERVALUED",
    "dcf_params": {
      "growth_rate_stage1": 0.08,
      "growth_rate_stage2": 0.04,
      "years_stage1": 5,
      "years_stage2": 5,
      "terminal_growth": 0.025,
      "risk_free_rate": 0.028,
      "beta": 0.85,
      "market_risk_premium": 0.07
    },
    "audit_trail": {
      "base_fcf": 55000000000,
      "shares_outstanding": 1256000000,
      "stage1_fcf_list": ["..."],
      "terminal_value": 2500000000000,
      "pv_sum": 2700000000000
    },
    "calculated_at": "2026-05-10T12:00:00Z",
    "narrative": "基于两阶段DCF模型分析..."
  },
  "meta": {
    "document_context": ["... (only present if document_ids provided)"]
  }
}
```

---

### DCF Explanation

```
POST /api/v1/analyze/dcf/explain
```

Generates a human-readable AI explanation for a previously stored DCF valuation result. Fetches the stored result (including full audit trail) by `valuation_id` and uses the LLM to produce a step-by-step breakdown.

**Auth:** Bearer token. Rate limited. Stock access checked (uses ticker from stored result).

**Request Body:**

```json
{
  "valuation_id": "v1b2c3d4-..."
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "valuation_id": "v1b2c3d4-...",
    "ticker": "600519.SH",
    "stock_name": "贵州茅台",
    "current_price": 1800.00,
    "intrinsic_value": 2150.00,
    "valuation_level": "UNDERVALUED",
    "explanation": "第一步：获取贵州茅台的自由现金流..."
  }
}
```

---

## Analysis - Yield Gap

### Yield Gap Analysis

```
POST /api/v1/analyze/yield
```

Calculates the **tax-aware net dividend yield** and compares it against risk-free rates (10-year treasury bond yield and 3-year large deposit rate). For Hong Kong stocks accessed via Stock Connect, applies the 20% withholding tax. Produces a yield gap and a recommendation.

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | yes | Stock ticker |
| `cost_basis` | decimal | yes | Purchase price per share (> 0), used for yield calculation |

```json
{
  "ticker": "0700.HK",
  "cost_basis": 300.00
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "0700.HK",
    "current_price": 350.00,
    "cost_basis": 300.00,
    "gross_dividend_yield": 0.012,
    "net_dividend_yield": 0.0096,
    "risk_free_bond_rate": 0.028,
    "risk_free_deposit_rate": 0.025,
    "yield_gap": -0.0184,
    "recommendation": "UNATTRACTIVE",
    "calculated_at": "2026-05-10T12:00:00Z",
    "narrative": "腾讯控股的税后股息率为0.96%..."
  }
}
```

---

## Analysis - ROIC-WACC

### ROIC-WACC Spread Analysis

```
POST /api/v1/analyze/roic
```

Computes **Return on Invested Capital (ROIC)**, **Weighted Average Cost of Capital (WACC)** with debt weighting, the **ROIC-WACC spread** (positive = economic moat), and a **3-year moat trend** using linear regression. Detects financial sector companies and adjusts NOPAT calculation accordingly.

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | yes | Stock ticker |
| `year` | int | no | Fiscal year |

```json
{
  "ticker": "600519.SH",
  "year": 2024
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "fiscal_year": 2024,
    "roic": 0.25,
    "negative_invested_capital": false,
    "nopat": 5000000000,
    "invested_capital": 20000000000,
    "wacc_breakdown": {
      "ke": 0.09,
      "kd": 0.04,
      "equity_weight": 0.85,
      "debt_weight": 0.15,
      "de_ratio": 0.18,
      "tax_rate": 0.25,
      "wacc": 0.0815
    },
    "spread": 0.1685,
    "spread_classification": "STRONG_MOAT",
    "moat_trend": {
      "trend": "IMPROVING",
      "slope": 0.02,
      "p_value": 0.04,
      "data_points": 3
    },
    "is_financial_sector": false,
    "audit_trail": { "...": "..." },
    "calculated_at": "2026-05-10T12:00:00Z"
  }
}
```

**`spread_classification` values:** `STRONG_MOAT`, `MOAT`, `THIN_MOAT`, `NO_MOAT`, `VALUE_DESTRUCTION`

---

## Analysis - Capital Allocation

### Capital Allocation Scorecard

```
POST /api/v1/analyze/capex
```

Evaluates how well management allocates capital across three equally-weighted dimensions:
1. **Buyback yield** — repurchase amount / market cap (grade A/B/C/D)
2. **Dividend stability** — 5-year DPU trend via linear regression (grade A/B/C/D)
3. **Expansion discipline** — detects blind expansion (ROIC < WACC + CapEx surge) (grade A/B/C/D)

Returns an overall A/B/C/D composite grade.

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | yes | Stock ticker |
| `year` | int | no | Fiscal year (defaults to current year - 1) |

```json
{
  "ticker": "600519.SH",
  "year": 2024
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "fiscal_year": 2024,
    "buyback_yield": {
      "buyback_yield": 0.005,
      "repurchase_amount": 500000000,
      "market_cap": 100000000000,
      "data_quality": "AKSHARE",
      "grade": "B"
    },
    "dividend_stability": {
      "classification": "STABLE",
      "slope": 0.5,
      "p_value": 0.01,
      "data_points": 5,
      "dpu_values": [10.0, 10.5, 11.0, 11.5, 12.0],
      "grade": "A"
    },
    "expansion_discipline": {
      "alert": false,
      "roic_wacc_spread": 0.1685,
      "capex_yoy_growth": 0.05,
      "capex_current": 2000000000,
      "capex_previous": 1900000000,
      "reason": "ROIC > WACC, no blind expansion detected",
      "grade": "A"
    },
    "overall_grade": "A",
    "weighting": { "buyback": null, "dividend": 0.5, "expansion": 0.5 },
    "audit_trail": {
      "buyback_data_source": "AKSHARE",
      "dividend_data_source": "db",
      "roic_data_source": "phase9_db",
      "capex_data_points": 2
    },
    "calculated_at": "2026-05-10T12:00:00Z"
  }
}
```

---

## Analysis - Policy Resonance

### Upload Policy Document

```
POST /api/v1/analyze/policy/upload
```

Uploads a Chinese government policy PDF, processes it through the RAG pipeline (extract, chunk, embed, store in Qdrant `policy_documents` collection), extracts metadata via LLM (title, policy type, issuing body, effective date, industry tags), and persists the record.

**Auth:** Bearer token. Rate limited.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | yes | PDF file only |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "document_id": "d1b2c3d4-...",
    "title": "关于促进白酒产业高质量发展的指导意见",
    "chunk_count": 45,
    "page_count": 12,
    "status": "completed"
  }
}
```

---

### Policy Resonance Analysis

```
POST /api/v1/analyze/policy/resonance
```

Analyzes how government policies relate to a specific stock. Fetches the stock's business description, performs vector similarity search against the `policy_documents` Qdrant collection, verifies each match via LLM, calculates a resonance score (0-100), and produces a DCF terminal growth rate adjustment.

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ticker` | string | yes | — | Stock ticker |
| `terminal_growth` | float | no | 0.025 | Base terminal growth rate for DCF adjustment |

```json
{
  "ticker": "600519.SH",
  "terminal_growth": 0.025
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "resonance_score": 72.5,
    "tier": "supportive",
    "matched_policies": [
      {
        "chunk_content": "鼓励白酒企业提升品牌价值...",
        "chunk_id": "chunk-uuid",
        "document_id": "doc-uuid",
        "score": 0.85,
        "relevant": true,
        "confidence": 0.9,
        "reason": "该政策直接利好白酒行业..."
      }
    ],
    "dcf_adjustment": {
      "tier": "supportive",
      "adjustment_pct": 1.5,
      "adjusted_terminal_growth": 0.0254,
      "original_terminal_growth": 0.025
    },
    "policy_count": 1,
    "analyzed_at": "2026-05-10T12:00:00Z"
  }
}
```

**`tier` values:** `strongly_supportive`, `supportive`, `neutral`

---

## Analysis - Alpha Composite

### Alpha Composite Score

```
POST /api/v1/analyze/alpha
```

Computes a single composite Alpha score by orchestrating live analyses from ROIC, Capital Allocation, and Policy Resonance endpoints. Each dimension is normalized to 0-100 and weighted:

| Dimension | Weight |
|-----------|--------|
| ROIC-WACC spread | 40% |
| Capital allocation | 30% |
| Policy resonance | 20% |
| Moat trend | 10% |

The result is classified into `EXCELLENT` (>=80), `GOOD` (>=60), `FAIR` (>=40), `WEAK` (>=20), or `POOR` (<20).

**Auth:** Bearer token. Rate limited. Stock access checked.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | yes | Stock ticker |
| `year` | int | no | Fiscal year (defaults to current year - 1) |

```json
{
  "ticker": "600519.SH",
  "year": 2024
}
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "fiscal_year": 2024,
    "component_scores": {
      "roic_wacc_score": 85,
      "roic_wacc_raw": 0.1685,
      "capex_score": 75,
      "capex_raw_grade": "A",
      "policy_score": 72.5,
      "policy_raw_score": 72.5,
      "moat_score": 100,
      "moat_raw_trend": "IMPROVING"
    },
    "alpha_score": 79.5,
    "alpha_level": "GOOD",
    "weights_used": {
      "roic_wacc": 0.4,
      "capex": 0.3,
      "policy": 0.2,
      "moat": 0.1
    },
    "dcf_adjustment_summary": {
      "tier": "supportive",
      "adjustment_pct": 1.5,
      "adjusted_terminal_growth": 0.0254,
      "original_terminal_growth": 0.025
    },
    "audit_trail": { "...": "..." },
    "calculated_at": "2026-05-10T12:00:00Z"
  }
}
```

---

## Pipeline

All pipeline endpoints require Bearer token auth.

### Health Check

```
GET /api/v1/pipeline/health
```

Tests connectivity to Redis (via arq pool PING), PostgreSQL (SELECT 1), and reports worker/watcher status.

**Response (200):**

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
    "checked_at": "2026-05-10T12:00:00Z"
  }
}
```

`status` is `"healthy"` when all components are healthy or not yet configured; `"degraded"` if any component is unhealthy.

---

### Pipeline Status

```
GET /api/v1/pipeline/status
```

Returns aggregate task counts across all 6 pipeline states, plus last/next poll times.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "counts": {
      "PENDING": 2,
      "RUNNING": 1,
      "DONE": 15,
      "FAILED": 1,
      "CANCELLED": 0,
      "STALE": 0
    },
    "last_poll_time": "2026-05-10T06:00:00Z",
    "next_poll_time": "2026-05-10T12:00:00Z",
    "total_tasks": 19
  }
}
```

---

### List Tasks

```
GET /api/v1/pipeline/tasks?state=DONE&ticker=600519.SH&page=1&limit=20
```

Returns pipeline tasks ordered by `created_at` descending, with optional filters.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `state` | string | null | Filter: `PENDING`, `RUNNING`, `DONE`, `FAILED`, `CANCELLED`, `STALE` |
| `ticker` | string | null | Filter by stock ticker |
| `created_after` | datetime | null | ISO datetime, inclusive |
| `created_before` | datetime | null | ISO datetime, inclusive |
| `page` | int | 1 | Page number |
| `limit` | int | 20 | Items per page (max 100) |

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "task_id": "t1b2c3d4-...",
      "ticker": "600519.SH",
      "business_key": "600519.SH:2024:annual",
      "state": "DONE",
      "current_stage": "complete",
      "error_message": null,
      "created_at": "2026-05-10T10:00:00Z",
      "updated_at": "2026-05-10T10:05:00Z"
    }
  ],
  "meta": { "total": 1, "page": 1, "limit": 20 }
}
```

---

### Trigger Pipeline

```
POST /api/v1/pipeline/trigger?force=false
```

Manually triggers pipeline processing for a ticker. Auto-adds the ticker to the watchlist if not already present. Deduplicates against already-completed tasks unless `force=true`.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `force` | bool | false | Bypass dedup for completed tasks |

**Request Body:**

```json
{
  "ticker": "600519.SH",
  "fiscal_year": 2024,
  "report_type": "annual"
}
```

**Response (200):**

```json
{
  "success": true,
  "data": { "task_id": "t1b2c3d4-..." }
}
```

---

### Watchlist Add

```
POST /api/v1/pipeline/watchlist
```

```json
{ "ticker": "600519.SH", "name": "贵州茅台" }
```

**Response (200):**

```json
{
  "success": true,
  "data": {
    "ticker": "600519.SH",
    "name": "贵州茅台",
    "added_at": "2026-05-10T12:00:00Z",
    "is_active": true
  }
}
```

**Error:** `400` — Stock already in watchlist.

---

### Watchlist List

```
GET /api/v1/pipeline/watchlist?active_only=true
```

| Param | Type | Default |
|-------|------|---------|
| `active_only` | bool | true |

**Response (200):**

```json
{
  "success": true,
  "data": [
    { "ticker": "600519.SH", "name": "贵州茅台", "added_at": "...", "is_active": true }
  ]
}
```

---

### Watchlist Remove

```
DELETE /api/v1/pipeline/watchlist/{ticker}
```

Soft-removes (sets `is_active=false`). Returns `404` if ticker not found.

**Response (200):**

```json
{ "success": true, "data": null, "meta": { "removed_ticker": "600519.SH" } }
```

---

### SSE Events Stream

```
GET /api/v1/pipeline/events
```

Server-Sent Events endpoint for real-time pipeline task notifications. Max connection duration: 1 hour. Supports reconnect via `Last-Event-ID` header with Redis-based replay.

**Event Types:**

| Event | Description |
|-------|-------------|
| `task_created` | New pipeline task created |
| `task_completed` | Task finished successfully |
| `task_failed` | Task encountered an error |
| `ping` | Keep-alive heartbeat (every 15s) |
| `error` | Redis unavailable |

**Example event:**

```
id: evt-uuid-123
event: task_completed
data: {"id":"evt-uuid-123","type":"task_completed","task_id":"...","ticker":"600519.SH"}
```

---

## Documents

### Upload Document

```
POST /api/v1/documents/upload
```

Uploads a PDF annual report for RAG processing (parse, chunk, embed, store in Qdrant). Returns immediately with `status: "processing"` — the actual processing happens in a background task.

**Auth:** Bearer token.

**Request:** `multipart/form-data`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | file | yes | — | PDF file |
| `ticker` | string | yes | — | Stock ticker (e.g. `600519.SH`) |
| `year` | int | yes | — | Fiscal year |
| `report_type` | string | no | `annual` | Report type |

**Response (200):**

```json
{
  "success": true,
  "data": {
    "document_id": "d1b2c3d4-...",
    "status": "processing",
    "chunk_count": 0,
    "page_count": 0
  }
}
```

---

### Get Document Status

```
GET /api/v1/documents/{document_id}/status
```

Returns the current processing status of an uploaded document.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "document_id": "d1b2c3d4-...",
    "status": "completed",
    "page_count": 120,
    "chunk_count": 85
  }
}
```

`status` values: `pending`, `processing`, `completed`, `failed`

---

### Search Documents

```
POST /api/v1/documents/search
```

Performs semantic search across all indexed documents with optional ticker/year filtering. When `use_multi_query` is enabled, generates query variations for improved recall.

**Auth:** Bearer token.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | yes | — | Natural language search query |
| `ticker` | string | no | null | Filter by stock ticker |
| `year` | int | no | null | Filter by fiscal year |
| `limit` | int | no | 10 | Max results |
| `score_threshold` | float | no | 0.5 | Minimum similarity score |
| `use_multi_query` | bool | no | false | Enable multi-query expansion |

```json
{
  "query": "贵州茅台 营业收入增长",
  "ticker": "600519.SH",
  "year": 2024,
  "limit": 10,
  "score_threshold": 0.5
}
```

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "chunk_id": "chunk-uuid",
      "content": "2024年公司实现营业收入...",
      "parent_content": "完整父段落（约2000 tokens）...",
      "page_number": 12,
      "section": "管理层讨论与分析",
      "score": 0.89,
      "ticker": "600519.SH",
      "year": 2024
    }
  ],
  "meta": { "total": 5 }
}
```

---

### Delete Document

```
DELETE /api/v1/documents/{document_id}
```

Removes all associated chunks from Qdrant and deletes the document metadata record from PostgreSQL.

**Response (200):**

```json
{
  "success": true,
  "data": {
    "document_id": "d1b2c3d4-...",
    "status": "deleted"
  }
}
```

---

## Common Patterns

### Authentication

All protected endpoints require:

```
Authorization: Bearer <access_token>
```

Tokens are JWTs with an expiry. Use `/auth/refresh` to get a new pair before the access token expires.

### Standard Response Envelope

Every API response follows this structure:

```json
{
  "success": true,
  "data": { "..." },
  "error": null,
  "meta": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | `true` on success, `false` on error |
| `data` | T or null | Response payload (present on success) |
| `error` | string or null | Human-readable error message (present on failure) |
| `meta` | object or null | Additional metadata (pagination, RAG context, etc.) |

### HTTP Status Codes

| Code | When |
|------|------|
| `200` | Success |
| `201` | Resource created (stock access add) |
| `400` | Validation error, or self-modify prevention |
| `401` | Missing, invalid, or expired token |
| `403` | Disabled account, non-admin on admin route, or no stock access |
| `404` | User/document/ticker not found |
| `429` | Rate limit exceeded |

### Rate Limiting

- **Default:** 100 requests per hour per user
- **Admins:** bypass all rate limiting
- **Response headers:** `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **On 429:** includes `Retry-After` header with seconds until reset
- **Override:** admin can set per-user limits via `/api/v1/admin/users/{id}/rate-limit`

### Stock Access Control

| User type | Access |
|-----------|--------|
| `admin` | All tickers (no restrictions) |
| `user` with no access entries | All tickers (default open) |
| `user` with access entries | Only the listed tickers |

### Pagination

All list endpoints use the same pattern:

```
GET /endpoint?page=1&limit=20
```

Response includes:
```json
"meta": { "total": 100, "page": 1, "limit": 20 }
```

### Enum Values

| Enum | Values |
|------|--------|
| `UserRole` | `admin`, `user` |
| `RiskLevel` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `ValuationLevel` | `SIGNIFICANTLY_UNDERVALUED`, `UNDERVALUED`, `FAIR_VALUE`, `OVERVALUED`, `SIGNIFICANTLY_OVERVALUED` |
| `YieldRecommendation` | `ATTRACTIVE`, `NEUTRAL`, `UNATTRACTIVE` |
| `Market` | `A_SHARE`, `HK_SHARE` |
| `AlphaLevel` | `EXCELLENT` (>=80), `GOOD` (>=60), `FAIR` (>=40), `WEAK` (>=20), `POOR` (<20) |
| `ResonanceTier` | `strongly_supportive`, `supportive`, `neutral` |
| `CapitalAllocationGrade` | `A`, `B`, `C`, `D` |
| `SpreadClassification` | `STRONG_MOAT`, `MOAT`, `THIN_MOAT`, `NO_MOAT`, `VALUE_DESTRUCTION` |
| `PipelineState` | `PENDING`, `RUNNING`, `DONE`, `FAILED`, `CANCELLED`, `STALE` |
