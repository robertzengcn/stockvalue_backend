# Phase 1: M-Score Real Calculation - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix hardcoded M-Score indices by calculating all 8 (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) from actual two-year financial data. The calculation replaces the current default values (1.0/0.0) hardcoded in `data_service.py` with real year-over-year ratios. Data validation errors replace silent defaults when required fields are missing.

Scope: M-Score 8 indices calculation, data field mapping expansion in `get_financial_report`, audit trail with intermediate values. Does NOT include: F-Score changes, caching, RAG pipeline, agent orchestration, or UI.

</domain>

<decisions>
## Implementation Decisions

### 数据字段映射策略

- **D-01:** 统一映射层 — 在 `data_service.py` 的 `_get_financial_report_from_akshare/efinance/tushare` 中扩展字段映射，将原始字段名统一成内部标准名。`risk_service` 只处理标准化后的数据，不关心数据来源差异。
- **D-02:** 扩展 `get_financial_report` — 在现有映射中补充 M-Score 所需的额外字段（约 10 个），不新增专用方法。
- **D-03:** 独立计算函数 — 新增 `calculate_mscore_indices(current_report, previous_report)` 纯函数，接收两年标准化财务数据，返回 8 个指数值。`calculate_beneish_m_score` 保持不变，仍只做线性组合。
- **D-04:** SG&A 代理字段 — 用 `OPERATE_EXPENSE`（营业总支出）作为 SG&A 费用的代理，避免字段缺失问题。
- **D-05:** DEPI 简化处理 — MVP 阶段 DEPI（折旧指数）设为 1.0（中性值），因 AKShare 不直接提供折旧字段。后续有更好数据源时优化。
- **D-06:** TATA 用标准公式 — `(Net Income - Operating Cash Flow) / Total Assets`，用已有的 `net_income` 和 `operating_cash_flow` 字段。
- **D-07:** 完整字段映射表确认 — M-Score 所需字段及 AKShare 对应关系已确认（见 code_context 部分）。

### 缺失数据与边界处理

- **D-08:** 严格模式 — M-Score 必需字段缺失时抛出 `DataValidationError`，不返回 M-Score 结果。符合 success criteria #4 要求。
- **D-09:** 分母为零时标记不可计算 — 若指数计算中分母为零（如前一年 revenue 为零），该指数标记为不可计算，`red_flags` 添加警告。M-Score 仍用其他可计算指数给出结果。
- **D-10:** 港股和 A 股统一处理 — M-Score 计算逻辑不区分市场。数据源差异在 `data_service` 层处理。

### 数据验证与审计追踪

- **D-11:** 完整审计追踪 — 每个指数附带计算中间值（分子、分母、比值）和字段来源（如 `accounts_receivable -> ACCOUNTS_RECE (AKShare)`）。
- **D-12:** 扩展 MScoreData — 在现有 JSONB 列 `mscore_data` 中增加每个指数的中间值和来源信息，不需要新数据库迁移。

### Claude's Discretion

- 具体的字段映射实现细节（如 efinance/Tushare 的备选字段名优先级）
- `calculate_mscore_indices` 函数的内部结构和错误消息措辞
- 不可计算指数的 `red_flags` 文本内容

### Folded Todos

None.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### M-Score 算法参考
- `doc/M-Score 与 F-Score：投资分析.md` — M-Score 8 指标的业务解释、阈值标准、与 F-Score 的配合使用策略

### 现有代码（必须理解）
- `stockvaluefinder/stockvaluefinder/services/risk_service.py` — 当前 M-Score 计算逻辑（公式正确，但依赖预计算 index）
- `stockvaluefinder/stockvaluefinder/external/data_service.py` — 数据获取和字段映射（当前硬编码 8 个 index 为 1.0/0.0）
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` — AKShare API 客户端（get_profit_sheet, get_balance_sheet, get_cash_flow_sheet 方法）
- `stockvaluefinder/stockvaluefinder/models/risk.py` — MScoreData Pydantic 模型（需扩展审计字段）
- `stockvaluefinder/stockvaluefinder/api/risk_routes.py` — 风险分析 API 端点（调用链参考）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `calculate_beneish_m_score()` in `risk_service.py:10-80` — M-Score 线性组合公式已正确实现，保持不变
- `calculate_piotroski_f_score()` in `risk_service.py:83-212` — F-Score 已从原始数据计算，可作为 M-Score 改造的参考模式
- `AKShareClient` in `akshare_client.py` — 已有 `get_profit_sheet`, `get_balance_sheet`, `get_cash_flow_sheet` 方法，支持 period 参数获取指定年度数据
- `eastmoney_hsf10_symbol()` in `akshare_client.py:16-39` — 股票代码转换，已处理 SH/SZ/HK 格式
- `ExternalDataService.get_financial_report()` in `data_service.py:725-800` — 统一数据获取入口，已支持 fallback 链
- `_get_financial_report_from_akshare()` in `data_service.py:802-913` — AKShare 字段映射参考，需扩展

### Established Patterns
- 纯函数服务模式：`risk_service.py` 中所有计算都是无状态纯函数，新函数应遵循此模式
- 冻结 Pydantic 模型：`MScoreData` 使用 `model_config = {"frozen": True}`
- 字段名映射模式：`data_service.py` 中用 `income.get("FIELD_EN", income.get("字段中文", 0))` 多级回退
- 数据获取链：`risk_routes.py` -> `data_service.get_financial_report()` -> `akshare_client` -> `risk_service.calculate_*`

### Integration Points
- `data_service.py:895-902` (AKShare), `974-981` (efinance), `1044-1051` (Tushare) — 硬编码 index 值的位置，需替换为真实计算
- `risk_service.py:48-55` — `calculate_beneish_m_score` 读取 index 值的位置，需改为读取 `calculate_mscore_indices` 的结果
- `risk_service.py:396-510` — `analyze_financial_risk` 编排函数，需在调用 `calculate_beneish_m_score` 之前调用 `calculate_mscore_indices`
- `models/risk.py:12-24` — `MScoreData` 模型，需扩展审计字段

### M-Score 完整字段映射表

| 内部标准名 | AKShare 字段 | 数据源 | 指数用途 |
|---|---|---|---|
| revenue | TOTAL_OPERATE_INCOME | profit_sheet | DSRI, SGI, DEPI |
| net_income | NETPROFIT | profit_sheet | TATA |
| operating_cash_flow | NETCASH_OPERATE | cash_flow_sheet | TATA |
| accounts_receivable | ACCOUNTS_RECE | balance_sheet | DSRI |
| cost_of_goods | OPERATE_COST | profit_sheet | GMI, DEPI |
| total_current_assets | TOTAL_CURRENT_ASSETS | balance_sheet | AQI |
| total_assets | TOTAL_ASSETS | balance_sheet | AQI, TATA, LVGI |
| ppe (固定资产) | FIXED_ASSET | balance_sheet | AQI, DEPI |
| sga_expense | OPERATE_EXPENSE | profit_sheet | SGAI |
| depreciation | (无直接字段，MVP=1.0) | - | DEPI |
| long_term_debt | LONGTERM_LOAN | balance_sheet | LVGI |
| total_liabilities | TOTAL_LIABILITIES | balance_sheet | LVGI |

</code_context>

<specifics>
## Specific Ideas

- DEPI 指数在 MVP 阶段简化为 1.0 中性值，后续可通过估算折旧（固定资产净值变化+现金流量表补充数据）优化
- 不可计算的指数应在 red_flags 中明确说明原因（如 "DSRI: previous year revenue is zero, index not calculable"）
- 审计追踪格式参考：`{"dsri": {"value": 1.15, "numerator": 0.32, "denominator": 0.28, "source_fields": {"accounts_receivable": "ACCOUNTS_RECE (AKShare)", "revenue": "TOTAL_OPERATE_INCOME (AKShare)"}}}`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-m-score-real-calculation*
*Context gathered: 2026-04-14*
