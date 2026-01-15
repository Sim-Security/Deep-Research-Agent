"""Main LangGraph implementation for the Deep Research agent.

This module defines the complete deep research workflow using LangGraph:
- Clarification node (optional)
- Research brief transformation
- Supervisor subgraph (delegates to researchers)
- Researcher subgraph (conducts focused research)
- Final report generation
"""

import asyncio
from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from deep_research.configuration import Configuration
from deep_research.prompts import (
    CLARIFY_WITH_USER_PROMPT,
    COMPRESS_RESEARCH_PROMPT,
    FINAL_REPORT_PROMPT,
    RESEARCHER_PROMPT,
    SUPERVISOR_PROMPT,
    TRANSFORM_TO_RESEARCH_BRIEF_PROMPT,
)
from deep_research.state import (
    AgentInputState,
    AgentState,
    ClarifyWithUser,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    ResearchQuestion,
    SupervisorState,
)
from deep_research.utils import (
    format_citations,
    format_search_results,
    get_model_token_limit,
    get_today_str,
    init_model,
    is_token_limit_exceeded,
    results_to_citations,
    search,
)

# =============================================================================
# MAIN WORKFLOW NODES
# =============================================================================


async def clarify_with_user(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["transform_to_brief", "__end__"]]:
    """Optionally ask the user for clarification before starting research.

    Args:
        state: Current agent state with user messages
        config: Runtime configuration

    Returns:
        Command to proceed to research or interrupt for clarification
    """
    configurable = Configuration.from_runnable_config(config)

    # Skip clarification if disabled
    if not configurable.allow_clarification:
        return Command(goto="transform_to_brief")

    # Get messages context
    messages = state.get("messages", [])
    messages_str = get_buffer_string(messages)

    # Format the clarification prompt
    prompt = CLARIFY_WITH_USER_PROMPT.format(
        messages=messages_str,
        date=get_today_str(),
    )

    # Get the model
    model = init_model(
        configurable.research_model,
        max_tokens=1024,
        temperature=0.0,
    )

    # Ask the model if clarification is needed
    try:
        structured_model = model.with_structured_output(ClarifyWithUser)
        response: ClarifyWithUser = await structured_model.ainvoke(
            [HumanMessage(content=prompt)]
        )

        if response.need_clarification:
            # Interrupt to get user clarification
            user_response = interrupt(
                {
                    "question": response.question,
                    "type": "clarification_needed",
                }
            )

            # Add user's clarification to messages
            return Command(
                goto="clarify_with_user",
                update={
                    "messages": [HumanMessage(content=user_response)],
                },
            )
        else:
            # Ready to proceed - add verification message
            return Command(
                goto="transform_to_brief",
                update={
                    "messages": [AIMessage(content=response.verification)],
                },
            )

    except Exception as e:
        # On error, proceed without clarification
        print(f"Clarification error: {e}")
        return Command(goto="transform_to_brief")


async def transform_to_brief(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """Transform user messages into a detailed research brief.

    Args:
        state: Current agent state with messages
        config: Runtime configuration

    Returns:
        Updated state with research_brief
    """
    configurable = Configuration.from_runnable_config(config)

    messages = state.get("messages", [])
    messages_str = get_buffer_string(messages)

    prompt = TRANSFORM_TO_RESEARCH_BRIEF_PROMPT.format(
        messages=messages_str,
        date=get_today_str(),
    )

    model = init_model(
        configurable.research_model,
        max_tokens=2048,
        temperature=0.0,
    )

    try:
        structured_model = model.with_structured_output(ResearchQuestion)
        response: ResearchQuestion = await structured_model.ainvoke(
            [HumanMessage(content=prompt)]
        )

        return {
            "research_brief": response.research_brief,
            "supervisor_messages": [HumanMessage(content=response.research_brief)],
        }

    except Exception as e:
        # Fallback: use raw messages as brief
        print(f"Transform error: {e}")
        return {
            "research_brief": messages_str,
            "supervisor_messages": [HumanMessage(content=messages_str)],
        }


# =============================================================================
# SUPERVISOR SUBGRAPH
# =============================================================================


async def supervisor(
    state: SupervisorState,
    config: RunnableConfig,
) -> Command[Literal["supervisor_tools", "__end__"]]:
    """Research supervisor that delegates to researcher agents.

    Args:
        state: Supervisor state with research brief and notes
        config: Runtime configuration

    Returns:
        Command with tool calls to conduct research or end
    """
    configurable = Configuration.from_runnable_config(config)

    # Check iteration limit
    iterations = state.get("research_iterations", 0)
    if iterations >= configurable.max_researcher_iterations:
        return Command(
            goto=END,
            update={
                "notes": state.get("notes", []),
            },
        )

    # Build supervisor prompt
    prompt = SUPERVISOR_PROMPT.format(
        date=get_today_str(),
        research_brief=state.get("research_brief", ""),
        max_iterations=configurable.max_researcher_iterations,
        max_concurrent=configurable.max_concurrent_research_units,
    )

    # Get model with tool binding
    model = init_model(
        configurable.research_model,
        max_tokens=configurable.research_model_max_tokens,
        temperature=0.0,
    )
    model_with_tools = model.bind_tools([ConductResearch, ResearchComplete])

    # Get supervisor messages
    supervisor_messages = state.get("supervisor_messages", [])

    # Invoke model
    try:
        response = await model_with_tools.ainvoke(
            [
                SystemMessage(content=prompt),
                *supervisor_messages,
            ]
        )

        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [response],
                "research_iterations": iterations + 1,
            },
        )

    except Exception as e:
        print(f"Supervisor error: {e}")
        return Command(goto=END)


async def supervisor_tools(
    state: SupervisorState,
    config: RunnableConfig,
) -> Command[Literal["supervisor", "__end__"]]:
    """Execute tool calls from the supervisor.

    Args:
        state: Supervisor state with tool calls
        config: Runtime configuration

    Returns:
        Command with tool results or end signal
    """
    configurable = Configuration.from_runnable_config(config)

    supervisor_messages = state.get("supervisor_messages", [])
    if not supervisor_messages:
        return Command(goto=END)

    most_recent = supervisor_messages[-1]
    if not isinstance(most_recent, AIMessage) or not most_recent.tool_calls:
        return Command(goto=END)

    tool_messages = []
    raw_notes = []

    # Check for ResearchComplete
    for tc in most_recent.tool_calls:
        if tc["name"] == "ResearchComplete":
            return Command(
                goto=END,
                update={"notes": state.get("notes", [])},
            )

    # Handle ConductResearch calls
    research_calls = [
        tc for tc in most_recent.tool_calls if tc["name"] == "ConductResearch"
    ]

    if research_calls:
        # Limit concurrent research
        allowed = research_calls[: configurable.max_concurrent_research_units]
        overflow = research_calls[configurable.max_concurrent_research_units :]

        # Execute research in parallel
        tasks = [
            researcher_subgraph.ainvoke(
                {
                    "researcher_messages": [
                        HumanMessage(content=tc["args"]["research_topic"])
                    ],
                    "research_topic": tc["args"]["research_topic"],
                    "tool_call_iterations": 0,
                },
                config,
            )
            for tc in allowed
        ]

        try:
            results = await asyncio.gather(*tasks)

            for result, tc in zip(results, allowed):
                compressed = result.get("compressed_research", "Error: Research failed")
                tool_messages.append(
                    ToolMessage(
                        content=compressed,
                        name=tc["name"],
                        tool_call_id=tc["id"],
                    )
                )
                raw_notes.extend(result.get("raw_notes", []))

        except Exception as e:
            print(f"Research execution error: {e}")
            for tc in allowed:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {e}",
                        name=tc["name"],
                        tool_call_id=tc["id"],
                    )
                )

        # Handle overflow
        for tc in overflow:
            tool_messages.append(
                ToolMessage(
                    content="Error: Max concurrent research limit reached",
                    name=tc["name"],
                    tool_call_id=tc["id"],
                )
            )

    return Command(
        goto="supervisor",
        update={
            "supervisor_messages": tool_messages,
            "raw_notes": raw_notes,
        },
    )


# Build supervisor subgraph
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
# Edges are handled by Command returns

supervisor_subgraph = supervisor_builder.compile()


# =============================================================================
# RESEARCHER SUBGRAPH
# =============================================================================


async def researcher(
    state: ResearcherState,
    config: RunnableConfig,
) -> Command[Literal["researcher_tools", "compress"]]:
    """Individual researcher agent that conducts focused research.

    Args:
        state: Researcher state with topic
        config: Runtime configuration

    Returns:
        Command with search tool calls or proceed to compression
    """
    configurable = Configuration.from_runnable_config(config)

    # Check iteration limit
    iterations = state.get("tool_call_iterations", 0)
    if iterations >= configurable.max_react_tool_calls:
        return Command(goto="compress")

    prompt = RESEARCHER_PROMPT.format(
        date=get_today_str(),
        research_topic=state.get("research_topic", ""),
    )

    model = init_model(
        configurable.research_model,
        max_tokens=configurable.research_model_max_tokens,
        temperature=0.0,
    )

    messages = state.get("researcher_messages", [])

    try:
        response = await model.ainvoke(
            [
                SystemMessage(content=prompt),
                *messages,
            ]
        )

        # Check if model wants to end research
        content = response.content.lower() if response.content else ""
        if "research complete" in content or iterations >= 2:
            return Command(
                goto="compress",
                update={"researcher_messages": [response]},
            )

        return Command(
            goto="researcher_tools",
            update={
                "researcher_messages": [response],
                "tool_call_iterations": iterations + 1,
            },
        )

    except Exception as e:
        print(f"Researcher error: {e}")
        return Command(goto="compress")


async def researcher_tools(
    state: ResearcherState,
    config: RunnableConfig,
) -> Command[Literal["researcher", "compress"]]:
    """Execute search for the researcher.

    Args:
        state: Researcher state
        config: Runtime configuration

    Returns:
        Command with search results
    """
    configurable = Configuration.from_runnable_config(config)

    topic = state.get("research_topic", "")

    # Perform search
    search_api = configurable.search_api.value
    results = await search(
        topic,
        search_api=search_api,
        max_results=configurable.max_search_results,
    )

    # Format results and create citations
    results_str = format_search_results(results)
    citations = results_to_citations(results)

    return Command(
        goto="researcher",
        update={
            "researcher_messages": [
                HumanMessage(content=f"Search Results:\n{results_str}")
            ],
            "raw_notes": [results_str],
            "citations": citations,
        },
    )


async def compress_research(
    state: ResearcherState,
    config: RunnableConfig,
) -> dict:
    """Compress raw research into a concise summary.

    Args:
        state: Researcher state with raw notes
        config: Runtime configuration

    Returns:
        Compressed research output
    """
    configurable = Configuration.from_runnable_config(config)

    raw_notes = state.get("raw_notes", [])
    raw_research = "\n\n".join(raw_notes)

    if not raw_research:
        return {
            "compressed_research": "No research findings.",
            "raw_notes": [],
        }

    prompt = COMPRESS_RESEARCH_PROMPT.format(raw_research=raw_research)

    model = init_model(
        configurable.compression_model,
        max_tokens=configurable.compression_model_max_tokens,
        temperature=0.0,
    )

    try:
        response = await model.ainvoke([HumanMessage(content=prompt)])
        return {
            "compressed_research": response.content,
            "raw_notes": raw_notes,
            "citations": state.get("citations", []),
        }

    except Exception as e:
        print(f"Compression error: {e}")
        return {
            "compressed_research": raw_research[:5000],
            "raw_notes": raw_notes,
        }


# Build researcher subgraph
researcher_builder = StateGraph(
    ResearcherState,
    output=ResearcherOutputState,
    config_schema=Configuration,
)
researcher_builder.add_node("researcher", researcher)
researcher_builder.add_node("researcher_tools", researcher_tools)
researcher_builder.add_node("compress", compress_research)
researcher_builder.add_edge(START, "researcher")
researcher_builder.add_edge("compress", END)

researcher_subgraph = researcher_builder.compile()


# =============================================================================
# FINAL REPORT GENERATION
# =============================================================================


async def final_report_generation(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """Generate the final comprehensive research report.

    Args:
        state: Agent state with all research findings
        config: Runtime configuration

    Returns:
        Final report in state
    """
    configurable = Configuration.from_runnable_config(config)

    notes = state.get("notes", [])
    raw_notes = state.get("raw_notes", [])
    findings = "\n\n".join(notes + raw_notes)

    messages = state.get("messages", [])
    messages_str = get_buffer_string(messages)

    prompt = FINAL_REPORT_PROMPT.format(
        research_brief=state.get("research_brief", ""),
        messages=messages_str,
        findings=findings,
        date=get_today_str(),
    )

    model = init_model(
        configurable.final_report_model,
        max_tokens=configurable.final_report_model_max_tokens,
        temperature=0.0,
    )

    max_retries = 3
    current_retry = 0
    current_findings = findings

    while current_retry <= max_retries:
        try:
            response = await model.ainvoke([HumanMessage(content=prompt)])

            # Add citations to report
            citations = state.get("citations", [])
            report = response.content
            if citations:
                report += "\n\n" + format_citations(citations)

            return {
                "final_report": report,
                "messages": [response],
                "notes": {"type": "override", "value": []},
                "raw_notes": {"type": "override", "value": []},
            }

        except Exception as e:
            if is_token_limit_exceeded(e, configurable.final_report_model):
                current_retry += 1
                # Truncate findings
                limit = get_model_token_limit(configurable.final_report_model)
                current_findings = current_findings[: limit * 2]
                prompt = FINAL_REPORT_PROMPT.format(
                    research_brief=state.get("research_brief", ""),
                    messages=messages_str[:2000],
                    findings=current_findings,
                    date=get_today_str(),
                )
            else:
                return {
                    "final_report": f"Error generating report: {e}",
                    "messages": [AIMessage(content="Report generation failed")],
                }

    return {
        "final_report": "Error: Max retries exceeded",
        "messages": [AIMessage(content="Report generation failed")],
    }


# =============================================================================
# BUILD MAIN WORKFLOW
# =============================================================================


deep_researcher_builder = StateGraph(
    AgentState,
    input=AgentInputState,
    config_schema=Configuration,
)

# Add nodes
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("transform_to_brief", transform_to_brief)
deep_researcher_builder.add_node("supervisor", supervisor_subgraph)
deep_researcher_builder.add_node("final_report", final_report_generation)

# Add edges
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("transform_to_brief", "supervisor")
deep_researcher_builder.add_edge("supervisor", "final_report")
deep_researcher_builder.add_edge("final_report", END)

# Compile the graph
deep_researcher = deep_researcher_builder.compile()

# Export for langgraph.json
__all__ = ["deep_researcher"]
