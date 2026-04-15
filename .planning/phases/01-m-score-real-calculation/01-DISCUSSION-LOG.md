# Phase 1: M-Score Real Calculation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 01-m-score-real-calculation
**Areas discussed:** 数据字段映射策略, 缺失数据与边界处理, 数据验证与审计追踪

---

## 数据字段映射策略

| Option | Description | Selected |
|--------|-------------|----------|
| 统一映射层 | 在 data_service 层做字段标准化映射 | ✓ |
| 计算函数内处理 | 在 risk_service 中直接处理不同数据源字段名 | |
| 独立映射模块 | 新建 field_mapper.py 专门负责字段转换 | |

**User's choice:** 统一映射层
**Notes:** 与现有架构一致，data_service 已经在做部分字段映射

| Option | Description | Selected |
|--------|-------------|----------|
| 扩展 financial report | 在现有 get_financial_report 中补充 M-Score 字段 | ✓ |
| 新增专用方法 | 新建 get_mscore_raw_data 方法 | |

**User's choice:** 扩展 financial report
**Notes:** 保持 data_service 作为统一数据入口

| Option | Description | Selected |
|--------|-------------|----------|
| 独立函数 | 新增 calculate_mscore_indices 纯函数 | ✓ |
| 合并到现有函数 | 改造 calculate_beneish_m_score | |

**User's choice:** 独立函数
**Notes:** 职责分离，保持 calculate_beneish_m_score 不变

| Option | Description | Selected |
|--------|-------------|----------|
| OPERATE_EXPENSE | 营业总支出作为 SG&A 代理 | ✓ |
| 销售费用+管理费用 | 更接近原始定义但可能缺失 | |
| 优先精确回退到总费用 | 复杂度稍高但更准确 | |

**User's choice:** OPERATE_EXPENSE
**Notes:** 简单可靠，避免字段缺失问题

| Option | Description | Selected |
|--------|-------------|----------|
| MVP 先简化 DEPI | 设为 1.0 中性值 | ✓ |
| 复杂估算折旧 | 用资产负债表和现金流量表估算 | |

**User's choice:** MVP 先简化 DEPI
**Notes:** AKShare 无直接折旧字段，后续优化

| Option | Description | Selected |
|--------|-------------|----------|
| 标准公式 | (Net Income - CFO) / Total Assets | ✓ |
| 详细应计分解 | 包含非流动资产/负债变化 | |

**User's choice:** 标准公式
**Notes:** 用已有字段，无需额外数据

---

## 缺失数据与边界处理

| Option | Description | Selected |
|--------|-------------|----------|
| 严格模式 — 报错 | 缺失字段拋出 DataValidationError | ✓ |
| 降级模式 — 默认值+警告 | 用默认值并标记 | |
| 混合模式 — 核心报错，次要降级 | 核心字段报错，次要字段用默认值 | |

**User's choice:** 严格模式 — 报错
**Notes:** 符合 success criteria #4 要求

| Option | Description | Selected |
|--------|-------------|----------|
| 标记不可计算 | 指数标记为不可计算，red_flags 添加警告 | ✓ |
| 直接报错 | 不返回 M-Score | |

**User's choice:** 标记不可计算
**Notes:** 分母为零时仍给出部分结果

| Option | Description | Selected |
|--------|-------------|----------|
| 统一处理 | 港股和 A 股不区分计算逻辑 | ✓ |
| 单独处理港股 | 港股用不同字段映射或计算逻辑 | |

**User's choice:** 统一处理
**Notes:** 差异在 data_service 层解决

---

## 数据验证与审计追踪

| Option | Description | Selected |
|--------|-------------|----------|
| 完整中间值+来源 | 每个指数附带分子、分母、字段来源 | ✓ |
| 简洁 — 仅结果值 | 只记录指数值和最终 M-Score | |
| 中间值，无来源 | 平衡信息量和复杂度 | |

**User's choice:** 完整中间值+来源
**Notes:** 完全可重现计算过程

| Option | Description | Selected |
|--------|-------------|----------|
| 扩展 MScoreData | 在现有 JSONB 列中增加审计数据 | ✓ |
| 单独存储 | 新增数据库字段 | |

**User's choice:** 扩展 MScoreData
**Notes:** 不需要新数据库迁移

---

## Claude's Discretion

- efinance/Tushare 的备选字段名优先级
- calculate_mscore_indices 函数的内部结构
- 不可计算指数的 red_flags 文本内容

## Deferred Ideas

None — discussion stayed within phase scope.
