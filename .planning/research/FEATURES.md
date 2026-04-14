# Feature Research

**Domain:** AI-enhanced value investment analysis platform for A-share/HK stocks (individual investors, Chinese language)
**Researched:** 2026-04-14
**Confidence:** HIGH (based on project docs, code review, competitor analysis, and market research)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any stock analysis tool for Chinese individual investors must have. Missing these = product feels incomplete or untrustworthy. These are informed by competitor analysis of TongHuaShun, Xueqiu, and EastMoney, as well as global platforms like Value Sense and ValueMarkers.

| Feature | Why Expected | Complexity | Status |
|---------|--------------|------------|--------|
| Accurate financial data fetching (income statement, balance sheet, cash flow) | Users assume financial data is available; without it, nothing works | MEDIUM | EXISTS (AKShare/efinance/Tushare fallback chain) |
| Stock price lookup (current price, historical) | Fundamental for any valuation or yield calculation | LOW | EXISTS (efinance client) |
| Risk screening (fraud detection scores) | A-share market has high fraud risk; investors demand "explosive mine clearance" | MEDIUM | PARTIAL (M-Score formula exists but indices are hardcoded; F-Score works; need real M-Score calculation) |
| Financial health scoring | Users expect a single verdict: "is this company safe?" | MEDIUM | PARTIAL (risk_level enum exists; M-Score hardcoded; need real index calculation) |
| DCF valuation with adjustable parameters | Value investors expect intrinsic value calculations with sensitivity | MEDIUM | EXISTS (2-stage DCF, WACC, terminal value, parameter overrides) |
| Yield gap analysis (dividend vs risk-free) | Core value proposition; the "is this stock better than a bank deposit?" question | LOW | EXISTS (tax-aware yield gap with HK Stock Connect tax handling) |
| Chinese-language narrative explanation | Target users are Chinese individual investors who need plain-language analysis | MEDIUM | EXISTS (DeepSeek LLM narrative generation with graceful fallback) |
| Data persistence and history | Users expect to revisit past analyses; no re-computation needed | LOW | EXISTS (PostgreSQL with 7 ORM models, Alembic migrations) |
| Standardized API responses | Frontend consumers (future) expect consistent envelope format | LOW | EXISTS (ApiResponse[T] pattern) |
| Redis caching for external data | Repeated API calls are slow and rate-limited; users expect fast responses | MEDIUM | SCAFFOLDING (CacheManager exists but not integrated into routes/services) |
| Source traceability for AI conclusions | Regulatory requirement: AI conclusions must link to source document page/paragraph | HIGH | NOT BUILT (audit_trail field exists in DCF but no RAG-backed source linking) |

### Differentiators (Competitive Advantage)

Features that set StockValueFinder apart from TongHuaShun (general trading tool), Xueqiu (community + discussion), and EastMoney (news + fund sales). None of these platforms offer automated, auditable value investing analysis with RAG-backed reasoning.

| Feature | Value Proposition | Complexity | Status |
|---------|-------------------|------------|--------|
| Beneish M-Score with real calculated indices (not hardcoded) | Only dedicated fraud-screening tool for A-shares; TongHuaShun has basic screening but no M-Score; ValueMarkers and MarketInOut offer it for US stocks only | MEDIUM | NOT BUILT (formula framework exists, indices default to 1.0/0.0) |
| RAG pipeline for annual report analysis (PDF upload -> chunking -> embedding -> retrieval) | No Chinese retail tool offers semantic search over annual reports; this is institutional-grade technology democratized | HIGH | SCAFFOLDING (vector_store, retriever, embeddings, pdf_processor are empty stubs) |
| Multi-agent analysis orchestration (coordinator + risk + valuation + yield agents via LangGraph) | Enables parallel, auditable analysis workflow; single LLM call competitors cannot match this | HIGH | SCAFFOLDING (agent classes exist but are empty TODO stubs) |
| Subprocess-based calculation sandbox | Guarantees deterministic financial arithmetic; LLMs never touch numbers directly; audit trail is complete | MEDIUM | STUB (execute_calculation raises NotImplementedError) |
| Altman Z-Score bankruptcy detection | Pairs naturally with M-Score: M-Score catches earnings manipulation, Z-Score catches insolvency. No A-share retail tool offers both | LOW | NOT BUILT |
| DuPont Analysis (ROE decomposition) | Turns raw ROE into actionable insight: is profitability from operations, asset efficiency, or leverage? | LOW | NOT BUILT |
| Graham Number margin of safety | Strong brand recognition among value investors; minimal implementation effort using existing EPS/BVPS data | LOW | NOT BUILT |
| Tax-aware dividend yield for HK Stock Connect | Automatically deducts 20% dividend tax for mainland investors buying HK stocks via Stock Connect | LOW | EXISTS (market-aware tax calculation in yield_service) |
| LLM-powered DCF explanation endpoint | Generates step-by-step plain-Chinese walkthrough of how intrinsic value was calculated; builds user trust in AI results | MEDIUM | EXISTS (POST /api/v1/analyze/dcf/explain) |
| Yield gap time-series visualization data | Historical yield gap trend (dividend vs bond vs deposit) over time; enables the "three-line chart" from UI spec | MEDIUM | NOT BUILT (only point-in-time analysis; no historical yield gap tracking) |
| Batch CSI 300 screening report generation | Generate static screening reports for all CSI 300 constituents; validates whether target users will pay for 300 reports | HIGH | NOT BUILT (individual stock analysis only) |

### Anti-Features (Deliberately NOT Building)

Features that seem appealing but would derail the project, create regulatory risk, or contradict the value investing philosophy.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Real-time tick-by-tick price data | Users coming from TongHuaShun expect live charts | Value investors do not need minute-level prices; expensive data licensing; induces panic trading | Fetch price on-demand for calculations; cache for 5 minutes; never show intraday charts |
| Technical analysis indicators (K-lines, MACD, RSI, Bollinger Bands) | Every stock app has them | Contradicts value investing philosophy ("do not time the market"); product manager explicitly warned against this | Focus on fundamental indicators only; show weekly/yearly price trends at most |
| AI-powered stock recommendations ("buy/sell/hold") | Users want actionable advice | Regulatory minefield in China; "investment advice" requires securities license; product must position as "auxiliary tool" not "advice" | Provide data, analysis, and narrative context; user makes their own decision; add disclaimer on every output |
| Automated trading execution | Tempting full-stack "analysis to action" feature | Requires brokerage API integration; massive regulatory overhead; enormous liability; product scope explosion | Stay as analysis-only tool; user executes trades on their own broker |
| Social features / community / copy-trading | Xueqiu's model seems successful | Community moderation cost; legal liability for copy-trading losses; herd behavior risk; scope creep | Focus on individual analysis quality; maybe add report sharing (PDF/image export) later |
| Multi-market support (US, Japan, Europe) | Broader market = more users | Data source complexity; different accounting standards; currency conversion; different tax regimes; MVP scope explosion | A-share + HK Stock Connect only; these are the target markets with known pain points |
| Chat-based conversational interface | AI chatbots are trendy | Expensive per-query LLM cost; hallucination risk on financial data; harder to audit than structured reports; not needed for MVP | Batch static reports first; add structured Q&A (not open-ended chat) after validation |
| User authentication and portfolio management | Users want to save their watchlists | Scope creep for MVP; adds complexity (auth, sessions, roles, password reset); single-user system is sufficient for validation | Single-user API for MVP; add auth after product-market fit confirmed |
| Custom indicator / scripting engine | Power users want to write their own formulas | Sandbox security risk; support burden; scope creep; MarketInOut offers this but it is not a differentiator for our target users | Provide a comprehensive set of pre-built analyses (M-Score, Z-Score, DuPont, Graham); defer scripting to v3+ |
| LLM performing financial calculations directly | Faster to implement (just ask the LLM to calculate) | LLMs hallucinate numbers; financial calculations MUST be deterministic; explicitly forbidden by project architecture principle | Extract parameters via LLM, compute in Python, return structured results with audit trail |

---

## Feature Dependencies

```
[Accurate M-Score Calculation]
    +--requires--> [Raw Financial Data Fetching] (EXISTS)
    +--requires--> [Two-Year Comparative Financial Data] (EXISTS)

[RAG Pipeline (PDF -> retrieval)]
    +--requires--> [PDF Processor] (STUB)
    +--requires--> [Embedding Model (bge-m3)] (STUB)
    +--requires--> [Qdrant Vector Store] (STUB)
    +--requires--> [PostgreSQL + pgvector metadata] (EXISTS)
    +--enhances--> [Source Traceability] (audit trail links to document pages)

[Multi-Agent Orchestration]
    +--requires--> [LangGraph State Machine] (NOT BUILT)
    +--requires--> [Risk Agent] (STUB)
    +--requires--> [Valuation Agent] (STUB)
    +--requires--> [Yield Agent] (STUB)
    +--requires--> [Coordinator Agent] (STUB)
    +--enhances--> [Batch CSI 300 Screening] (parallel agent analysis)

[Subprocess Calculation Sandbox]
    +--enhances--> [M-Score Calculation] (safe code execution)
    +--enhances--> [DCF Valuation] (isolated FCF computation)
    +--independent--> Can ship without RAG or agents

[Redis Caching]
    +--independent--> Integrates into any route/service
    +--enhances--> [Batch CSI 300 Screening] (avoid re-fetching for 300 stocks)
    +--enhances--> [Response Speed] (financial data 24h, prices 5min, rates 1h)

[Altman Z-Score]
    +--requires--> [Balance Sheet Data] (already fetched via AKShare)
    +--requires--> [Market Cap Data] (already available)
    +--enhances--> [Risk Analysis] (pairs with M-Score for dual screening)

[DuPont Analysis]
    +--requires--> [Income Statement Data] (already fetched)
    +--requires--> [Balance Sheet Data] (already fetched)
    +--enhances--> [Risk/Quality Analysis] (explains WHY ROE is high or low)

[Graham Number]
    +--requires--> [EPS] (already fetched)
    +--requires--> [Book Value Per Share] (already fetched)
    +--enhances--> [DCF Valuation] (provides quick sanity check against DCF)

[Batch CSI 300 Screening]
    +--requires--> [Redis Caching] (avoid hammering upstream APIs for 300 stocks)
    +--requires--> [CSI 300 Constituent List] (AKShare provides this)
    +--enhances--> [Product Validation] (the two-week sprint goal from PRD)
```

### Dependency Notes

- **M-Score calculation requires raw financial data**: The M-Score formula framework exists in risk_service.py but all 8 indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) default to 1.0/0.0 because the specific data fields needed (receivables, gross profit, fixed assets, etc.) are not yet extracted from financial reports. This is the single most important technical debt.
- **RAG pipeline is a prerequisite for source traceability**: Without document-level retrieval, audit trails cannot link conclusions to specific annual report pages. This is a regulatory requirement.
- **Multi-agent orchestration enhances batch screening**: LangGraph enables parallel risk/valuation/yield analysis per stock, making CSI 300 batch processing feasible.
- **Redis caching is a prerequisite for batch screening**: Without caching, analyzing 300 stocks means 300+ upstream API calls per batch run. Caching (24h for financials, 5min for prices) reduces this dramatically.
- **Subprocess sandbox is independent**: It can ship without RAG or agents. Current calculations run in-process as pure Python functions. The sandbox adds isolation for user-submitted or LLM-generated code.
- **Altman Z-Score, DuPont, and Graham Number all use existing data**: All three can leverage data already being fetched by the AKShare/efinance clients. No new external data dependencies.
- **LLM calculations are forbidden by architecture principle**: All anti-features around LLM arithmetic stem from the core architectural decision that financial calculations must be deterministic Python, never LLM-generated.

---

## MVP Definition

### Launch With (v1 -- Current Milestone)

The minimum needed to validate whether Chinese individual investors will pay for automated value investing analysis of CSI 300 stocks.

- [x] ~~Multi-source financial data fetching (AKShare/efinance/Tushare)~~ -- EXISTS
- [x] ~~Risk analysis API with M-Score framework, F-Score, anomaly detection~~ -- PARTIAL (needs real M-Score indices)
- [x] ~~DCF valuation API with adjustable parameters~~ -- EXISTS
- [x] ~~Yield gap analysis API with tax-awareness~~ -- EXISTS
- [x] ~~LLM narrative generation in Chinese~~ -- EXISTS
- [x] ~~PostgreSQL persistence~~ -- EXISTS
- [ ] **M-Score indices calculated from real financial data** -- The highest-priority fix; hardcoded defaults make the fraud detection non-functional
- [ ] **Redis caching integration** -- CacheManager exists but is not wired into routes/services; essential for batch screening performance
- [ ] **Comprehensive test suite (80%+ coverage)** -- Currently low coverage; no integration tests; risk service untested

### Add After Validation (v1.x)

Features to add once core analysis is working and validated with real users.

- [ ] **Altman Z-Score** -- Pairs with M-Score for complete risk screening; uses existing balance sheet data; well-validated model
- [ ] **DuPont Analysis** -- Turns raw ROE into actionable insight; trivial math on existing data; high user value
- [ ] **Graham Number** -- Minimal effort, strong value investing brand recognition; quick sanity check against DCF
- [ ] **RAG pipeline** -- PDF upload, chunking, bge-m3 embedding, Qdrant storage, semantic retrieval; enables source traceability
- [ ] **Multi-agent orchestration** -- LangGraph coordinator + specialized agents; enables parallel analysis and batch screening
- [ ] **Subprocess calculation sandbox** -- Isolated Python execution for deterministic computations; audit trail generation
- [ ] **Yield gap historical tracking** -- Store and serve historical yield gap data; enables the "three-line chart" from UI spec
- [ ] **Batch CSI 300 report generation** -- Generate static screening reports for all constituents; validate willingness to pay

### Future Consideration (v2+)

Features to defer until product-market fit is established and user demand is clear.

- [ ] **Free Cash Flow Quality Score** -- Multi-year CFO/net income ratio; catches what M-Score misses
- [ ] **Debt Serviceability Metrics** -- Interest coverage, debt/EBITDA, net debt/FCF; quantifies leverage risk beyond "cun dai shuang gao" flag
- [ ] **PEG Ratio** -- Growth-adjusted valuation; different angle than DCF for growth-oriented value plays
- [ ] **Earnings Stability scoring** -- EPS volatility and compound growth rates over 5+ years; requires multi-year historical data
- [ ] **Shareholder Return Analysis** -- Dividend payout trends, buyback yield, total shareholder return; extends yield gap
- [ ] **Interactive parameter sliders in frontend** -- When frontend is built, allow real-time DCF parameter adjustment
- [ ] **PDF/image report export** -- Share analysis results as formatted documents
- [ ] **Mobile-responsive dashboard** -- Core layout showing yield gap + risk score for on-the-go analysis

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| M-Score real index calculation | HIGH | MEDIUM | P1 |
| Redis caching integration | HIGH | LOW | P1 |
| Test suite (80%+ coverage) | MEDIUM (internal) | MEDIUM | P1 |
| Altman Z-Score | HIGH | LOW | P2 |
| DuPont Analysis | HIGH | LOW | P2 |
| Graham Number | MEDIUM | LOW | P2 |
| RAG pipeline | HIGH | HIGH | P2 |
| Multi-agent orchestration | HIGH | HIGH | P2 |
| Subprocess calculation sandbox | MEDIUM | MEDIUM | P2 |
| Batch CSI 300 screening | HIGH | MEDIUM | P2 |
| Yield gap historical tracking | MEDIUM | MEDIUM | P3 |
| FCF Quality Score | MEDIUM | LOW | P3 |
| Debt Serviceability Metrics | MEDIUM | LOW | P3 |
| PEG Ratio | LOW | LOW | P3 |
| Earnings Stability | MEDIUM | MEDIUM | P3 |
| Shareholder Return Analysis | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for this milestone -- fixes broken core functionality (M-Score), enables performance (Redis), ensures quality (tests)
- P2: Should have -- completes the analysis toolkit (Z-Score, DuPont, Graham) and enables advanced capabilities (RAG, agents, batch)
- P3: Nice to have -- extends analysis depth and adds secondary metrics

---

## Competitor Feature Analysis

| Feature | TongHuaShun (iFinD) | Xueqiu | ValueMarkers / Value Sense | StockValueFinder |
|---------|---------------------|--------|---------------------------|------------------|
| Financial data access | Full (paid Level-2) | Basic (free) | US markets primarily | A-share + HK via AKShare (free) |
| Technical analysis | Industry-leading K-line, indicators | Basic charts | Not a focus | NOT building (anti-feature) |
| Natural language stock query | "WenCai 2.0" (NL screening) | Not available | Not available | Not yet; RAG-based search planned |
| M-Score fraud detection | Not available for retail | Not available | Available (US stocks) | Building (A-share + HK) |
| F-Score financial health | Basic financial screening | Community discussion | Available | Building (A-share + HK) |
| DCF valuation | Not interactive | Not available | Available (some platforms) | Built with adjustable params |
| Dividend yield gap analysis | Not available | Community posts mention it | Not available | Built with tax-awareness |
| AI narrative explanation | Limited AI summaries | Not available | Some AI summaries | Built via DeepSeek |
| Annual report RAG search | Not available | Not available | Not available | Planned (differentiator) |
| Community / social | Basic stock forum | Industry-leading (9.5/10) | Not a focus | NOT building (anti-feature) |
| Brokerage integration | Full trading capability | Linked to brokers | Not available | NOT building (anti-feature) |
| Batch screening | Premium feature | Not available | Screener available | Planned for CSI 300 |

### Competitive Positioning

StockValueFinder occupies a unique niche: **automated, auditable value investing analysis for A-share/HK stocks**. TongHuaShun dominates trading and technical analysis. Xueqiu dominates community discussion. Neither focuses on the value investor who wants to answer "is this company lying?" and "is this stock cheaper than a bank deposit?" Those two questions are the product's killer features.

The competitive moat comes from combining three things no single competitor offers:
1. **Deterministic financial calculations** (M-Score, DCF, yield gap) with LLM narrative -- not black-box AI
2. **RAG-backed source traceability** -- every AI conclusion links to the original report page
3. **A-share specific domain knowledge** -- "cun dai shuang gao" detection, HK Stock Connect tax handling, China-specific risk-free rates

---

## Sources

- Project documentation: `doc/AI-enhanced value investing decision platform.md`, `doc/system_idea.md`, `doc/Core technology architecture and implementation documentation.md`
- Additional analysis advice: `doc/Additional_Financial_Analysis_Advice.md`, `doc/Additional_Financial_Analysis_Technology_Advice.md`
- UI recommendations: `doc/ui_advise.md`
- Codebase review: services (risk, valuation, yield, narrative), routes (risk, valuation, yield), agents (coordinator, risk, valuation, yield -- all stubs), RAG (all stubs)
- Competitor analysis: TongHuaShun "WenCai 2.0" NL search, Xueqiu community model, EastMoney comprehensive services -- [Sina Finance 2025 App review](https://finance.sina.cn/2025-11-25/detail-infyqyue3055551.d.html)
- Global value investing tools: Value Sense Beneish M-Score calculator, ValueMarkers multi-score screening, MarketInOut screener -- [Value Sense](https://valuesense.io/), [ValueMarkers](https://valuemarkers.com/compare)
- AI stock analysis landscape: Jenova.ai DCF, ValuationBot, Alpha Spread -- [SchemaForge comparison guide](https://schemaforge.ai/zh/blog/best-ai-stock-research-tools-2025)
- Stock analysis app feature expectations: [DeepTracker 2026 tools guide](https://www.deeptracker.ai/blog/best-stock-market-analysis-tools), [WallStreetZen analysis software](https://www.wallstreetzen.com/blog/best-stock-analysis-software/)

---
*Feature research for: AI-enhanced value investment analysis platform (A-share/HK stocks)*
*Researched: 2026-04-14*
