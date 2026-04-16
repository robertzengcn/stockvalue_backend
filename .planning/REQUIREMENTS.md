# Requirements: StockValueFinder

**Defined:** 2026-04-14
**Core Value:** Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Layer

- [ ] **DATA-01**: Redis caching integrated into all external data routes (24h financials, 5min prices, 1h rates)
- [ ] **DATA-02**: CacheManager wired into data_service, risk_service, valuation_service, and yield_service
- [ ] **DATA-03**: RAG pipeline: PDF upload endpoint that accepts annual report PDFs
- [ ] **DATA-04**: RAG pipeline: PDF processing with chunking (500-token child, 2000-token parent documents)
- [ ] **DATA-05**: RAG pipeline: bge-m3 embedding generation for Chinese financial text
- [ ] **DATA-06**: RAG pipeline: Qdrant vector store integration with metadata filtering (year, industry, ticker)
- [ ] **DATA-07**: RAG pipeline: Semantic retrieval endpoint returning parent-document context with source page references

### Risk Analysis

- [x] **RISK-01**: Beneish M-Score DSRI (Days Sales Receivable Index) calculated from actual balance sheet data
- [x] **RISK-02**: Beneish M-Score GMI (Gross Margin Index) calculated from income statement data
- [x] **RISK-03**: Beneish M-Score AQI (Asset Quality Index) calculated from balance sheet data
- [x] **RISK-04**: Beneish M-Score SGI (Sales Growth Index) calculated from income statement data
- [x] **RISK-05**: Beneish M-Score DEPI (Depreciation Index) calculated from income statement + balance sheet data
- [x] **RISK-06**: Beneish M-Score SGAI (SGA Index) calculated from income statement data
- [x] **RISK-07**: Beneish M-Score LVGI (Leverage Index) calculated from balance sheet data
- [x] **RISK-08**: Beneish M-Score TATA (Total Accruals to Total Assets) calculated from cash flow + balance sheet data
- [x] **RISK-09**: Complete M-Score composite calculation using all 8 real indices with audit trail
- [x] **RISK-10**: Risk API returns calculated M-Score with individual index breakdown and data source references

### Multi-Agent Orchestration

- [ ] **AGENT-01**: LangGraph state machine with coordinator agent managing analysis workflow
- [ ] **AGENT-02**: Risk agent performs M-Score, F-Score, and anomaly detection autonomously
- [ ] **AGENT-03**: Valuation agent performs DCF calculation with parameter extraction autonomously
- [ ] **AGENT-04**: Yield agent performs yield gap analysis with rate fetching autonomously
- [ ] **AGENT-05**: Coordinator agent orchestrates parallel risk/valuation/yield analysis and aggregates results
- [ ] **AGENT-06**: Agent pipeline produces structured analysis output with LLM narrative summary

### Testing and Quality

- [ ] **TEST-01**: Unit tests for risk_service (M-Score calculation, F-Score, anomaly detection) with 80%+ coverage
- [ ] **TEST-02**: Unit tests for valuation_service (DCF, WACC, terminal value) with 80%+ coverage
- [ ] **TEST-03**: Unit tests for yield_service (dividend yield, yield gap, tax calculation) with 80%+ coverage
- [ ] **TEST-04**: Unit tests for data_service (multi-source fallback, data normalization) with 80%+ coverage
- [x] **TEST-05**: Integration tests for API endpoints (risk, valuation, yield) with mocked external services
- [ ] **TEST-06**: Integration tests for database persistence (CRUD operations, migrations)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Risk Analysis

- **RISK-11**: Altman Z-Score bankruptcy detection using existing balance sheet data
- **RISK-12**: DuPont Analysis (ROE decomposition into margin, turnover, leverage)

### Valuation

- **VAL-01**: Graham Number quick intrinsic value calculation
- **VAL-02**: Yield gap historical time-series tracking and chart data endpoint

### Infrastructure

- **INFR-01**: Subprocess-based calculation sandbox with resource limits
- **INFR-02**: Batch CSI 300 screening report generation

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time tick-by-tick prices | Value investors don't need minute-level data; contradicts product philosophy |
| Technical analysis (K-lines, MACD, RSI) | Contradicts value investing approach; explicitly rejected in PRD |
| AI buy/sell/hold recommendations | Regulatory risk in China; product must be auxiliary tool not investment advice |
| Automated trading execution | Massive regulatory overhead and liability |
| Social/community features | Scope creep; moderation cost |
| Multi-market support (US, Japan) | Data source complexity; different accounting standards |
| Chat-based conversational interface | Expensive per-query; hallucination risk; batch reports sufficient for MVP |
| User authentication | Single-user system for MVP; add after product-market fit |
| Frontend application | API-only for this milestone |
| LLM performing financial calculations | Architecture principle: LLMs never touch numbers |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 4 | Pending |
| DATA-04 | Phase 4 | Pending |
| DATA-05 | Phase 4 | Pending |
| DATA-06 | Phase 4 | Pending |
| DATA-07 | Phase 4 | Pending |
| RISK-01 | Phase 1 | Complete |
| RISK-02 | Phase 1 | Complete |
| RISK-03 | Phase 1 | Complete |
| RISK-04 | Phase 1 | Complete |
| RISK-05 | Phase 1 | Complete |
| RISK-06 | Phase 1 | Complete |
| RISK-07 | Phase 1 | Complete |
| RISK-08 | Phase 1 | Complete |
| RISK-09 | Phase 1 | Complete |
| RISK-10 | Phase 1 | Complete |
| AGENT-01 | Phase 5 | Pending |
| AGENT-02 | Phase 5 | Pending |
| AGENT-03 | Phase 5 | Pending |
| AGENT-04 | Phase 5 | Pending |
| AGENT-05 | Phase 5 | Pending |
| AGENT-06 | Phase 6 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 3 | Pending |
| TEST-05 | Phase 3 | Complete |
| TEST-06 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after roadmap creation*
