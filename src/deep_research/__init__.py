"""Package initialization for deep_research."""

from deep_research.configuration import Configuration, SearchAPI
from deep_research.state import (
    AgentInputState,
    AgentState,
    Citation,
    ClarifyWithUser,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    ResearchQuestion,
    Summary,
    SupervisorState,
)

__all__ = [
    # Configuration
    "Configuration",
    "SearchAPI",
    # State
    "AgentInputState",
    "AgentState",
    "SupervisorState",
    "ResearcherState",
    "ResearcherOutputState",
    # Structured Outputs
    "ConductResearch",
    "ResearchComplete",
    "ClarifyWithUser",
    "ResearchQuestion",
    "Summary",
    "Citation",
]
