"""Streamlit UI for the Deep Research Agent.

Interactive web interface for conducting deep research with real-time progress tracking.
"""

import asyncio
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for premium look
st.markdown(
    """
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%);
    }
    
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        color: #a0a0b0;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .research-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        backdrop-filter: blur(10px);
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .status-running {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
        color: white;
    }
    
    .status-complete {
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
        color: white;
    }
    
    .citation-link {
        color: #667eea;
        text-decoration: none;
    }
    
    .citation-link:hover {
        text-decoration: underline;
    }
</style>
""",
    unsafe_allow_html=True,
)


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "research_status" not in st.session_state:
        st.session_state.research_status = None
    if "final_report" not in st.session_state:
        st.session_state.final_report = None
    if "config" not in st.session_state:
        st.session_state.config = {}


def render_sidebar():
    """Render the configuration sidebar."""
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")

        # API Keys Section
        with st.expander("🔑 API Keys", expanded=True):
            openrouter_key = st.text_input(
                "OpenRouter API Key",
                value=os.environ.get("OPENROUTER_API_KEY", ""),
                type="password",
                help="Get your key at openrouter.ai/keys",
            )
            if openrouter_key:
                os.environ["OPENROUTER_API_KEY"] = openrouter_key

            tavily_key = st.text_input(
                "Tavily API Key (Optional)",
                value=os.environ.get("TAVILY_API_KEY", ""),
                type="password",
                help="For production search. Get at tavily.com",
            )
            if tavily_key:
                os.environ["TAVILY_API_KEY"] = tavily_key

            langsmith_key = st.text_input(
                "LangSmith API Key",
                value=os.environ.get("LANGCHAIN_API_KEY", ""),
                type="password",
                help="For tracing. Get at smith.langchain.com",
            )
            if langsmith_key:
                os.environ["LANGCHAIN_API_KEY"] = langsmith_key
                os.environ["LANGCHAIN_TRACING_V2"] = "true"

        # Model Configuration
        with st.expander("🧠 Model Settings"):
            model = st.selectbox(
                "Research Model",
                [
                    "x-ai/grok-4.1-fast",
                    "anthropic/claude-sonnet-4",
                    "openai/gpt-4o",
                    "google/gemini-2.0-flash-001",
                ],
                index=0,
            )
            st.session_state.config["research_model"] = model

            max_iterations = st.slider(
                "Max Research Iterations",
                min_value=1,
                max_value=10,
                value=6,
            )
            st.session_state.config["max_researcher_iterations"] = max_iterations

        # Search Configuration
        with st.expander("🔍 Search Settings"):
            search_api = st.radio(
                "Search API",
                ["DuckDuckGo (Free)", "Tavily (Production)"],
                index=0,
            )
            st.session_state.config["search_api"] = (
                "duckduckgo" if "DuckDuckGo" in search_api else "tavily"
            )

            max_results = st.slider(
                "Results per Search",
                min_value=3,
                max_value=10,
                value=5,
            )
            st.session_state.config["max_search_results"] = max_results

        st.markdown("---")
        st.markdown("### 📊 Session Info")
        st.markdown(f"**Messages:** {len(st.session_state.messages)}")
        if st.session_state.research_status:
            st.markdown(f"**Status:** {st.session_state.research_status}")


def render_message(role: str, content: str):
    """Render a chat message."""
    if role == "user":
        st.markdown(
            f"""
        <div style="display: flex; justify-content: flex-end; margin: 1rem 0;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        color: white; padding: 1rem 1.5rem; border-radius: 20px 20px 5px 20px;
                        max-width: 80%;">
                {content}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
        <div style="display: flex; justify-content: flex-start; margin: 1rem 0;">
            <div style="background: rgba(255, 255, 255, 0.08); 
                        color: #e0e0e0; padding: 1rem 1.5rem; border-radius: 20px 20px 20px 5px;
                        max-width: 80%; border: 1px solid rgba(255, 255, 255, 0.1);">
                {content}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )


async def run_research(topic: str):
    """Run the deep research workflow."""
    try:
        from deep_research.deep_researcher import deep_researcher

        # Build config
        config = {
            "configurable": {
                "research_model": st.session_state.config.get(
                    "research_model", "x-ai/grok-4.1-fast"
                ),
                "search_api": st.session_state.config.get("search_api", "duckduckgo"),
                "max_researcher_iterations": st.session_state.config.get(
                    "max_researcher_iterations", 6
                ),
                "max_search_results": st.session_state.config.get(
                    "max_search_results", 5
                ),
            }
        }

        # Run the graph
        st.session_state.research_status = "🔄 Researching..."

        result = await deep_researcher.ainvoke(
            {"messages": [HumanMessage(content=topic)]},
            config,
        )

        st.session_state.final_report = result.get(
            "final_report", "No report generated."
        )
        st.session_state.research_status = "✅ Complete"

        return result

    except Exception as e:
        st.session_state.research_status = f"❌ Error: {str(e)}"
        return None


def render_report(report: str):
    """Render the final research report."""
    st.markdown("### 📄 Research Report")

    # Download buttons
    col1, col2 = st.columns([1, 5])
    with col1:
        st.download_button(
            label="📥 Download MD",
            data=report,
            file_name=f"research_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
        )

    # Display report
    st.markdown(report)


def main():
    """Main application entry point."""
    init_session_state()

    # Header
    st.markdown(
        '<h1 class="main-header">🔬 Deep Research Agent</h1>', unsafe_allow_html=True
    )
    st.markdown(
        '<p class="sub-header">Powered by LangGraph • Grok • LangSmith</p>',
        unsafe_allow_html=True,
    )

    # Render sidebar
    render_sidebar()

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        # Chat interface
        st.markdown("### 💬 Research Query")

        # Display previous messages
        for msg in st.session_state.messages:
            render_message(msg["role"], msg["content"])

        # Input form
        with st.form("research_form", clear_on_submit=True):
            topic = st.text_area(
                "What would you like to research?",
                placeholder="e.g., Latest advancements in LangGraph agentic patterns 2024-2025",
                height=100,
            )

            submitted = st.form_submit_button(
                "🚀 Start Research",
                use_container_width=True,
            )

            if submitted and topic:
                st.session_state.messages.append({"role": "user", "content": topic})

                with st.spinner("🔬 Conducting deep research..."):
                    result = asyncio.run(run_research(topic))

                if result:
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": "Research complete! See the report below.",
                        }
                    )
                    st.rerun()

    with col2:
        # Status panel
        st.markdown("### 📊 Status")
        if st.session_state.research_status:
            st.info(st.session_state.research_status)
        else:
            st.info("Ready to research")

    # Display final report
    if st.session_state.final_report:
        st.markdown("---")
        render_report(st.session_state.final_report)

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666; font-size: 0.85rem;">
            Built with ❤️ using LangGraph, Streamlit, and Grok
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
