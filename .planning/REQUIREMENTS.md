# Requirements: StockValueFinder

**Defined:** 2026-05-03
**Core Value:** Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.

## v1.2 Requirements

Requirements for Alpha Engine V2.0 milestone. Each maps to roadmap phases.

### Value Creation (ROIC-WACC)

- [ ] **ROIC-01**: User can calculate ROIC (NOPAT / Invested Capital) from AKShare financial data for any CSI 300 stock
- [ ] **ROIC-02**: User can calculate true WACC (weighted cost of equity + after-tax cost of debt) with debt/equity ratio from balance sheet
- [ ] **ROIC-03**: User can view ROIC-WACC spread with classification (value creating vs destroying)
- [ ] **ROIC-04**: System detects financial sector stocks and applies correct NOPAT formula (OPERATE_PROFIT instead of EBIT-based)
- [ ] **ROIC-05**: System handles edge cases: negative invested capital (cash-rich companies), NaN debt fields (debt-free companies)
- [ ] **ROIC-06**: User can view 3-year ROIC-WACC spread trend with moat detection (widening spread flagged as competitive advantage)

### Capital Allocation

- [ ] **CAPEX-01**: User can view buyback yield (repurchase amount / market cap) from AKShare stock_repurchase_em()
- [ ] **CAPEX-02**: User can view 5-year dividend per unit stability trend with growth/decline/stable classification
- [ ] **CAPEX-03**: System alerts on blind expansion (ROIC < WACC AND CapEx growth exceeding threshold)
- [ ] **CAPEX-04**: User can view capital allocation scorecard combining buyback yield, dividend stability, and expansion discipline

### Policy Resonance

- [ ] **POL-01**: User can upload policy documents (PDF) which are stored in a dedicated Qdrant collection with policy metadata
- [ ] **POL-02**: System matches policy documents to stocks via vector similarity (policy text vs stock business description) with LLM classification to reduce false positives
- [ ] **POL-03**: User can view policy resonance score per stock (0-100) with matched policy excerpts
- [ ] **POL-04**: System auto-adjusts DCF terminal growth rate based on policy resonance (supportive policy -> +1% adjustment)

### Alpha Composite Score

- [ ] **ALPHA-01**: User can view composite Alpha score with fixed weights (40% ROIC-WACC, 30% Capital Allocation, 20% Policy, 10% Moat trend)
- [ ] **ALPHA-02**: User can view all sub-scores and composite via a single API endpoint with full audit trail
- [x] **ALPHA-03**: System persists Alpha analysis results with all component scores and DCF parameter adjustments

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Supply Chain Risk

- **CHAIN-01**: System extracts top-5 customer names from annual report disclosures
- **CHAIN-02**: System monitors customer concentration risk (top-5 > 50% revenue = high dependency)
- **CHAIN-03**: System cross-references customer negative events with supplier stock risk rating

### Advanced Features

- **ADV-01**: Sector-relative ROIC ranking (compare within industry peers)
- **ADV-02**: User-adjustable Alpha weight configuration
- **ADV-03**: Live policy news monitoring (keyword alerts)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Supply chain / customer dependency monitoring | Data quality issues (A-share top-5 client names often hidden), deferred |
| Live policy news crawling | Upload-based RAG matching sufficient for v1.2 |
| User-adjustable Alpha weights | Fixed weights sufficient for MVP |
| Sector-relative ROIC ranking | Requires peer group definitions, deferred |
| HK stock Alpha analysis | CSI 300 only for this milestone |
| Real-time Alpha score updates | On-demand calculation sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ROIC-01 | Phase 9 | Pending |
| ROIC-02 | Phase 9 | Pending |
| ROIC-03 | Phase 9 | Pending |
| ROIC-04 | Phase 9 | Pending |
| ROIC-05 | Phase 9 | Pending |
| ROIC-06 | Phase 9 | Pending |
| CAPEX-01 | Phase 10 | Pending |
| CAPEX-02 | Phase 10 | Pending |
| CAPEX-03 | Phase 10 | Pending |
| CAPEX-04 | Phase 10 | Pending |
| POL-01 | Phase 11 | Pending |
| POL-02 | Phase 11 | Pending |
| POL-03 | Phase 11 | In Progress |
| POL-04 | Phase 11 | In Progress |
| ALPHA-01 | Phase 12 | Pending |
| ALPHA-02 | Phase 12 | Pending |
| ALPHA-03 | Phase 12 | Complete |

**Coverage:**
- v1.2 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-05-03*
*Last updated: 2026-05-03 after v1.2 roadmap creation*
