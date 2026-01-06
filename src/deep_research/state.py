"""Graph state definitions and data structures for the Deep Research agent."""

import operator
from typing import Annotated, Optional

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# =============================================================================
# STRUCTURED OUTPUTS - Used for LLM tool calling
# =============================================================================


class ConductResearch(BaseModel):
    """Tool call to delegate research on a specific topic."""

    research_topic: str = Field(
        description="The topic to research. Should be highly detailed (at least a paragraph).",
    )


class ResearchComplete(BaseModel):
    """Tool call to indicate research is complete."""

    pass


class Summary(BaseModel):
    """Research summary with key findings."""

    summary: str = Field(description="Concise summary of findings")
    key_excerpts: str = Field(description="Important quotes or data points")
    sources: list[str] = Field(default_factory=list, description="URLs of sources used")


class ClarifyWithUser(BaseModel):
    """Model for user clarification requests."""

    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        default="",
        description="A question to ask the user to clarify the research scope",
    )
    verification: str = Field(
        default="",
        description="Verification message that research will start after clarification.",
    )


class ResearchQuestion(BaseModel):
    """Research question and brief for guiding research."""

    research_brief: str = Field(
        description="A detailed research question to guide the research.",
    )


class Citation(BaseModel):
    """Structured citation for a source."""

    title: str = Field(description="Title of the source")
    url: str = Field(description="URL of the source")
    snippet: str = Field(default="", description="Relevant excerpt from the source")
    accessed_date: str = Field(default="", description="Date the source was accessed")


# =============================================================================
# REDUCER FUNCTIONS
# =============================================================================


def override_reducer(current_value, new_value):
    """Reducer that allows overriding values with special dict format."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


# =============================================================================
# STATE DEFINITIONS
# =============================================================================


class AgentInputState(MessagesState):
    """Input state - only contains messages from the user."""

    pass


class AgentState(MessagesState):
    """Main agent state for the deep research workflow."""

    # Research context
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: Optional[str] = None

    # Research outputs
    raw_notes: Annotated[list[str], override_reducer] = []
    notes: Annotated[list[str], override_reducer] = []
    citations: Annotated[list[Citation], operator.add] = []

    # Final output
    final_report: str = ""
    quality_score: Optional[float] = None


class SupervisorState(TypedDict):
    """State for the research supervisor that delegates to researchers."""

    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str
    notes: Annotated[list[str], override_reducer]
    research_iterations: int
    raw_notes: Annotated[list[str], override_reducer]


class ResearcherState(TypedDict):
    """State for individual researchers conducting focused research."""

    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer]
    citations: Annotated[list[Citation], operator.add]


class ResearcherOutputState(BaseModel):
    """Output state from individual researchers."""

    compressed_research: str
    raw_notes: list[str] = []
    citations: list[Citation] = []
