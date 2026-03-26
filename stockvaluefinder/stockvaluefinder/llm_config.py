"""LLM client configuration and factory.

This module provides a flexible configuration system for using different LLM providers
including Anthropic Claude, DeepSeek, OpenAI-compatible APIs, and local models.

Environment Variables:
    LLM_PROVIDER: Primary LLM provider to use (anthropic, deepseek, openai, custom)
    LLM_MODEL: Model name to use (defaults to provider-specific defaults)
    LLM_API_KEY: API key for the provider (can also use provider-specific keys)
    LLM_BASE_URL: Custom base URL for OpenAI-compatible APIs
    LLM_TEMPERATURE: Default temperature for generation (0.0-1.0)
    LLM_MAX_TOKENS: Default max tokens for generation
"""

import logging
import os
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    CUSTOM = "custom"  # For OpenAI-compatible APIs
    LOCAL = "local"  # For local models (Ollama, LM Studio, etc.)


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM client."""

    provider: LLMProvider
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 60

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(f"Temperature must be between 0.0 and 1.0, got {self.temperature}")
        if self.max_tokens <= 0:
            raise ValueError(f"Max tokens must be positive, got {self.max_tokens}")

        # Validate base URL for custom providers
        if self.provider == LLMProvider.CUSTOM and not self.base_url:
            raise ValueError("base_url is required for custom provider")


@dataclass
class LLMSettings:
    """LLM settings manager with support for multiple providers."""

    # Default model names for each provider
    DEFAULT_MODELS: dict[LLMProvider, str] = field(default_factory=lambda: {
        LLMProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
        LLMProvider.DEEPSEEK: "deepseek-chat",
        LLMProvider.OPENAI: "gpt-4o",
        LLMProvider.CUSTOM: "gpt-3.5-turbo",  # Default for OpenAI-compatible APIs
        LLMProvider.LOCAL: "llama2",  # Default for Ollama
    })

    # Default base URLs for each provider
    DEFAULT_BASE_URLS: dict[LLMProvider, str | None] = field(default_factory=lambda: {
        LLMProvider.ANTHROPIC: None,  # Uses SDK default
        LLMProvider.DEEPSEEK: "https://api.deepseek.com",
        LLMProvider.OPENAI: None,  # Uses SDK default
        LLMProvider.CUSTOM: None,  # User must provide
        LLMProvider.LOCAL: "http://localhost:11434",  # Ollama default
    })

    @classmethod
    @lru_cache
    def get_config(cls, provider: str | None = None) -> LLMConfig:
        """Get LLM configuration from environment variables.

        Args:
            provider: LLM provider to use (defaults to LLM_PROVIDER env var)

        Returns:
            LLMConfig with settings from environment

        Raises:
            ValueError: If required configuration is missing or invalid

        Examples:
            >>> # Use default provider from env
            >>> config = LLMSettings.get_config()

            >>> # Override provider
            >>> config = LLMSettings.get_config("anthropic")

            >>> # Use with environment variables:
            >>> # export LLM_PROVIDER=anthropic
            >>> # export ANTHROPIC_API_KEY=sk-ant-...
            >>> # export LLM_MODEL=claude-3-5-sonnet-20241022
        """
        # Determine provider
        if provider:
            provider_enum = LLMProvider(provider)
        else:
            provider_str = os.getenv("LLM_PROVIDER", "anthropic").lower()
            provider_enum = LLMProvider(provider_str)

        # Get model name
        model = os.getenv("LLM_MODEL") or cls.DEFAULT_MODELS[provider_enum]

        # Get API key (try provider-specific key first, then generic)
        provider_key_map = {
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.CUSTOM: "LLM_API_KEY",
            LLMProvider.LOCAL: None,  # No API key needed for local models
        }

        env_key = provider_key_map[provider_enum]
        if env_key:
            api_key = os.getenv(env_key, "")
            if not api_key:
                # Try generic LLM_API_KEY as fallback
                api_key = os.getenv("LLM_API_KEY", "")
                if not api_key and provider_enum != LLMProvider.LOCAL:
                    raise ValueError(
                        f"API key not found. Set {env_key} or LLM_API_KEY environment variable."
                    )
        else:
            api_key = ""  # Local models don't need API key

        # Get base URL
        base_url = os.getenv("LLM_BASE_URL") or cls.DEFAULT_BASE_URLS[provider_enum]

        # Get generation parameters
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))
        timeout = int(os.getenv("LLM_TIMEOUT", "60"))

        config = LLMConfig(
            provider=provider_enum,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        logger.info(
            f"Initialized LLM config: provider={provider_enum}, "
            f"model={model}, temperature={temperature}"
        )

        return config

    @classmethod
    def reset_cache(cls) -> None:
        """Reset the configuration cache.

        Useful for testing or when environment variables change at runtime.
        """
        cls.get_config.cache_clear()


# Global convenience function
def get_llm_config(provider: str | None = None) -> LLMConfig:
    """Get LLM configuration - convenience function.

    Args:
        provider: LLM provider to use (defaults to LLM_PROVIDER env var)

    Returns:
        LLMConfig with settings from environment
    """
    return LLMSettings.get_config(provider)


__all__ = [
    "LLMProvider",
    "LLMConfig",
    "LLMSettings",
    "get_llm_config",
]
