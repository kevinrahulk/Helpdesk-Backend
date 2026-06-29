# AI Helpdesk Ticket Assistant — Backend API

FastAPI · SQLAlchemy 2.0 · PostgreSQL · JWT Auth  
**Phase 1: Full backend without AI** — AI endpoints are scaffolded and ready for Phase 2.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL running locally (or Docker)

### 2. Clone & install

```bash
cd helpdesk
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and SECRET_KEY at minimum
```

### 4. Create the database

```bash
# PostgreSQL
createdb helpdesk_db
```

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

On first startup the app will:
- `CREATE TABLE` for all models (idempotent)
- Seed roles: `employee`, `agent`, `admin`
- Create default admin: `admin@helpdesk.local` / `Admin1234`

### 6. Open API docs

```
http://localhost:8000/docs      ← Swagger UI
http://localhost:8000/redoc     ← ReDoc
```

---

## Project Structure

```
helpdesk/
├── app/
│   ├── main.py           ← FastAPI app, CORS, startup
│   ├── config.py         ← Settings (reads .env)
│   ├── database.py       ← Engine + get_db dependency
│   ├── models.py         ← SQLAlchemy ORM models
│   ├── schemas.py        ← Pydantic V2 request/response schemas
│   ├── auth.py           ← JWT + password hashing + role dependencies
│   ├── seed.py           ← Roles + default admin seeder
│   ├── routers/
│   │   ├── auth.py       ← /auth/*
│   │   ├── users.py      ← /users/* and /agents/*
│   │   ├── categories.py ← /categories/*
│   │   ├── tickets.py    ← /tickets/* (CRUD, status, comments, attachments)
│   │   ├── dashboard.py  ← /dashboard
│   │   ├── reports.py    ← /reports/*
│   │   └── ai.py         ← /ai/* (placeholder — ready for Phase 2)
│   └── services/
│       └── ticket_service.py  ← Business logic (SLA, status FSM, assignment)
├── requirements.txt
└── .env.example
```

---

## API Reference (36 endpoints)

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | ❌ | Login → returns JWT |
| POST | `/auth/logout` | ✅ | Logout (client drops token) |
| GET  | `/auth/profile` | ✅ | Current user profile |

**Login request:**
```json
{ "email": "admin@helpdesk.local", "password": "Admin1234" }
```
**Login response:**
```json
{
  "success": true,
  "message": "Login Successful",
  "data": {
    "access_token": "<JWT>",
    "user": { "id": "...", "full_name": "System Admin", "email": "...", "role": "admin" }
  }
}
```
All subsequent requests: `Authorization: Bearer <JWT>`

---

### User Management *(Admin only)*

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/users` | List users — filters: `role`, `is_active`, `search`, `page`, `page_size` |
| POST   | `/users` | Create employee account |
| POST   | `/agents` | Create support agent account |
| GET    | `/agents` | List agents with open ticket count (assignment panel) |
| GET    | `/users/{id}` | Get single user (admin = any; others = own) |
| PUT    | `/users/{id}` | Update name / email / role |
| PATCH  | `/users/{id}/status` | Activate or deactivate |

**Create user body:**
```json
{
  "full_name": "Jane Smith",
  "email": "jane@company.com",
  "password": "Pass1234",
  "role_id": "<uuid>",
  "is_active": true
}
```

---

### Ticket Categories *(Admin: write; All: read)*

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/categories` | List categories (`active_only=true` default) |
| POST   | `/categories` | Create category |
| GET    | `/categories/{id}` | Single category |
| PUT    | `/categories/{id}` | Update |
| DELETE | `/categories/{id}` | Soft-delete (sets `is_active=false`) |

---

### Tickets

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST   | `/tickets` | Employee, Admin | Create ticket |
| GET    | `/tickets` | All (scoped) | List tickets — filters: `status`, `priority`, `category_id`, `search`, `page`, `page_size` |
| GET    | `/tickets/{id}` | All (scoped) | Full detail with comments, logs, attachments |
| PATCH  | `/tickets/{id}` | Agent, Admin | Update title / description / category / priority |
| PATCH  | `/tickets/{id}/status` | Agent, Admin | Status transition |
| PATCH  | `/tickets/{id}/assign` | Admin | Assign/reassign to agent |
| GET    | `/tickets/{id}/logs` | All (scoped) | Status change audit trail |
| POST   | `/tickets/{id}/comments` | Agent, Admin | Add comment |
| GET    | `/tickets/{id}/comments` | All (scoped) | List comments (internal hidden from Employee) |
| PATCH  | `/tickets/{id}/comments/{cid}` | Agent, Admin | Edit comment |
| POST   | `/tickets/{id}/attachments` | All | Register attachment metadata (after S3 upload) |
| GET    | `/tickets/{id}/attachments` | All (scoped) | List attachments |

**Create ticket body:**
```json
{
  "title": "VPN not connecting after update",
  "description": "Since the latest Windows update I cannot connect to the company VPN...",
  "category_id": "<uuid or null>",
  "priority": "high",
  "ai_suggestion_id": "<uuid or null>"
}
```

**Status transition body:**
```json
{ "status": "in_progress", "reason": "Starting investigation" }
```

**Status lifecycle:**
```
open → in_progress → waiting_for_user → resolved → closed
                ↑_______________|           |
                        reopen ←-----------+
```

---

### Dashboard *(Role-scoped)*

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/dashboard` | Returns Employee / Agent / Admin stats based on JWT role |

---

### Reports *(Admin only)*

| Method | Endpoint | Query params | Description |
|--------|----------|-------------|-------------|
| GET    | `/reports/summary` | `date_from`, `date_to`, `priority`, `category_id` | Totals, avg resolution, SLA |
| GET    | `/reports/agent-performance` | `date_from`, `date_to` | Per-agent ticket counts + avg hours |
| GET    | `/reports/sla` | `date_from`, `date_to` | SLA compliance |
| GET    | `/reports/ticket-volume` | `groupby` (day/week/month), `date_from`, `date_to` | Volume chart data |

---

### AI Assistant *(Phase 2 placeholder)*

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST   | `/ai/ticket-suggestion` | Employee | Pre-creation suggestions (stub) |
| GET    | `/ai/tickets/{id}/summary` | Agent, Admin | Ticket insight panel (stub) |

These return stub responses now. In Phase 2, replace the function bodies in `app/routers/ai.py` with real AI provider calls.

---

## Role Access Summary

| Endpoint group | Employee | Agent | Admin |
|---|---|---|---|
| Auth (login/profile) | ✅ | ✅ | ✅ |
| User management | ❌ | ❌ | ✅ |
| Categories (read) | ✅ | ✅ | ✅ |
| Categories (write) | ❌ | ❌ | ✅ |
| Create ticket | ✅ | ❌ | ✅ |
| View own tickets | ✅ | ❌ | ✅ |
| View assigned tickets | ❌ | ✅ | ✅ |
| View all tickets | ❌ | ❌ | ✅ |
| Update ticket / status | ❌ | ✅ (assigned) | ✅ |
| Assign ticket | ❌ | ❌ | ✅ |
| Add comments | ❌ (read-only) | ✅ | ✅ |
| Internal comments | ❌ hidden | ✅ | ✅ |
| Reports | ❌ | ❌ | ✅ |
| AI suggestions | ✅ (create) | view | view |
| AI summary | ❌ | ✅ | ✅ |

---

## Phase 2 — AI Integration Guide

To wire in the AI provider, edit `app/routers/ai.py`:

### `POST /ai/ticket-suggestion`
1. Receive `title` + `description`
2. Sanitize / truncate inputs
3. Call AI provider (OpenAI, Anthropic, etc.)
4. Parse response → `suggested_category`, `suggested_priority`, `first_fix[]`, `similar_tickets[]`, `confidence_score`
5. Persist a `TicketAISuggestion` row with `suggestion_type='creation'` and `ticket_id` set once the ticket is created
6. Return `suggestion_id` to the frontend for inclusion in `TicketCreate.ai_suggestion_id`

### `GET /ai/tickets/{id}/summary`
1. Load full ticket + recent comments
2. Build a prompt summarizing the ticket
3. Call AI provider → `summary`, `root_cause`, `suggested_reply`, `similar_tickets[]`
4. Persist as `TicketAISuggestion` with `suggestion_type='summary'`
5. Return the suggestion (check for existing before regenerating)

### Graceful degradation (FR-AI-005)
Wrap AI calls in try/except. On failure, return the stub/empty response already in place — the frontend must handle `null` fields gracefully.

---

## SLA Configuration

Edit `.env` or `app/config.py`:

| Priority | Default SLA |
|----------|-------------|
| critical | 4 hours |
| high | 8 hours |
| medium | 24 hours |
| low | 72 hours |

SLA due date is auto-computed at ticket creation.

---

## Security Notes

- Passwords hashed with **bcrypt** via `passlib`
- JWT signed with **HS256**; set `SECRET_KEY` to a 32+ byte random value in production
- Deactivated users are rejected at the auth layer on every request
- No hard deletes anywhere — employees and categories use soft-delete
- Internal comments are filtered at the API layer, never sent to employees
