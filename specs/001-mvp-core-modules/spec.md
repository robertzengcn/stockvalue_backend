# Feature Specification: AI 增强型价值投资决策平台 MVP

**Feature Branch**: `001-mvp-core-modules`
**Created**: 2026-02-26
**Status**: Draft
**Input**: User description: "AI 增强型价值投资决策平台 MVP - 核心三大模块: 财报解析、动态估值、风险排雷"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 财务排雷报告生成 (Priority: P1)

严肃投资者想要快速了解一只A股或港股是否存在财务造假风险，系统自动分析财报数据并生成排雷报告。

**Why this priority**: 在A股做价值投资，"不踩雷"比"选牛股"更重要。这是MVP的核心护城河功能，能直接帮助用户避免重大损失。

**Independent Test**: 可以独立测试 - 输入股票代码，系统返回Beneish M-Score、存贷双高检测、商誉占比等风险指标。用户可以通过报告判断是否需要进一步调研或规避该股票。

**Acceptance Scenarios**:

1. **Given** 用户输入股票代码 "600519.SH" (贵州茅台), **When** 系统完成分析, **Then** 返回完整的排雷报告包含 M-Score < -1.78 (安全)、存贷双高检测通过、商誉占比正常
2. **Given** 用户输入股票代码, **When** 该公司存在存贷双高异常, **Then** 报告中"存贷双高"标记为红色警告，并显示具体异常数据
3. **Given** 用户输入港股代码 "0700.HK", **When** 系统计算 M-Score, **Then** 正确应用港股会计准则进行计算并给出结果

---

### User Story 2 - 股息率 vs 存款利率对比 (Priority: P2)

投资者想要比较持有高股息股票与存银行大额存单的收益差异，系统计算税后股息率并与实时存款利率对比。

**Why this priority**: 这是2026年市场环境下投资者最关心的"确定性"收益对比，能够帮助用户做出明智的资产配置决策。

**Independent Test**: 可以独立测试 - 输入股票代码和持仓成本，系统返回税后股息率、存款利率、利差，并给出投资建议。

**Acceptance Scenarios**:

1. **Given** 用户输入港股代码 "0700.HK" 和持仓成本 300 HKD, **When** 系统计算股息率, **Then** 返回税后股息率(已扣除20%港股通红利税)、3年期大额存单利率、二者利差
2. **Given** 股票税后股息率 < 存款利率, **When** 系统生成建议, **Then** 显示红色警告 "风险提示：当前分红回报不具吸引力"
3. **Given** 股票税后股息率 > 存款利率, **When** 系统生成建议, **Then** 显示正利差并提示投资价值

---

### User Story 3 - 动态 DCF 估值 (Priority: P3)

投资者想要了解股票的内在价值，系统根据实时无风险利率和行业增长率自动计算DCF估值并显示安全边际。

**Why this priority**: 解决用户"不知道多少钱算便宜"的问题，是价值投资的核心工具，但依赖前两个模块的数据基础。

**Independent Test**: 可以独立测试 - 输入股票代码，系统返回WACC、FCF预测、内在价值、当前股价的安全边际。

**Acceptance Scenarios**:

1. **Given** 用户输入股票代码 "000002.SZ", **When** 系统运行 DCF 模型, **Then** 返回内在价值、折现率(WACC包含实时10年期国债收益率)、预测增长率、安全边际百分比
2. **Given** 用户调整增长率滑块从5%到3%, **When** 参数改变, **Then** 系统实时重新计算内在价值并更新安全边际
3. **Given** 当前股价高于内在价值, **When** 系统评估, **Then** 显示负安全边际提示"当前估值偏高"

---

### Edge Cases

- What happens when 年报数据缺失或PDF解析失败？系统应提示用户数据不可用并记录日志
- What happens when 股票停牌无最新股价？使用最后有效交易日价格并标注
- What happens when 存款利率数据源暂时不可用？显示缓存数据并标注更新时间，如果缓存超过24小时则警告
- How does system handle 同时分析多只股票？支持批量输入，但串行处理避免API限流
- What happens when 计算出的财务指标异常（如除零错误）？系统应捕获异常并返回"数据异常"而非崩溃

## Requirements *(mandatory)*

### Functional Requirements

#### 模块一：财务排雷系统 (Risk Shield)
- **FR-001**: System MUST 自动计算 Beneish M-Score 的8个维度指标并给出总分
- **FR-002**: System MUST 检测"存贷双高"异常（账面货币资金与有息负债同时高增长）
- **FR-003**: System MUST 计算商誉占净资产比例并标记过高的公司（>30%）
- **FR-004**: System MUST 提取核心财务指标：营收、净利润、经营性现金流、毛利率、资产负债率
- **FR-005**: System MUST 检测净利润与经营性现金流的背离情况并发出警告
- **FR-006**: System MUST 支持A股（中国会计准则）和港股（IFRS）两种会计准则
- **FR-007**: System MUST 所有计算结果必须可追溯到财报原文的页码和段落

#### 模块二：机会成本对比引擎 (Yield Gap)
- **FR-008**: System MUST 计算税后股息率（A股无红利税，港股通自动扣除20%）
- **FR-009**: System MUST 获取最新的3年期大额存单利率和10年期国债收益率（日更）
- **FR-010**: System MUST 计算利差 = 税后股息率 - max(国债利率, 存款利率)
- **FR-011**: System MUST 当利差 < 0 时显示红色警告提示
- **FR-012**: System MUST 支持用户输入持仓成本以计算个人股息率

#### 模块三：动态估值沙盒 (Valuation Sandbox)
- **FR-013**: System MUST 实现 DCF（现金流折现）模型计算内在价值
- **FR-014**: System MUST 实时获取10年期国债收益率作为无风险利率
- **FR-015**: System MUST 根据行业历史数据提供合理的增长率预设值
- **FR-016**: System MUST 支持用户动态调整参数（增长率、折现率、终端增长率）并实时重新计算
- **FR-017**: System MUST 显示安全边际 = (内在价值 - 当前股价) / 当前股价
- **FR-018**: System MUST 所有计算必须由确定性Python代码执行，LLM仅负责参数提取和结果解读

#### 数据与架构要求
- **FR-019**: System MUST 使用 Tushare 或 AKShare API 获取A股/港股财务数据
- **FR-020**: System MUST 实现双数据源备份，主数据源故障时自动切换
- **FR-021**: System MUST 将年报PDF转换为保留表格结构的Markdown格式
- **FR-022**: System MUST 对财报数据实现缓存机制（无重大公告且股价波动<1%时使用缓存）
- **FR-023**: System MUST 所有财务计算在隔离的Docker容器中执行
- **FR-024**: System MUST API响应格式遵循统一标准 {success, data, error, meta}

#### 性能与质量要求
- **FR-025**: System MUST 单只股票排雷报告生成时间在 30秒内
- **FR-026**: System MUST AI提取的财务指标与人工复核一致性 > 98%
- **FR-027**: System MUST 支持 CSI 300 成分股的批量分析
- **FR-028**: System MUST 通过严格的类型检查（mypy strict模式）
- **FR-029**: System MUST 测试覆盖率 > 80%
- **FR-030**: System MUST 所有API端点必须有输入验证（Pydantic模型）

### Key Entities

- **股票 (Stock)**: 代表一只A股或港股，包含代码、名称、市场、行业、最新股价等属性
- **财务报告 (FinancialReport)**: 公司的年报或季报，包含营收、利润、现金流等财务数据
- **风险评分 (RiskScore)**: 对股票的风险评估结果，包含M-Score、存贷双高标志、商誉占比等
- **股息数据 (DividendData)**: 股票的分红信息，包含每股股利、分红频率、税率等
- **估值结果 (ValuationResult)**: DCF估值计算结果，包含内在价值、WACC、增长率、安全边际等
- **利率数据 (RateData)**: 市场利率信息，包含国债收益率、存款利率、更新时间等

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户可以在 30秒内 获得单只股票的完整排雷报告
- **SC-002**: 系统标记为"高风险"（M-Score > -1.78）的公司，在未来6个月内出现ST或大幅下跌 > 20% 的比例 > 60%
- **SC-003**: AI提取的财务指标与人工复核的一致性 > 98%
- **SC-004**: 股息率对比计算的准确性 > 99.5%（通过抽样人工验证）
- **SC-005**: 用户可以在 1分钟内 完成从输入股票代码到获得完整投资建议（排雷+股息+估值）的流程
- **SC-006**: 系统支持同时处理 10只股票 的批量分析请求而响应时间线性增长
- **SC-007**: 90% 的用户能够理解排雷报告并基于报告做出投资决策（通过用户调研验证）

## Dependencies & Assumptions

### Dependencies
- Tushare Pro API token 或 AKShare 数据访问权限
- LLM API访问（Claude 3.5 Sonnet / DeepSeek-V3 / GPT-4o）
- 向量数据库（Qdrant）和关系数据库
- 年报PDF数据源（巨潮资讯、港交所）

### Assumptions
- MVP阶段仅支持CSI 300成分股
- 用户具备基础财务知识，理解市盈率、股息率等概念
- 年报数据以PDF格式为主，暂不考虑XBRL格式
- 港股通用户已开通港股通交易权限
- 存款利率参考四大国有大行的大额存单利率
- 计算基准日为最新财报发布日

## Out of Scope

以下功能明确不在MVP范围内：
- 实时股价推送（仅提供查询，不推送）
- 管理层诚信度检测（语义分析MD&A与审计意见）
- 行业政策自动跟踪与分析
- 用户投资组合管理功能
- AI对话式交互（MVP仅提供静态报告生成）
- 跨市场套利提醒（AH股溢价分析）
- 自动交易下单功能
