# Requirements: StockValueFinder v1.4 — Financial Metrics Validation

**Defined:** 2026-05-20
**Core Value:** Ensure all financial analysis indicators produce numerically correct results end-to-end, from raw AKShare/efinance data through field mapping and calculation to API response.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Metric Registry (REG)

- [ ] **REG-01**: System provides a machine-readable YAML registry (`metric_registry.yaml`) as the single source of truth for all financial metrics across all 7 analysis modules.
- [ ] **REG-02**: Each metric entry defines: display name, module/function path, formula reference (academic paper or textbook), input fields with AKShare/efinance field mappings, output tolerance (absolute and/or relative), whether audit_trail is required, and L1 reference test values from published papers.
- [ ] **REG-03**: Registry supports sector variants (e.g., financial vs non-financial ROIC NOPAT formulas) with distinct input mappings and tolerances per variant.
- [ ] **REG-04**: Registry is Pydantic-validated at load time with frozen models — any schema violation (missing tolerance, invalid formula reference) fails fast before tests run.
- [ ] **REG-05**: Registry is the driver for all golden tests and reconciliation — tests discover which metrics to verify by reading the registry, not hardcoded lists.

### Golden Dataset (GOLD)

- [ ] **GOLD-01**: Golden dataset includes 12-15 CSI 300 stocks spanning all sectors: consumer staples (600519.SH), banking (601398.SH), insurance (601318.SH), technology (000063.SZ), real estate (000002.SZ), high-dividend (601088.SH), plus additional representatives covering pharmaceuticals, energy, industrials, and materials.
- [ ] **GOLD-02**: Each stock/year pair includes: frozen AKShare JSON responses (income, balance sheet, cashflow), hand-verified `expected_metrics.yaml` with values sourced from annual reports (not AKShare), and `provenance.md` documenting which annual report page/line item was used.
- [ ] **GOLD-03**: Golden values cover all 7 modules: M-Score + 8 sub-indices, F-Score, ROIC + NOPAT breakdown, WACC components, FCF projection, Yield Gap components, CapEx scores, Policy resonance scores, and Alpha composite scores.
- [ ] **GOLD-04**: Golden manifest (`manifest.yaml`) catalogs all stock entries with sector, fiscal years, verification status, and provenance — serves as the index for test discovery.
- [ ] **GOLD-05**: Golden values must NOT use AKShare as their source — only annual reports, CNINFO (巨潮), exchange filings, or Wind/Choice terminals.

### L1 Formula Verification (LV1)

- [ ] **LV1-01**: L1 tests verify every pure `calculate_*` function against published paper reference values (e.g., Beneish 1999 Table 3, Piotroski 2000 examples) — not just synthetic inputs.
- [ ] **LV1-02**: M-Score: 8 sub-indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) each tested with at least one paper-published example input/output pair; composite M-Score tested with full paper example.
- [ ] **LV1-03**: ROIC: both financial-sector and non-financial-sector NOPAT formulas tested with at least 3 published examples each; invested capital calculation tested separately.
- [ ] **LV1-04**: F-Score: all 9 binary components tested for correct 0/1 scoring against boundary conditions from Piotroski (2000).
- [ ] **LV1-05**: All L1 tests are marked `@pytest.mark.l1_formula` and run as CI gate on every PR.

### L2 Field Mapping Verification (LV2)

- [ ] **LV2-01**: L2 mapping snapshot tests freeze AKShare JSON responses for golden stocks and assert that key financial fields (revenue, net profit, operating cash flow, total assets, etc.) are non-null after extraction through `_extract_akshare_*` / `_coalesce_akshare_field`.
- [ ] **LV2-02**: L2 field traceability tests verify that each `IndexAuditDetail.numerator / denominator ≈ value` for M-Score sub-indices and ROIC components when computed from frozen AKShare data.
- [ ] **LV2-03**: L2 cross-source consistency tests compare AKShare vs efinance field values for the same ticker+year and assert core financial statement fields deviate < 2%.
- [ ] **LV2-04**: L2 sector-branch tests verify that financial stocks (banks, insurers, securities) correctly trigger financial-sector field extraction paths and non-financial stocks use the standard path.
- [ ] **LV2-05**: All L2 tests are marked `@pytest.mark.l2_mapping` and run as CI gate on every PR (use frozen JSON, no network).

### L3 End-to-End Golden Testing (LV3)

- [ ] **LV3-01**: L3 golden tests exercise the full pipeline for each golden stock/year: frozen AKShare data → data_service extraction → service calculation → compare computed value against hand-verified expected value with registry-specified tolerance.
- [ ] **LV3-02**: P0 metrics (M-Score, ROIC) must achieve 100% pass rate against golden values. P1 metrics (WACC/FCF, Yield Gap, CapEx) must achieve >= 90%.
- [ ] **LV3-03**: Test failures produce a structured diff report showing: metric name, expected value, computed value, delta, tolerance applied, and pass/fail status.
- [ ] **LV3-04**: L3 frozen tests (`-m golden`) run on every PR using frozen JSON — no network required.
- [ ] **LV3-05**: L3 live tests (`-m golden_live`) run weekly against real AKShare endpoints to detect upstream data changes or field renames.

### Reconcile CLI (CLI)

- [ ] **CLI-01**: CLI tool `uv run python -m stockvaluefinder.tools.reconcile --ticker TICKER --year YEAR` fetches live data and compares all computed metrics against golden expected values.
- [ ] **CLI-02**: `--metric METRIC_NAME` flag limits reconciliation to a single metric (e.g., `--metric m_score`).
- [ ] **CLI-03**: `--verbose` flag shows full audit_trail breakdown for each metric, including numerator/denominator values.
- [ ] **CLI-04**: `--json` flag outputs machine-parseable JSON for CI/CD integration.
- [ ] **CLI-05**: CLI displays colored pass/fail table with metric name, expected, computed, delta, tolerance, and status.
- [ ] **CLI-06**: Exit code is 0 if all P0 metrics pass, non-zero if any P0 metric fails (suitable for CI gate).

### CI Integration (CI)

- [ ] **CI-01**: `pytest -m l1_formula` runs on every PR as required gate (fast, no I/O).
- [ ] **CI-02**: `pytest -m l2_mapping` runs on every PR as required gate (frozen JSON, no network).
- [ ] **CI-03**: `pytest -m golden` runs on every PR as required gate (frozen JSON, no network).
- [ ] **CI-04**: `pytest -m golden_live` runs on weekly schedule (hits real AKShare, alerts on regression).
- [ ] **CI-05**: Metric registry YAML schema validation runs as pre-commit hook or early CI step — catches registry drift before tests execute.

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Production Monitoring

- **MON-01**: Periodic reconcile job that alerts (Slack/email) when live computed values deviate from golden beyond tolerance.
- **MON-02**: Dashboard showing per-metric pass/fail status over time with historical trend.

### Frontend

- **FRNT-01**: Frontend displays audit_trail breakdown for each metric so users can inspect how values were computed.

## Out of Scope

| Feature | Reason |
|---------|--------|
| DCF total intrinsic value golden testing | DCF terminal value and total intrinsic value involve LLM-generated growth projections and are inherently subjective — test sub-components (WACC, FCF) only |
| Policy resonance score exact matching | Policy scores involve LLM semantic matching — test range (0-100) and formula only |
| Docker-based calculation sandbox golden testing | `calculation_sandbox.py` is for sandboxed execution — services already test pure functions directly |
| HK stock golden dataset | Focus on CSI 300 A-shares first; HK stocks (0700.HK) can be added in v2 |
| Modifying production API endpoints | Validation is test-time only; no production code changes needed |
| Real-time validation dashboard | v2 production monitoring feature |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REG-01 | Phase 17 | Complete |
| REG-02 | Phase 17 | Complete |
| REG-03 | Phase 17 | Complete |
| REG-04 | Phase 17 | Complete |
| REG-05 | Phase 17 | Complete |
| GOLD-01 | Phase 18 | Complete |
| GOLD-02 | Phase 18 | Complete |
| GOLD-03 | Phase 18 | Complete |
| GOLD-04 | Phase 18 | Complete |
| GOLD-05 | Phase 18 | Complete |
| LV1-01 | Phase 19 | Pending |
| LV1-02 | Phase 19 | Pending |
| LV1-03 | Phase 19 | Pending |
| LV1-04 | Phase 19 | Pending |
| LV1-05 | Phase 19 | Pending |
| LV2-01 | Phase 20 | Pending |
| LV2-02 | Phase 20 | Pending |
| LV2-03 | Phase 20 | Pending |
| LV2-04 | Phase 20 | Pending |
| LV2-05 | Phase 20 | Pending |
| LV3-01 | Phase 21 | Pending |
| LV3-02 | Phase 21 | Pending |
| LV3-03 | Phase 21 | Pending |
| LV3-04 | Phase 21 | Pending |
| LV3-05 | Phase 21 | Pending |
| CLI-01 | Phase 22 | Pending |
| CLI-02 | Phase 22 | Pending |
| CLI-03 | Phase 22 | Pending |
| CLI-04 | Phase 22 | Pending |
| CLI-05 | Phase 22 | Pending |
| CLI-06 | Phase 22 | Pending |
| CI-01 | Phase 23 | Pending |
| CI-02 | Phase 23 | Pending |
| CI-03 | Phase 23 | Pending |
| CI-04 | Phase 23 | Pending |
| CI-05 | Phase 23 | Pending |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0

---
*Requirements defined: 2026-05-20*
*Last updated: 2026-05-20 after initial definition*
