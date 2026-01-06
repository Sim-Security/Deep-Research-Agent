# 🔬 Deep Research Agent

A powerful deep research agent built with **LangGraph** that conducts comprehensive research on any topic using parallel research execution, citation tracking, and intelligent synthesis.

![LangGraph](https://img.shields.io/badge/LangGraph-0.5.4-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- **🔄 Parallel Research** - Supervisor-researcher architecture with concurrent research execution
- **📝 Citation Tracking** - Automatic source attribution with URLs
- **🤖 Multi-Model Support** - Gemini, GPT, Claude via OpenRouter
- **🔍 Flexible Search** - DuckDuckGo (free) or Tavily (production)
- **📊 LangSmith Integration** - Full observability and tracing
- **🎨 Streamlit UI** - Interactive web interface for research

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/Sim-Security/Deep-Research-Agent.git
cd Deep-Research-Agent

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required:**
- `OPENROUTER_API_KEY` - Get at [openrouter.ai/keys](https://openrouter.ai/keys)

**Optional:**
- `TAVILY_API_KEY` - For production search ([tavily.com](https://tavily.com))
- `LANGCHAIN_API_KEY` - For tracing ([smith.langchain.com](https://smith.langchain.com))

### 3. Run the UI

```bash
streamlit run app.py
```

### 4. Or use LangGraph Studio

```bash
# Install LangGraph CLI
pip install "langgraph-cli[inmem]"

# Start the server
langgraph dev
```

Open [LangGraph Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024) in your browser.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Deep Research Workflow                    │
├─────────────────────────────────────────────────────────────┤
│  User Input → Clarify → Transform Brief → Supervisor        │
│                                              ↓              │
│                                    ┌─────────────────┐      │
│                                    │   Researcher 1  │      │
│                                    │   Researcher 2  │ ←─── │
│                                    │   Researcher N  │      │
│                                    └─────────────────┘      │
│                                              ↓              │
│                          Final Report ← Compress Findings   │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
deep-research-agent/
├── src/deep_research/
│   ├── __init__.py          # Package exports
│   ├── state.py              # State definitions
│   ├── configuration.py      # Pydantic config
│   ├── prompts.py            # Prompt templates
│   ├── utils.py              # Search & utilities
│   └── deep_researcher.py    # Main LangGraph workflow
├── app.py                    # Streamlit UI
├── langgraph.json            # LangGraph CLI config
├── pyproject.toml            # Dependencies
└── .env.example              # Environment template
```

## 🔧 Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RESEARCH_MODEL` | `google/gemini-2.0-flash-001` | LLM for research |
| `SEARCH_API` | `duckduckgo` | Search backend |
| `MAX_RESEARCHER_ITERATIONS` | `6` | Research depth |
| `MAX_CONCURRENT_RESEARCH_UNITS` | `5` | Parallel tasks |

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Inspired by [open_deep_research](https://github.com/langchain-ai/open_deep_research) by LangChain.
