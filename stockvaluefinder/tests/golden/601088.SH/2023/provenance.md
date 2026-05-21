# Provenance: 601088.SH (China Shenhua Energy) FY2023

## Status
- **Verification**: PENDING -- requires human verification from annual report

## Data Source
- **AKShare Data**: Frozen (raw_akshare_income.json, raw_akshare_balance.json, raw_akshare_cashflow.json)
- **Annual Report**: NOT YET CROSS-REFERENCED

## Instructions for Verification
1. Download the 2023 annual report from CNINFO (http://www.cninfo.com.cn)
2. Look up consolidated financial statements (合并资产负债表, 合并利润表, 合并现金流量表)
3. Cross-reference frozen AKShare values with annual report figures
4. Run calculate_* functions against the frozen data to compute expected values
5. Update expected_metrics.yaml with the computed values
6. Update this provenance.md with the full computation details (see 600519.SH provenance.md as example)
7. Set `verified_date` and `verified_by` in expected_metrics.yaml
8. Update manifest.yaml: set `l3_verified: true` and `provenance: "frozen_akshare_verified"`

## Notes
- Sector: energy
- is_financial: False
- Key validation focus: P1: High dividend, Yield Gap validation
- Frozen AKShare data is available and can be used to compute metrics immediately
- The human verification step is cross-referencing with the annual report PDF
