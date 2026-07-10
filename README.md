# 🎫 AI Helpdesk Ticket Assistant

An intelligent, AI-powered helpdesk ticketing system designed to streamline support operations. It coordinates automatic ticket categorization, sentiment analysis, urgency evaluation, SLA calculation, similar ticket retrieval, and automated resolution suggestion generation.

This repository contains the **FastAPI Backend API**, which orchestrates multiple AI agents using **LangGraph** and integrates with a **React-based Frontend Dashboard** built with Material UI and Redux.

---

## 🛠️ Architecture & Tech Stack

### Backend (Python/FastAPI)
*   **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) for high-performance, asynchronous REST and WebSocket communication.
*   **Database ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) with PostgreSQL, utilizing both `psycopg2` (synchronous) and `asyncpg` (asynchronous) sessions.
*   **AI Agent Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/) to construct stateful, multi-agent workflows.
*   **LLMs & Embedding Providers**: Integrated with **OpenAI / OpenRouter**, **Google Gemini**, and **Groq** APIs.
*   **Vector Database**: [pgvector](https://github.com/pgvector/pgvector) for semantic similarity searches on historical tickets (transparent Python fallback included).
*   **Real-time Layer**: [WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) for instantaneous client UI notification pushes.
*   **Authentication**: OAuth2 Password Flow with JWT tokens (`python-jose` and `passlib[bcrypt]`).

### Frontend (React/Vite)
*   **Core**: [React 18](https://react.dev/) + [Vite](https://vitejs.dev/) for rapid development builds.
*   **UI Components**: [Material UI (MUI) v6](https://mui.com/) and `@mui/icons-material`.
*   **State Management**: [Redux Toolkit](https://redux-toolkit.js.org/) for auth session, notification toast, and global ticket cache.
*   **Charts & Visualizations**: `@mui/x-charts` for SLA metrics, categories distribution, and agent performance dashboards.

---

## 🧭 Stateful AI Workflows (LangGraph Orchestration)

The system leverages three specialized LangGraph engines located in [`app/ai/graphs`](file:///Users/kevin/Desktop/Ticket_assistant/app/Backend/helpdesk/app/ai/graphs):

```mermaid
graph TD
    A[Employee Submits Ticket] --> B{Creation Graph}
    B -- Out of Scope --> C[Flag as Spamd/Spam End]
    B -- Valid IT Request --> D[Extract Category, Urgency & Sentiment]
    D --> E[Embed Description & Query Similar Tickets via pgvector]
    E --> F[Generate Automated Solution Suggestion]
    F --> G[Assign Agent & Trigger Assignment Graph]
    G --> H[Update Suggestion Dynamically on Agent Change]
    H --> I[Agent / Employee Comment Logs]
    I --> J{Resolution Graph}
    J --> K[Summarize Resolution & Set to Resolved State]
```

### 1. Creation Graph (`creation_graph.py`)
*   **Validation**: Assesses minimum length and checks formatting.
*   **Intent Filtering**: Classifies whether the ticket description is IT-related or out of scope.
*   **Ticket Analysis**: Extracts tags, maps categories, and scores sentiment and urgency.
*   **Vector Search**: Converts text to embeddings, queries pgvector to find similar historical tickets, and maps them to suggestions.
*   **Confidence Evaluation**: Checks LLM certainty; flags tickets for human agent review if confidence is low.
*   **Persistence**: Automatically saves AI summaries, suggestions, and embeddings.

### 2. Assignment Graph (`assignment_graph.py`)
*   Updates AI-generated summaries and suggested fixes dynamically when a ticket gets assigned or handed over to a different support agent.

### 3. Resolution Graph (`resolution_graph.py`)
*   Summarizes the resolution timeline and outcome based on comment history logs and the final agent resolution explanation.

---

## 📂 Project Structure

```
Ticket_assistant/
├── Backend/helpdesk/          # Backend FastAPI codebase
│   ├── app/
│   │   ├── ai/                # AI LangGraph workflows & configs
│   │   │   ├── graphs/        # Creation, assignment, and resolution graph controllers
│   │   │   ├── nodes/         # Graph nodes executing business & LLM tasks
│   │   │   ├── prompts/       # Structured prompt templates for LLMs
│   │   │   ├── services/      # Vector and AI inference services
│   │   │   └── tools/         # Internal LangChain search/utility tools
│   │   ├── models/            # SQLAlchemy database models
│   │   ├── routers/           # API routes (auth, users, tickets, ai, websocket)
│   │   ├── schemas/           # Pydantic request/response validation schemas
│   │   ├── services/          # Core business logic (SLA calculations, DB operations)
│   │   ├── auth.py            # JWT authentication utilities
│   │   ├── config.py          # Application configuration loader
│   │   ├── database.py        # SQLAlchemy engine & session pool creators
│   │   ├── main.py            # FastAPI main entrypoint
│   │   ├── seed.py            # System seed data (Roles, Admin Accounts)
│   │   └── websocket.py       # WebSocket connection manager
│   ├── migrate.py             # Script to add AI-specific database fields
│   ├── requirements.txt       # Python dependencies list
│   └── README.md              # Backend documentation
│
└── Frontend/                  # Frontend React/Vite codebase
    └── ai-helpdesk-assistant/
        ├── src/
        │   ├── api/           # Axios client configurations
        │   ├── components/    # Reusable UI widgets
        │   ├── context/       # WebSockets and dynamic context hooks
        │   ├── pages/         # Dashboard, Tickets, Reports, User Manager
        │   ├── slices/        # Redux Toolkit state slices
        │   └── theme/         # MUI design customization theme definitions
```

---

## 🚀 Setting Up the Project

### Prerequisites
*   **Python**: `3.10` or higher
*   **Node.js**: `18.x` or higher (with `npm` or `yarn`)
*   **PostgreSQL**: Installed and running

> [!TIP]
> **pgvector Setup**: 
> For the best search performance, enable `pgvector` on your PostgreSQL database by running:
> ```sql
> CREATE EXTENSION IF NOT EXISTS vector;
> ```
> *If pgvector is not installed on your PostgreSQL server, the backend will automatically fall back to an in-process, memory-based cosine-similarity scan.*

---

### Step 1: Backend Setup & Run

1.  **Navigate to the backend directory**:
    ```bash
    cd Backend/helpdesk
    ```

2.  **Configure environment variables**:
    Copy the example template file to create your active `.env`:
    ```bash
    cp .env.example .env
    ```
    Open `.env` and fill in the required parameters:
    *   `DATABASE_URL`: Connection string (e.g., `postgresql+psycopg2://user:pass@localhost:5432/helpdesk`)
    *   `DATABASE_URL_ASYNC`: Async connection string (e.g., `postgresql+asyncpg://user:pass@localhost:5432/helpdesk`)
    *   `SECRET_KEY`: JWT Signing Key (Generate using `python -c "import secrets; print(secrets.token_hex(32))"`)
    *   `AI_PRIMARY_PROVIDER`: Select your AI engine (`openai`, `gemini`, or `groq`)
    *   Add the corresponding API keys for the providers you configured (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `GROQ_API_KEY`).

3.  **Set up virtual environment & install requirements**:
    ```bash
    # Create the virtual environment
    python3 -m venv .venv

    # Activate the virtual environment (macOS/Linux)
    source .venv/bin/activate

    # On Windows run: .venv\Scripts\activate

    # Install Python requirements
    pip install -r requirements.txt
    ```

4.  **Database Migration & Initialization**:
    On server boot, FastAPI creates standard tables automatically. Execute these commands to add custom AI fields and seed roles/admin users:
    ```bash
    # Run the custom DB migration to append AI fields to the tickets table
    python migrate.py

    # Seed user roles and default administrator
    python -m app.seed
    ```

    > [!IMPORTANT]
    > **Seeded Administrator Credentials**:
    > *   **Username**: `admin@helpdesk.com`
    > *   **Password**: `Admin1234`

5.  **Run the Backend server**:
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
    *   **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
    *   **ReDoc Docs**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
    *   **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Step 2: Frontend Setup & Run

1.  **Navigate to the frontend directory**:
    ```bash
    cd ../../Frontend/ai-helpdesk-assistant
    ```

2.  **Install node dependencies**:
    ```bash
    npm install
    ```

3.  **Configure environment file**:
    Create a local `.env` configuration:
    ```bash
    echo "VITE_API_URL=http://localhost:8000" > .env
    ```

4.  **Start the React development server**:
    ```bash
    npm run dev
    ```
    *   The dashboard will boot and be accessible at: [http://localhost:5173](http://localhost:5173).

---

## 🔒 User Roles & Access Control

The app uses a 3-tier Role-Based Access Control (RBAC) model:

| Role | Target Users | Allowed Operations |
| :--- | :--- | :--- |
| **Employee** | Corporate Staff / End-Users | Create tickets, view ticket progress, post updates, read solutions. |
| **Agent** | IT Support Engineers | View ticket queue, assign tickets to self/others, apply AI suggested fixes, comment, resolve tickets. |
| **Admin** | System Administrators | Complete user administration, system parameter editing, priority/SLA custom configurations. |

---

## 📈 Monitoring & Health Metrics
*   **Prometheus Exposer**: The backend exposes real-time application metrics at `http://localhost:8000/metrics`.
*   **System Logs**: Application event and access logs are written to `app.log` in the backend root directory.

