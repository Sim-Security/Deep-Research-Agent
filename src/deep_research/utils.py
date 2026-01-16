"""Utility functions for the Deep Research agent."""

import json
import os
import re
from datetime import datetime
from typing import Any

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from deep_research.state import Citation

# =============================================================================
# DATE UTILITIES
# =============================================================================


def get_today_str() -> str:
    """Get today's date as a formatted string."""
    return datetime.now().strftime("%B %d, %Y")


def get_iso_date() -> str:
    """Get today's date in ISO format."""
    return datetime.now().strftime("%Y-%m-%d")


# =============================================================================
# SEARCH QUERY EXTRACTION
# =============================================================================


def extract_search_queries(content: str, fallback_topic: str = "") -> list[str]:
    """Extract search queries from LLM response.

    Looks for JSON block with search_queries array. Falls back to topic if not found.

    Args:
        content: LLM response content
        fallback_topic: Topic to use if no queries found

    Returns:
        List of search queries
    """
    if not content:
        return [fallback_topic] if fallback_topic else []

    # Try to find JSON block in markdown code fence
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            queries = data.get("search_queries", [])
            if queries and isinstance(queries, list):
                return [q for q in queries if q and isinstance(q, str)]
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r'\{[^{}]*"search_queries"\s*:\s*\[[^\]]+\][^{}]*\}', content)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            queries = data.get("search_queries", [])
            if queries and isinstance(queries, list):
                return [q for q in queries if q and isinstance(q, str)]
        except json.JSONDecodeError:
            pass

    # Fallback to topic
    return [fallback_topic] if fallback_topic else []


def filter_relevant_results(
    results: list[dict[str, Any]],
    topic: str,
    min_relevance_words: int = 2,
) -> list[dict[str, Any]]:
    """Filter search results for relevance to the topic.

    Uses simple keyword matching to filter out obviously irrelevant results.

    Args:
        results: List of search results
        topic: Research topic to match against
        min_relevance_words: Minimum topic words that must appear in result

    Returns:
        Filtered list of relevant results
    """
    if not results or not topic:
        return results

    # Extract meaningful words from topic (3+ chars, not common words)
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
                  'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been',
                  'would', 'could', 'should', 'what', 'when', 'where', 'which', 'who',
                  'will', 'with', 'this', 'that', 'from', 'they', 'been', 'have'}

    topic_words = set(
        word.lower() for word in re.findall(r'\b\w{3,}\b', topic.lower())
        if word.lower() not in stop_words
    )

    if not topic_words:
        return results

    filtered = []
    for result in results:
        # Combine title and snippet for matching
        text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()

        # Count how many topic words appear in the result
        matches = sum(1 for word in topic_words if word in text)

        # Keep if enough topic words appear
        if matches >= min(min_relevance_words, len(topic_words)):
            filtered.append(result)

    # If filtering removed everything, return top 2 original results
    if not filtered and results:
        return results[:2]

    return filtered


# =============================================================================
# MODEL INITIALIZATION
# =============================================================================


def get_api_key_for_model(model_name: str) -> str | None:
    """Get the appropriate API key for a model.

    Supports OpenRouter format (provider/model-name) and direct provider models.
    """
    # OpenRouter models
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ.get("OPENROUTER_API_KEY")

    # Direct provider keys as fallback
    model_lower = model_name.lower()
    if "gpt" in model_lower or "openai" in model_lower:
        return os.environ.get("OPENAI_API_KEY")
    elif "claude" in model_lower or "anthropic" in model_lower:
        return os.environ.get("ANTHROPIC_API_KEY")
    elif "gemini" in model_lower or "google" in model_lower:
        return os.environ.get("GOOGLE_API_KEY")

    return None


def init_model(
    model_name: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    **kwargs,
) -> BaseChatModel:
    """Initialize a chat model with OpenRouter or direct provider.

    Args:
        model_name: Model identifier (OpenRouter format: provider/model-name)
        max_tokens: Maximum output tokens
        temperature: Sampling temperature
        **kwargs: Additional model configuration

    Returns:
        Initialized chat model
    """
    api_key = get_api_key_for_model(model_name)

    # Check if using OpenRouter
    if os.environ.get("OPENROUTER_API_KEY"):
        return init_chat_model(
            model=model_name,
            model_provider="openai",  # OpenRouter uses OpenAI-compatible API
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

    # Direct provider
    provider = None
    if "/" in model_name:
        provider, model_name = model_name.split("/", 1)

    return init_chat_model(
        model=model_name,
        model_provider=provider,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )


# =============================================================================
# SEARCH FUNCTIONS
# =============================================================================


async def duckduckgo_search(
    query: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search using DuckDuckGo (free, no API key required).

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results with title, url, snippet
    """
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )
        return results
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
        return []


async def tavily_search(
    query: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search using Tavily API (production quality).

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        List of search results with title, url, snippet
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("TAVILY_API_KEY not set, falling back to DuckDuckGo")
        return await duckduckgo_search(query, max_results)

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=max_results)

        results = []
        for r in response.get("results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                }
            )
        return results
    except Exception as e:
        print(f"Tavily search error: {e}, falling back to DuckDuckGo")
        return await duckduckgo_search(query, max_results)


async def search(
    query: str,
    search_api: str = "duckduckgo",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Unified search function supporting multiple backends.

    Args:
        query: Search query
        search_api: "duckduckgo" or "tavily"
        max_results: Maximum number of results

    Returns:
        List of search results
    """
    if search_api.lower() == "tavily":
        return await tavily_search(query, max_results)
    else:
        return await duckduckgo_search(query, max_results)


def results_to_citations(
    results: list[dict[str, Any]],
) -> list[Citation]:
    """Convert search results to Citation objects."""
    return [
        Citation(
            title=r.get("title", "Unknown"),
            url=r.get("url", ""),
            snippet=r.get("snippet", ""),
            accessed_date=get_iso_date(),
        )
        for r in results
    ]


def format_search_results(results: list[dict[str, Any]]) -> str:
    """Format search results for LLM consumption."""
    if not results:
        return "No search results found."

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(
            f"[{i}] {r.get('title', 'No title')}\n"
            f"URL: {r.get('url', 'No URL')}\n"
            f"Snippet: {r.get('snippet', 'No snippet')}\n"
        )
    return "\n".join(formatted)


# =============================================================================
# WEB CONTENT FETCHING
# =============================================================================


async def fetch_webpage_content(
    url: str,
    max_length: int = 50000,
) -> str:
    """Fetch and extract text content from a webpage.

    Args:
        url: URL to fetch
        max_length: Maximum content length

    Returns:
        Extracted text content
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            from bs4 import BeautifulSoup
            from markdownify import markdownify as md

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Convert to markdown
            text = md(str(soup), heading_style="ATX")

            # Truncate if needed
            if len(text) > max_length:
                text = text[:max_length] + "\n\n[Content truncated...]"

            return text

    except Exception as e:
        return f"Error fetching {url}: {e}"


# =============================================================================
# TOKEN UTILITIES
# =============================================================================


# Approximate token limits for common models
MODEL_TOKEN_LIMITS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "gemini-2.0-flash": 1000000,
    "gemini-1.5-pro": 2000000,
    "gemini-1.5-flash": 1000000,
}


def get_model_token_limit(model_name: str) -> int:
    """Get the approximate token limit for a model."""
    # Strip provider prefix
    if "/" in model_name:
        model_name = model_name.split("/", 1)[1]

    # Check for partial matches
    model_lower = model_name.lower()
    for key, limit in MODEL_TOKEN_LIMITS.items():
        if key in model_lower:
            return limit

    # Default fallback
    return 8192


def is_token_limit_exceeded(error: Exception, model_name: str) -> bool:
    """Check if an error is due to token limit exceeded."""
    error_str = str(error).lower()
    token_keywords = ["token", "context", "length", "too long", "maximum"]
    return any(kw in error_str for kw in token_keywords)


# =============================================================================
# MESSAGE UTILITIES
# =============================================================================


def get_notes_from_tool_calls(messages: list) -> list[str]:
    """Extract notes from tool call responses in messages."""
    notes = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "ConductResearch":
                    notes.append(tc.get("args", {}).get("research_topic", ""))
    return notes


def format_citations(citations: list[Citation]) -> str:
    """Format citations as a markdown reference list."""
    if not citations:
        return ""

    lines = ["\n## References\n"]
    seen_urls = set()
    for i, c in enumerate(citations, 1):
        if c.url not in seen_urls:
            seen_urls.add(c.url)
            lines.append(f"{i}. [{c.title}]({c.url})")

    return "\n".join(lines)
