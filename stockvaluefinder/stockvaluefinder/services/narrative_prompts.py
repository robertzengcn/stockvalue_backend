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


def build_risk_prompt(ticker: str, result_data: dict[str, Any]) -> tuple[str, str]:
    """Build prompt for risk analysis narrative.

    Args:
        ticker: Stock code (e.g. '600519.SH')
        result_data: RiskScore.model_dump() output

    Returns:
        (system_prompt, user_prompt) tuple
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
6. 综合风险等级的投资含义"""

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
PromptBuilder = Callable[[str, dict[str, Any]], tuple[str, str]]
