# 🔬 Deep Research Agent

A powerful deep research agent built with **LangGraph** that conducts comprehensive research on any topic using parallel research execution, citation tracking, and intelligent synthesis.

![LangGraph](https://img.shields.io/badge/LangGraph-0.5.4-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)
![CI](https://github.com/Sim-Security/Deep-Research-Agent/actions/workflows/ci.yml/badge.svg)
![CD](https://github.com/Sim-Security/Deep-Research-Agent/actions/workflows/cd.yml/badge.svg)

## ✨ Features

- **🔄 Parallel Research** - Supervisor-researcher architecture with concurrent research execution
- **📝 Citation Tracking** - Automatic source attribution with URLs
- **🤖 Multi-Model Support** - Gemini, GPT, Claude via OpenRouter
- **🔍 Tavily Search** - Production-quality research results (recommended over DuckDuckGo)
- **📊 LangSmith Integration** - Full observability and tracing
- **🎨 Streamlit UI** - Interactive web interface for research
- **🐳 Docker Ready** - Containerized deployment with multi-stage builds
- **⚙️ CI/CD Pipeline** - Automated testing, linting, and Docker image publishing

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
- `TAVILY_API_KEY` - **Strongly recommended** for quality results ([tavily.com](https://tavily.com), 1000 free searches/month)

**Optional:**
- `LANGCHAIN_API_KEY` - For tracing ([smith.langchain.com](https://smith.langchain.com))

> ⚠️ **Note:** DuckDuckGo is available as a fallback but returns poor results for technical queries. **Use Tavily for production research.**

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

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# Build and run
docker compose up --build

# Access at http://localhost:8501
```

### Pull Pre-built Image

```bash
# Pull from GitHub Container Registry
docker pull ghcr.io/sim-security/deep-research-agent:latest

# Run with environment variables
docker run -p 8501:8501 \
  -e OPENROUTER_API_KEY=your_key \
  -e TAVILY_API_KEY=your_key \
  ghcr.io/sim-security/deep-research-agent:latest
```

### Development Mode

```bash
# Run with hot reload (mounts source code)
docker compose --profile dev up dev
```

### Docker Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                      │
├─────────────────────────────────────────────────────────┤
│  Python 3.11-slim (minimal base image)                  │
│  ├── /opt/venv (isolated dependencies)                  │
│  ├── /app/src (application code)                        │
│  └── Non-root user (security)                           │
├─────────────────────────────────────────────────────────┤
│  Exposed: 8501 (Streamlit)                              │
│  Healthcheck: /_stcore/health                           │
└─────────────────────────────────────────────────────────┘
```

## ⚙️ CI/CD Pipeline

This project includes automated GitHub Actions workflows:

### Continuous Integration (CI)

Runs on every push and pull request:

| Job | Description |
|-----|-------------|
| **Lint** | Ruff linter + formatter check |
| **Type Check** | mypy static analysis |
| **Test** | pytest with timeout |
| **Docker Build** | Verify container builds |
| **Security** | Trivy vulnerability scan |

### Continuous Deployment (CD)

Runs on merge to main and version tags:

| Step | Description |
|------|-------------|
| **Build** | Multi-platform (amd64, arm64) |
| **Push** | GitHub Container Registry |
| **Attest** | Build provenance |

### Status Badges

- CI: ![CI](https://github.com/Sim-Security/Deep-Research-Agent/actions/workflows/ci.yml/badge.svg)
- CD: ![CD](https://github.com/Sim-Security/Deep-Research-Agent/actions/workflows/cd.yml/badge.svg)

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
├── .github/workflows/
│   ├── ci.yml                # Continuous Integration
│   └── cd.yml                # Continuous Deployment
├── app.py                    # Streamlit UI
├── Dockerfile                # Container definition
├── docker-compose.yml        # Orchestration config
├── langgraph.json            # LangGraph CLI config
├── pyproject.toml            # Dependencies
└── .env.example              # Environment template
```

## 🔧 Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `RESEARCH_MODEL` | `x-ai/grok-4.1-fast` | LLM for research |
| `SEARCH_API` | `tavily` | Search backend (**use tavily**, duckduckgo is poor quality) |
| `MAX_RESEARCHER_ITERATIONS` | `6` | Research depth |
| `MAX_CONCURRENT_RESEARCH_UNITS` | `5` | Parallel tasks |

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

Inspired by [open_deep_research](https://github.com/langchain-ai/open_deep_research) by LangChain.
