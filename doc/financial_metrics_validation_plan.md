# 财务指标准确性验证方案

本文档描述 StockValueFinder 系统中各类财务分析指标的**准确性验证体系**。适用于在已扩展 M-Score、F-Score、DCF、Yield Gap、ROIC、资本配置、政策共振、Alpha 综合分等指标后，系统性回答「这些数字算得对不对」的问题。

**相关入口**：`stockvaluefinder/main.py` 挂载的分析 API  
**最后更新**：2026-05-20

---

## 1. 背景与问题定义

当前系统通过 `main.py` 挂载了多条分析链路：

| 模块 | API 前缀 | 核心指标 |
|------|----------|----------|
| Risk | `POST /api/v1/analyze/risk` | Beneish M-Score、Piotroski F-Score、存贷双高、商誉比、利润-现金流背离 |
| Yield | `POST /api/v1/analyze/yield` | 税后股息率、Yield Gap |
| Valuation | `POST /api/v1/analyze/dcf` | WACC、FCF 预测、终值、安全边际 |
| ROIC | `POST /api/v1/analyze/roic` | NOPAT、投入资本、ROIC-WACC Spread、护城河趋势 |
| CapEx | `POST /api/v1/analyze/capex` | 回购收益率、分红稳定性、扩张纪律 |
| Policy | `POST /api/v1/analyze/policy/resonance` | 政策共振分、DCF 终值调整 |
| Alpha | `POST /api/v1/analyze/alpha` | 四维加权综合 Alpha 分 |

现有单元测试（如 `tests/unit/test_services/test_risk_service.py` 的 Hypothesis 属性测试、`test_roic_service.py` 的公式用例）主要验证 **L1：给定输入时公式是否正确**。

它们**无法**单独回答：

> 从 AKShare/efinance 原始字段 → 字段映射 → 服务计算 → 入库/API 返回，整条链路的数值是否与年报或权威数据源一致？

A 股尤其容易在**字段映射层**出错（银行/保险科目名、`_coalesce_akshare_field` 多字段回退等），这类错误不会触发纯公式单元测试失败。

---

## 2. 验证目标三层模型

每个指标需验证三个层次，缺一不可：

```
┌─────────────────────────────────────────────────────────────┐
│  L1 公式正确性      calculate_* 纯函数是否符合学术/行业定义    │
│  L2 输入映射正确性   AKShare 字段 → 服务入参 是否取对、取全    │
│  L3 端到端数值正确性  同一 ticker+fiscal_year 与基准值偏差可接受 │
└─────────────────────────────────────────────────────────────┘
```

| 层次 | 当前覆盖情况 | 主要缺口 |
|------|-------------|----------|
| L1 | 较好（risk/roic/valuation/yield/alpha/capex 均有单元测试） | 部分指标缺论文参考值用例 |
| L2 | 薄弱 | `data_service.py` 字段提取与行业分支 |
| L3 | 几乎无 | 无 Golden Dataset 回归 |

---

## 3. 指标注册表（Metric Registry）

建议建立机器可读的**指标注册表**，作为所有验证的单一事实来源。

**建议路径**：`stockvaluefinder/tests/fixtures/metric_registry.yaml`

```yaml
metrics:
  beneish_m_score:
    module: risk_service.calculate_beneish_m_score
    formula_ref: "Beneish (1999) Financial Analysts Journal 55(5)"
    tolerance: { absolute: 0.05, relative: 0.02 }
    audit_trail_required: true
  roic:
    module: roic_service.calculate_roic
    sector_variants:
      financial: "NOPAT = OPERATE_PROFIT * (1-T)"
      non_financial: "NOPAT = (TOTAL_PROFIT + FINANCE_EXPENSE) * (1-T)"
    tolerance: { relative: 0.01 }
```

**作用**：明确公式来源、输入字段、容差；驱动 golden 测试与覆盖率报告；与现有 `audit_trail` 对齐。

---

## 4. 四层验证体系

### 4.1 第 1 层：公式层（Formula Verification）

**目标**：纯函数在合成输入下输出可手算的结果。

- 从 Beneish / Piotroski 原论文各取 1～2 组 published example
- 对 `calculate_mscore_indices` 的 8 个子指数逐项验证分子分母
- 金融股 vs 非金融股 ROIC 双公式，各至少 3 个用例
- **CI 要求**：本层测试作为每次 PR 必过项

### 4.2 第 2 层：映射层（Field Mapping Verification）

**数据流**：

```
AKShare raw record → _extract_akshare_* / _coalesce_akshare_field
  → financial_report dict → route → calculate_* 入参
```

**验证方法**：

1. **Mapping 快照测试**：freeze AKShare JSON，断言关键字段非 null、行业分支正确
2. **字段溯源测试**：利用 `IndexAuditDetail` 复算 `numerator/denominator ≈ value`
3. **跨源一致性**：同一 ticker+year，AKShare vs efinance 核心字段偏差 < 2%

### 4.3 第 3 层：Golden Dataset（金标准数据集）

**样本设计**（建议 12～15 只 CSI 300）：

| 类别 | ticker | 验证重点 |
|------|--------|----------|
| 消费龙头 | 600519.SH | M-Score、ROIC |
| 银行 | 601398.SH | 金融 ROIC 公式 |
| 保险 | 601318.SH | 收入科目映射 |
| 科技 | 000063.SZ | CapEx、FCF |
| 地产 | 000002.SZ | 高杠杆 LVGI |
| 高分红 | 601088.SH | Yield Gap |
| 港股 | 0700.HK | 股息税 |

**目录结构**（`stockvaluefinder/tests/golden/`）：

```
tests/golden/
├── 600519.SH/2023/
│   ├── raw_akshare_income.json
│   ├── raw_akshare_balance.json
│   ├── raw_akshare_cashflow.json
│   ├── expected_metrics.yaml
│   └── provenance.md
└── manifest.yaml
```

**Golden 值来源**（按可信度）：年报手工 > 巨潮/交易所 > Wind/Choice；**禁止**用 AKShare 自身作 golden。

**自动化**：

```bash
uv run pytest tests/golden/ -m golden -v          # CI，freeze JSON
uv run pytest tests/golden/ -m golden --live -v   # 定期 live 回归
```

### 4.4 第 4 层：端到端与生产监控

| 手段 | 说明 |
|------|------|
| E2E golden | 扩展 `test_risk_api_e2e.py` 为数值对比 |
| Pipeline | `worker.py` analyze 后 DB vs golden |
| Reconcile CLI | `reconcile --ticker 600519.SH --year 2023` |
| 定期 Job | 每周 live reconcile + 告警 |
| Alpha | 先验四维 upstream，再验 composite |

---

## 5. 分模块验证优先级

| 优先级 | 模块 | 首要验证动作 |
|--------|------|-------------|
| P0 | Risk (M-Score indices) | Golden + audit_trail 复算 |
| P0 | ROIC / Invested Capital | 5 个 sector 各 1 个 golden |
| P1 | Valuation (WACC/FCF) | 子项 golden；DCF 总价 skip |
| P1 | Yield Gap | 600519 + 0700.HK |
| P1 | CapEx | expansion/contraction 样本 |
| P2 | Policy | 纯函数 + score 范围 |
| P2 | Alpha | upstream 全绿后再验 |

---

## 6. 容差与「正确」的定义

| 指标类型 | 容差建议 | 说明 |
|----------|----------|------|
| F-Score (0-9) | 0 | 必须精确 |
| ROIC 等比率 | ±1% relative | 税口径差异 |
| M-Score | ±0.05 absolute | 多 ratio 敏感 |
| FCF、NOPAT | ±2% relative | 折旧口径 |
| Policy / DCF 总价 | 不测精确值 | 主观或 LLM |

**判定标准**：P0 指标 100% 通过；P1 ≥ 90%；FAIL 须可由 audit_trail 解释根因。

---

## 7. 实施路线图

### Sprint 1（约 1 周）

- [ ] `metric_registry.yaml` + `tests/golden/manifest.yaml`
- [ ] 5 只代表股 2023 年报手工 golden
- [ ] `test_golden_metrics.py` + reconcile CLI 骨架
- [ ] CI：`pytest -m golden`

### Sprint 2（1～2 周）

- [ ] 12 样本 × 2022/2023；mapping 快照；跨源一致性
- [ ] Valuation/Yield audit_trail 可复算

### Sprint 3（持续）

- [ ] 每周 live job；新指标须 registry + ≥1 golden case
- [ ] 前端展示 audit_trail

---

## 8. 与现有架构衔接

| 构件 | 路径 | 用途 |
|------|------|------|
| audit_trail | `risk_service.py`, `roic_routes.py` | L2/L3 复算 |
| CalculationSandbox | `calculation_sandbox.py` | 与生产路径一致 |
| 纯函数 services | `services/*_service.py` | L1 与 E2E 解耦 |
| DEVELOPMENT_MODE | `external/data_service.py` | CI freeze / live 分离 |

`main.py` 七个 analyze router **无需修改**。

---

## 9. 最小可行第一步

1. **600519.SH 2023**：年报手工 M-Score、F-Score、ROIC、股息率 → `expected_metrics.yaml`
2. **1 个 golden test** + diff 报告
3. **ROIC / M-Score** audit_trail 可复算断言

---

## 10. 相关代码与文档索引

| 资源 | 路径 |
|------|------|
| API 入口 | `stockvaluefinder/stockvaluefinder/main.py` |
| 风险计算 | `stockvaluefinder/services/risk_service.py` |
| ROIC | `stockvaluefinder/services/roic_service.py` |
| 估值 | `stockvaluefinder/services/valuation_service.py` |
| 数据映射 | `stockvaluefinder/external/data_service.py` |
| M-Score 说明 | `doc/M-Score 与 F-Score：投资分析.md` |
| 估值模型 | `doc/AI-enhanced_valuation_model.md` |

---

## 11. 测试命令参考

```bash
cd stockvaluefinder
uv run pytest tests/unit/test_services/ -v
uv run pytest tests/golden/ -m golden -v
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023
```
