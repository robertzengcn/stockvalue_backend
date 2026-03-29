"""LLM client factory for creating configured LLM instances.

This module provides factory functions for creating LLM clients from various
providers using a unified configuration system.

Usage:
    >>> from stockvaluefinder.llm_factory import create_llm
    >>>
    >>> # Create LLM using environment configuration
    >>> llm = create_llm()
    >>>
    >>> # Create LLM with specific provider
    >>> llm = create_llm(provider="deepseek")
    >>>
    >>> # Use with LangChain
    >>> from langchain.schema import HumanMessage
    >>> response = await llm.ainvoke([HumanMessage(content="Hello")])
"""

import logging
from typing import Any

from stockvaluefinder.llm_config import LLMConfig, LLMProvider, get_llm_config

logger = logging.getLogger(__name__)


def create_llm(provider: str | None = None, **kwargs: Any) -> Any:
    """Create an LLM client instance based on configuration.

    This function creates a LangChain-compatible LLM client configured
    according to environment variables or explicit parameters.

    Args:
        provider: LLM provider to use (defaults to LLM_PROVIDER env var)
        **kwargs: Additional parameters to override config

    Returns:
        LangChain BaseLanguageModel instance configured and ready to use

    Raises:
        ValueError: If required dependencies are missing or configuration is invalid
        ImportError: If required packages are not installed

    Examples:
        >>> # Use environment configuration
        >>> llm = create_llm()
        >>>
        >>> # Override temperature
        >>> llm = create_llm(temperature=0.7)
        >>>
        >>> # Use specific provider
        >>> llm = create_llm(provider="deepseek")

    Provider-Specific Notes:

        Anthropic (Claude):
            Requires: langchain-anthropic, anthropic
            Environment: ANTHROPIC_API_KEY

        DeepSeek:
            Requires: langchain-openai, openai
            Environment: DEEPSEEK_API_KEY, LLM_BASE_URL

        OpenAI:
            Requires: langchain-openai, openai
            Environment: OPENAI_API_KEY

        Custom (OpenAI-compatible):
            Requires: langchain-openai, openai
            Environment: LLM_API_KEY, LLM_BASE_URL

        Local (Ollama):
            Requires: langchain-community
            Environment: LLM_BASE_URL (optional, defaults to localhost:11434)
    """
    config = get_llm_config(provider)

    # Override config with explicit parameters
    temperature = kwargs.get("temperature", config.temperature)
    max_tokens = kwargs.get("max_tokens", config.max_tokens)
    timeout = kwargs.get("timeout", config.timeout)

    # Import provider-specific implementations
    if config.provider == LLMProvider.ANTHROPIC:
        return _create_anthropic_llm(
            config, temperature=temperature, max_tokens=max_tokens, timeout=timeout
        )
    elif config.provider == LLMProvider.DEEPSEEK:
        return _create_deepseek_llm(
            config, temperature=temperature, max_tokens=max_tokens, timeout=timeout
        )
    elif config.provider == LLMProvider.OPENAI:
        return _create_openai_llm(
            config, temperature=temperature, max_tokens=max_tokens, timeout=timeout
        )
    elif config.provider == LLMProvider.CUSTOM:
        return _create_custom_llm(
            config, temperature=temperature, max_tokens=max_tokens, timeout=timeout
        )
    elif config.provider == LLMProvider.LOCAL:
        return _create_local_llm(config, temperature=temperature, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")


def _create_anthropic_llm(
    config: LLMConfig, temperature: float, max_tokens: int, timeout: int
) -> Any:
    """Create Anthropic Claude LLM instance."""
    try:
        from langchain_anthropic import ChatAnthropic  # type: ignore[import-not-found]

        llm = ChatAnthropic(
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        logger.info(f"Created Anthropic LLM: {config.model}")
        return llm
    except ImportError as e:
        raise ImportError(
            "langchain-anthropic is required for Anthropic Claude. "
            "Install with: uv add langchain-anthropic"
        ) from e


def _create_deepseek_llm(
    config: LLMConfig, temperature: float, max_tokens: int, timeout: int
) -> Any:
    """Create DeepSeek LLM instance using OpenAI-compatible API."""
    try:
        from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]

        base_url = config.base_url or "https://api.deepseek.com"

        llm = ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        logger.info(f"Created DeepSeek LLM: {config.model} @ {base_url}")
        return llm
    except ImportError as e:
        raise ImportError(
            "langchain-openai is required for DeepSeek. "
            "Install with: uv add langchain-openai"
        ) from e


def _create_openai_llm(
    config: LLMConfig, temperature: float, max_tokens: int, timeout: int
) -> Any:
    """Create OpenAI GPT LLM instance."""
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        logger.info(f"Created OpenAI LLM: {config.model}")
        return llm
    except ImportError as e:
        raise ImportError(
            "langchain-openai is required for OpenAI. "
            "Install with: uv add langchain-openai"
        ) from e


def _create_custom_llm(
    config: LLMConfig, temperature: float, max_tokens: int, timeout: int
) -> Any:
    """Create custom OpenAI-compatible LLM instance."""
    try:
        from langchain_openai import ChatOpenAI

        if not config.base_url:
            raise ValueError("LLM_BASE_URL is required for custom provider")

        llm = ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        logger.info(f"Created custom LLM: {config.model} @ {config.base_url}")
        return llm
    except ImportError as e:
        raise ImportError(
            "langchain-openai is required for OpenAI-compatible APIs. "
            "Install with: uv add langchain-openai"
        ) from e


def _create_local_llm(config: LLMConfig, temperature: float, max_tokens: int) -> Any:
    """Create local LLM instance (Ollama)."""
    try:
        from langchain_community.llms import Ollama  # type: ignore[import-not-found]

        base_url = config.base_url or "http://localhost:11434"

        llm = Ollama(
            model=config.model,
            base_url=base_url,
            temperature=temperature,
        )
        logger.info(f"Created local Ollama LLM: {config.model} @ {base_url}")
        return llm
    except ImportError as e:
        raise ImportError(
            "langchain-community is required for local models (Ollama). "
            "Install with: uv add langchain-community"
        ) from e


__all__ = [
    "create_llm",
]
