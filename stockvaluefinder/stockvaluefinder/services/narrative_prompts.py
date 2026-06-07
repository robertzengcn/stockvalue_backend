"""Prompt templates for LLM narrative generation.

Each builder returns a (system_prompt, user_prompt) tuple.
System prompts define the LLM role and output format.
User prompts inject structured analysis data into domain-specific templates.
"""

import json
from typing import Any, Callable

SYSTEM_PROMPT = """你是一位资深的价值投资分析师。你的任务是根据提供的定量分析数据，用中文撰写一段简洁专业的分析解读。

重要规则：
1. 你不得进行任何计算或修改数据，只解读已有的计算结果
2. 回复必须是纯JSON格式，不要包含任何其他文字
3. JSON结构必须严格如下：
{
  "summary": "一段200字以内的分析总结",
  "key_drivers": ["驱动因素1", "驱动因素2"],
  "risks": ["风险因素1", "风险因素2"]
}
4. key_drivers和risks各不超过3条
5. 使用专业但易懂的中文金融术语"""


def _serialize_data(data: dict[str, Any]) -> str:
    """Serialize analysis data to JSON string for prompt injection."""
    return json.dumps(data, ensure_ascii=False, default=str, indent=2)


def build_valuation_prompt(ticker: str, result_data: dict[str, Any]) -> tuple[str, str]:
    """Build prompt for DCF valuation narrative.

    Args:
        ticker: Stock code (e.g. '600519.SH')
        result_data: ValuationResult.model_dump() output

    Returns:
        (system_prompt, user_prompt) tuple
    """
    user_prompt = f"""请根据以下DCF估值分析数据，生成一段中文分析解读：

股票代码：{ticker}

分析数据：
{_serialize_data(result_data)}

请重点关注：
1. 当前价格与内在价值的对比
2. 安全边际是否充足
3. WACC水平及其合理性
4. 估值结论（低估/合理/高估）的投资含义"""

    return (SYSTEM_PROMPT, user_prompt)


def build_risk_prompt(
    ticker: str,
    result_data: dict[str, Any],
    pledge_data: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build prompt for risk analysis narrative.

    Args:
        ticker: Stock code (e.g. '600519.SH')
        result_data: RiskScore.model_dump() output
        pledge_data: Optional pledge risk data from PledgeRiskResult.model_dump().
            When None, no pledge section is added (backward compatible).

    Returns:
        (system_prompt, user_prompt) tuple
    """
    pledge_section = ""

    if pledge_data is not None:
        data_quality = pledge_data.get("data_quality", {})
        freshness = data_quality.get("freshness", "UNAVAILABLE")
        supported = pledge_data.get("supported", True)

        if not supported:
            # HK stocks: simple note, no risk assessment
            pledge_section = """
7. 股权质押：该股票为港股，港股不支持质押数据，无需分析质押风险。
"""
        elif freshness == "UNAVAILABLE":
            # NARR-03: explicitly state unavailable, forbid implying low risk
            pledge_section = """
7. 股权质押风险：质押数据不可得。重要约束：你只能说明"质押数据不可得"，不得暗示质押风险较低或较高，不得对质押风险做出任何推断。
"""
        else:
            # NARR-01: full pledge risk paragraph with structured data
            breakdown = pledge_data.get("risk_level_breakdown", {})
            company_risk = pledge_data.get("company_risk", {})
            holder_risk = pledge_data.get("holder_risk", {})
            closeout_risk = pledge_data.get("closeout_risk", {})

            closeout_note = ""
            safety_margin = closeout_risk.get("safety_margin")
            if safety_margin is not None:
                closeout_note = f"   - 平仓线安全距离: {safety_margin:.1f}%\n"
            # NARR-04: when safety_margin is null, omit closeout distance entirely

            pledge_section = f"""
7. 股权质押风险分析:
   - 最终风险等级: {breakdown.get("final_risk_level", "N/A")}
   - 公司质押比例: {company_risk.get("company_pledge_ratio", "N/A")}
   - 控股股东质押比例: {holder_risk.get("pledged_to_holding_ratio", "N/A")}
{closeout_note}
   重要约束（必须严格遵守）：
   - 你只能使用以上结构化字段中的质押数值，不得编造任何质押相关数字（NARR-02）
   - 如果平仓线安全距离未提供，请勿提及平仓线距离（NARR-04）
   - 质押相关分析必须完全基于上述数据，不得引入数据中不存在的数字或比例
"""

    user_prompt = f"""请根据以下风险分析数据，生成一段中文分析解读：

股票代码：{ticker}

分析数据：
{_serialize_data(result_data)}

请重点关注：
1. Beneish M-Score的数值及其含义（阈值-1.78，高于此值可能存在盈余操纵）
2. Piotroski F-Score（0-9分）及其代表的基本面质量变化
3. 是否存在存贷双高异常（高现金高负债）
4. 利润与现金流是否背离
5. 商誉风险是否过高
6. 综合风险等级的投资含义{pledge_section}"""

    return (SYSTEM_PROMPT, user_prompt)


def build_yield_prompt(ticker: str, result_data: dict[str, Any]) -> tuple[str, str]:
    """Build prompt for yield gap analysis narrative.

    Args:
        ticker: Stock code (e.g. '600519.SH')
        result_data: YieldGap.model_dump() output

    Returns:
        (system_prompt, user_prompt) tuple
    """
    user_prompt = f"""请根据以下股息收益率差分析数据，生成一段中文分析解读：

股票代码：{ticker}

分析数据：
{_serialize_data(result_data)}

请重点关注：
1. 税后股息率与无风险利率的对比
2. 收益率差（yield_gap）的正负及其含义
3. 相比持有国债或大额存单，持有该股票的收益优势或劣势
4. 投资建议的合理性"""

    return (SYSTEM_PROMPT, user_prompt)


DCF_EXPLANATION_SYSTEM_PROMPT = """你是一位资深的价值投资分析师和财务建模专家。你的任务是根据提供的DCF估值分析完整数据（包括审计轨迹），逐步解释内在价值是如何计算出来的。

重要规则：
1. 你不得进行任何计算或修改数据，只解读已有的计算结果和过程
2. 回复必须是纯JSON格式，不要包含任何其他文字
3. JSON结构必须严格如下：
{
  "step_by_step": "逐步展示DCF计算过程，包括每一步的具体数值（500字以内）",
  "data_inputs": "说明使用了哪些输入数据（当前价格、FCF、总股本、无风险利率等）及其来源",
  "wacc_explanation": "解释WACC是如何得出的，包括Rf、Beta、市场风险溢价的取值",
  "fcf_analysis": "分析FCF预测的方法论（两阶段增长模型），以及增长率的合理性评估",
  "reliability": "评估结果的可信度，指出主要的假设风险和数据局限性",
  "conclusion": "总结估值结论，当前价格与内在价值的关系，以及投资含义"
}
4. 每个字段内容使用专业但易懂的中文金融术语
5. 在step_by_step中，请详细列出每一步的具体数值"""


def build_dcf_explanation_prompt(
    ticker: str, result_data: dict[str, Any]
) -> tuple[str, str]:
    """Build prompt for step-by-step DCF calculation explanation.

    Args:
        ticker: Stock code (e.g. '600519.SH')
        result_data: Valuation result dict with audit_trail, dcf_params, etc.

    Returns:
        (system_prompt, user_prompt) tuple
    """
    user_prompt = f"""请根据以下DCF估值的完整计算数据（包含审计轨迹），逐步解释内在价值是如何计算出来的：

股票代码：{ticker}

完整分析数据（含audit_trail）：
{_serialize_data(result_data)}

请重点关注audit_trail中的每一步计算过程，详细解释：
1. 自由现金流（FCF）的起始值
2. 两阶段增长模型中每一年的FCF预测值
3. 每一年FCF的折现值和折现因子
4. 终端价值（Terminal Value）的计算
5. 终端价值的折现值
6. 企业价值（Enterprise Value）的汇总
7. 每股内在价值的计算
8. WACC的计算过程和各参数取值
9. 安全边际和估值水平的判断"""

    return (DCF_EXPLANATION_SYSTEM_PROMPT, user_prompt)


# Type alias for prompt builder functions
# Uses ... to allow optional params (e.g. pledge_data in build_risk_prompt)
PromptBuilder = Callable[..., tuple[str, str]]
