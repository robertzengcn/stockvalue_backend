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
2. 是否存在存贷双高异常（高现金高负债）
3. 利润与现金流是否背离
4. 商誉风险是否过高
5. 综合风险等级的投资含义"""

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


# Type alias for prompt builder functions
PromptBuilder = Callable[[str, dict[str, Any]], tuple[str, str]]
