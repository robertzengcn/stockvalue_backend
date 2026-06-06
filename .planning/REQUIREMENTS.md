# Requirements: StockValueFinder

**Defined:** 2026-06-05
**Core Value:** Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value

## v1 Requirements

### Data Fetching (DATA)

- [ ] **DATA-01**: System can fetch A-share equity pledge ratio data via AKShare stock_gpzy_pledge_ratio_em for a given trade date, returning company pledge ratio, pledged shares, market value, pledge count, unrestricted/restricted breakdown, and 1-year price change
- [ ] **DATA-02**: System can fetch important shareholder pledge details via AKShare stock_gpzy_pledge_ratio_detail_em, returning holder name, pledge amounts, ratios, pledgee, closeout price, and dates
- [x] **DATA-03**: System normalizes 6-digit AKShare stock codes to internal ticker format (600519.SH, 000002.SZ)
- [ ] **DATA-04**: System caches pledge ratio data in Redis with 24h TTL keyed by trade date, avoiding per-stock real-time bulk fetch
- [ ] **DATA-05**: System caches pledge detail data in Redis with 24h TTL keyed by latest
- [ ] **DATA-06**: System auto-finds the latest available trade date by trying last 10 calendar days in reverse order when no date is specified
- [ ] **DATA-07**: System uses Tushare pledge_detail as optional fallback for shareholder details when AKShare data is unavailable

### Risk Calculation (RISK)

- [x] **RISK-01**: System determines company overall pledge risk level (LOW/MEDIUM/HIGH) based on company pledge ratio thresholds (<10% LOW, 10-20% LOW with note, 20-30% MEDIUM, >30% HIGH)
- [x] **RISK-02**: System determines controlling shareholder pledge risk level based on holder pledge ratio thresholds (<30% LOW, 30-50% LOW with note, 50-80% MEDIUM, >80% HIGH)
- [x] **RISK-03**: System calculates closeout safety margin as (latest_price - estimated_closeout_price) / estimated_closeout_price * 100, and determines risk level (>50% LOW, 30-50% LOW with note, 20-30% MEDIUM, <20% HIGH)
- [ ] **RISK-04**: System applies combination upgrade rules: company pledge >30% + 1yr drop >30% -> at least HIGH, holder pledge >80% -> at least HIGH, closeout margin <20% -> at least HIGH, company pledge >20% + financial HIGH -> final at least HIGH, company pledge >20% + 存贷双高 -> final at least HIGH
- [ ] **RISK-05**: System merges financial risk level and pledge risk level into final risk level, where pledge risk can only upgrade (never downgrade) the financial risk level
- [ ] **RISK-06**: System generates structured red flags explaining each triggered risk condition with specific data values
- [x] **RISK-07**: System classifies data freshness as CURRENT (data within 10 calendar days), STALE (older), or UNAVAILABLE (no data)
- [x] **RISK-08**: System identifies controlling shareholder or largest holder by taking the holder with highest pledged_to_holding_ratio among top holders
- [x] **RISK-09**: System returns supported=false for HK tickers, returning pledge risk as unavailable with appropriate warning

### Persistence (DB)

- [ ] **DB-01**: System persists company pledge snapshots in equity_pledge_snapshots table with unique constraint on (ticker, latest_date, source)
- [ ] **DB-02**: System persists important shareholder pledge details in equity_pledge_details table with indexes on (ticker, announcement_date) and (ticker, holder_name)
- [ ] **DB-03**: System extends risk_scores table with pledge_risk JSONB and risk_level_breakdown JSONB columns, both nullable
- [ ] **DB-04**: System preserves raw API response payload in source_raw JSONB field for audit traceability
- [ ] **DB-05**: System uses upsert for snapshots and replace-all for details per ticker (since AKShare details lack stable unique IDs)
- [ ] **DB-06**: Alembic migration 021 creates new tables and extends risk_scores without modifying existing data

### API Integration (API)

- [ ] **API-01**: User can request risk analysis with include_pledge_risk=true (default) to receive pledge risk data in the response
- [ ] **API-02**: Risk API response includes pledge_risk object with risk_level, company_pledge_ratio, controlling_holder_pledge_ratio, closeout_safety_margin, red_flags, and data_quality fields
- [ ] **API-03**: Risk API response includes risk_level_breakdown showing financial_risk_level, pledge_risk_level, final_risk_level, and merge_reason when pledge risk upgrades the overall level
- [ ] **API-04**: When pledge data fetch fails, the risk API still returns complete financial risk results (M-Score, F-Score) with pledge_risk showing data_quality.freshness=UNAVAILABLE and appropriate warning
- [ ] **API-05**: HK stock requests return pledge_risk.supported=false without error, while financial risk analysis proceeds normally

### Narrative (NARR)

- [ ] **NARR-01**: Risk narrative includes equity pledge paragraph describing risk level, key ratios, and risk factors when pledge data is available
- [ ] **NARR-02**: Narrative prompt explicitly forbids generating pledge numbers not present in structured pledge_risk fields
- [ ] **NARR-03**: When data is unavailable, narrative only states "pledge data unavailable" and does not imply low risk
- [ ] **NARR-04**: When closeout_safety_margin is null, narrative does not mention closeout distance

## v2 Requirements

### Trends & Industry Comparison

- **TREND-01**: System tracks 3/6/12 month pledge ratio change trend
- **TREND-02**: System calculates industry pledge ratio percentile ranking
- **TREND-03**: System shows pledge new/release/expiry trend over time

### Event-Driven Alerts

- **EVNT-01**: System identifies supplementary pledge, release, forced sale, judicial freeze events from announcements/RAG
- **EVNT-02**: System triggers pledge risk change alerts in watchlist
- **EVNT-03**: System incorporates pledge events into market scanner candidate risk penalty

## Out of Scope

| Feature | Reason |
|---------|--------|
| HK stock pledge data | No reliable free data source; HK tickers return supported=false in V1 |
| Intraday real-time pledge alerts | Post-market close data is sufficient for value investing |
| User-adjustable risk thresholds | Fixed thresholds from PRD sufficient for V1 |
| Peer group relative pledge ranking | Requires industry peer definitions, deferred to v2 |
| Consistent actor (一致行动人) consolidation | Complex shareholder relationship data not available in V1; use highest-ratio holder approximation |
| M-Score/F-Score formula modification | Pledge risk is independent dimension, must not change existing financial risk calculations |
| Predictive pledge risk modeling | V1 is descriptive only, based on current data and thresholds |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 29 | Pending |
| DATA-02 | Phase 29 | Pending |
| DATA-03 | Phase 29 | Complete |
| DATA-04 | Phase 29 | Pending |
| DATA-05 | Phase 29 | Pending |
| DATA-06 | Phase 29 | Pending |
| DATA-07 | Phase 29 | Pending |
| RISK-01 | Phase 30 | Complete |
| RISK-02 | Phase 30 | Complete |
| RISK-03 | Phase 30 | Complete |
| RISK-04 | Phase 30 | Pending |
| RISK-05 | Phase 30 | Pending |
| RISK-06 | Phase 30 | Pending |
| RISK-07 | Phase 30 | Complete |
| RISK-08 | Phase 30 | Complete |
| RISK-09 | Phase 30 | Complete |
| DB-01 | Phase 31 | Pending |
| DB-02 | Phase 31 | Pending |
| DB-03 | Phase 31 | Pending |
| DB-04 | Phase 31 | Pending |
| DB-05 | Phase 31 | Pending |
| DB-06 | Phase 31 | Pending |
| API-01 | Phase 31 | Pending |
| API-02 | Phase 31 | Pending |
| API-03 | Phase 31 | Pending |
| API-04 | Phase 31 | Pending |
| API-05 | Phase 31 | Pending |
| NARR-01 | Phase 31 | Pending |
| NARR-02 | Phase 31 | Pending |
| NARR-03 | Phase 31 | Pending |
| NARR-04 | Phase 31 | Pending |

**Coverage:**

- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0

---
*Requirements defined: 2026-06-05*
*Last updated: 2026-06-05 after initial definition*
