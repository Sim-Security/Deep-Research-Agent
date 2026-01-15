"""Configuration management for the Deep Research agent."""

import os
from enum import Enum
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class SearchAPI(Enum):
    """Available search API providers."""

    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"
    NONE = "none"


class Configuration(BaseModel):
    """Main configuration for the Deep Research agent.

    Supports OpenRouter for flexible model selection (Gemini, GPT, Claude, etc.)
    and DuckDuckGo (free) or Tavily (production) for search.
    """

    # =========================================================================
    # Model Configuration (OpenRouter format: provider/model-name)
    # =========================================================================

    summarization_model: str = Field(
        default="x-ai/grok-4.1-fast",
        description="Model for summarizing search results",
    )
    summarization_model_max_tokens: int = Field(
        default=8192,
        description="Max output tokens for summarization",
    )

    research_model: str = Field(
        default="x-ai/grok-4.1-fast",
        description="Model for conducting research",
    )
    research_model_max_tokens: int = Field(
        default=10000,
        description="Max output tokens for research",
    )

    compression_model: str = Field(
        default="x-ai/grok-4.1-fast",
        description="Model for compressing research findings",
    )
    compression_model_max_tokens: int = Field(
        default=8192,
        description="Max output tokens for compression",
    )

    final_report_model: str = Field(
        default="x-ai/grok-4.1-fast",
        description="Model for writing the final report",
    )
    final_report_model_max_tokens: int = Field(
        default=16000,
        description="Max output tokens for final report",
    )

    # =========================================================================
    # Search Configuration
    # =========================================================================

    search_api: SearchAPI = Field(
        default=SearchAPI.DUCKDUCKGO,
        description="Search API: 'duckduckgo' (free) or 'tavily' (production)",
    )

    max_search_results: int = Field(
        default=5,
        description="Maximum search results per query",
    )

    max_content_length: int = Field(
        default=50000,
        description="Max character length for webpage content before summarization",
    )

    # =========================================================================
    # Agent Behavior
    # =========================================================================

    allow_clarification: bool = Field(
        default=True,
        description="Whether to ask clarifying questions before starting research",
    )

    max_researcher_iterations: int = Field(
        default=6,
        description="Maximum research reflection iterations",
    )

    max_react_tool_calls: int = Field(
        default=10,
        description="Maximum tool calls in a single researcher step",
    )

    max_concurrent_research_units: int = Field(
        default=5,
        description="Maximum parallel research tasks",
    )

    max_structured_output_retries: int = Field(
        default=3,
        description="Retries for structured output parsing failures",
    )

    # =========================================================================
    # Observability
    # =========================================================================

    enable_langsmith: bool = Field(
        default=True,
        description="Enable LangSmith tracing",
    )

    langsmith_project: str = Field(
        default="deep-research-agent",
        description="LangSmith project name",
    )

    @classmethod
    def from_runnable_config(
        cls, config: RunnableConfig | None = None
    ) -> "Configuration":
        """Create Configuration from RunnableConfig or environment variables."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())

        values: dict[str, Any] = {}
        for field_name in field_names:
            # Check configurable first, then environment
            env_key = field_name.upper()
            value = configurable.get(field_name) or os.environ.get(env_key)
            if value is not None:
                # Handle enum conversion
                if field_name == "search_api" and isinstance(value, str):
                    value = SearchAPI(value.lower())
                values[field_name] = value

        return cls(**values)

    @classmethod
    def from_env(cls) -> "Configuration":
        """Create Configuration from environment variables only."""
        return cls.from_runnable_config(None)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
