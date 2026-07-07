# AI Helpdesk Ticket Assistant - Backend API

An AI-powered helpdesk ticketing backend built with **FastAPI**, **SQLAlchemy**, and **LangGraph**. It coordinates automatic ticket categorization, sentiment analysis, urgency evaluation, similar ticket search, and automated resolution suggestion generation.

---

## 🛠️ Tech Stack & Architecture

- **FastAPI**: Modern, high-performance web framework for Python.
- **SQLAlchemy (ORM)** & **PostgreSQL**: Robust persistence layer with support for both synchronous (`psycopg2`) and asynchronous (`asyncpg`) database operations.
- **Alembic**: Database migrations.
- **LangGraph**: Workflow engine for stateful multi-agent and step-based AI orchestration.
- **LangChain Core & Community Ecosystem**:
  - Integration with **Groq** (`llama-3.3-70b-versatile`), **Gemini** (`gemini-2.5-flash`), and **OpenAI** / **OpenRouter** (`gpt-oss-20b`).
  - **pgvector**: High-performance PostgreSQL extension for semantic vector search (`text-embedding-3-small`) to retrieve similar historical tickets.
- **WebSockets**: Real-time notifications and UI updates.
- **JWT (OAuth2 with password flow)**: Security using `python-jose` and `passlib[bcrypt]`.

---

## 🧭 AI Workflows (LangGraph Orchestrations)

The backend features three specialized LangGraph engines located in [app/ai/graphs](file:///Users/kevin/Desktop/Ticket_assistant/app/Backend/helpdesk/app/ai/graphs):

```
       [Ticket Created/Suggested]
                   │
                   ▼
       ┌───────────────────────┐
       │   Creation Graph      │──(OutOfScope)──► [Flag & End]
       └───────────────────────┘
                   │
                   ▼ (Category, Urgency, Similar Tickets)
       ┌───────────────────────┐
       │   Assignment Graph    │◄─(Agent Assigned)
       └───────────────────────┘
                   │
                   ▼ (Real-time Live Summary Updates)
       ┌───────────────────────┐
       │   Resolution Graph    │◄─(Comments + Resolved State)
       └───────────────────────┘
                   │
                   ▼ (Final Resolved Summary)
```

1. **Ticket Creation Graph** (`creation_graph.py`):
   - **Validation**: Ensures minimum input length and basic formatting.
   - **Intent Filtering**: Classifies whether the ticket is IT-related or out of scope.
   - **Ticket Analysis**: Extracts tags, maps categories, and scores sentiment and urgency.
   - **Vector search**: Translates description to embeddings, queries pgvector to find similar historical tickets, and maps them to suggestions.
   - **Confidence Evaluation**: Calculates LLM confidence; triggers human agent review flags if confidence is low.
   - **Persistence**: Persists the summary, similar tickets, and embeddings to the DB.
2. **Assignment Graph** (`assignment_graph.py`):
   - Updates AI-generated summary and suggestions dynamically when a ticket gets assigned to a support agent.
3. **Resolution Graph** (`resolution_graph.py`):
   - Summarizes the resolution process based on agent/employee comment logs and the resolution explanation.

---

## 📂 Project Structure

```
Backend/helpdesk/
├── app/
│   ├── ai/                  # AI LangGraph workflows & configs
│   │   ├── graphs/          # Creation, assignment, and resolution graph states
│   │   ├── nodes/           # Graph nodes executing business & LLM logic
│   │   ├── prompts/         # Prompts templates for LLM agents
│   │   ├── services/        # Vector and AI inference services
│   │   └── tools/           # Internal LangChain tools
│   ├── models/              # SQLAlchemy database models
│   ├── routers/             # API routes (auth, users, tickets, ai, websocket)
│   ├── schemas/             # Pydantic request/response validations
│   ├── services/            # Custom application business logic
│   ├── auth.py              # JWT authentication utilities
│   ├── config.py            # Global system config
│   ├── database.py          # SQLAlchemy engine & session generators
│   ├── main.py              # FastAPI app instantiator & routes mount
│   ├── seed.py              # Idempotent DB seeder
│   └── websocket.py         # Real-time WebSocket connections manager
├── docs/                    # Architecture diagrams & documentation
├── migrate.py               # Database helper script for AI columns
└── requirements.txt         # Package dependencies
```

---

## ⚙️ Prerequisites

- **Python**: `3.10` or higher
- **PostgreSQL**: Installed and running (requires `pgvector` extension enabled on the database)

---

## 🚀 Getting Started

### 1. Set Up Environment Variables

Clone the repository and copy the environment template:
```bash
cp .env.example .env
```

Edit the `.env` file to configure:
- **`DATABASE_URL`**: Database connection string (e.g., `postgresql+psycopg2://user:pass@localhost:5432/dbname`)
- **`DATABASE_URL_ASYNC`**: Asynchronous DB URI (e.g., `postgresql+asyncpg://user:pass@localhost:5432/dbname`)
- **`SECRET_KEY`**: Run `python -c "import secrets; print(secrets.token_hex(32))"` to generate a secure secret.
- **AI Keys** (Specify values for your active provider):
  - `AI_PRIMARY_PROVIDER` ("groq", "openai", "gemini")
  - `GROQ_API_KEY` (if Groq is primary)
  - `GOOGLE_API_KEY` (if Gemini is primary)
  - `OPENAI_API_KEY` (if OpenAI is primary/fallback)

### 2. Configure a Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize & Seed Database

On process startup, FastAPI auto-creates database tables using `Base.metadata.create_all()`.
To seed system roles (`employee`, `agent`, `admin`) and the default admin account, run:

```bash
python -m app.seed
```

- **Default Admin Username**: `admin@helpdesk.com`
- **Default Admin Password**: `Admin1234`

To execute the manual script adding AI-specific columns to tickets:
```bash
python migrate.py
```

### 4. Run the API Server

Start the API server locally using `uvicorn`:

```bash
uvicorn app.main:app --reload --port 8000
```

- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Redoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)
