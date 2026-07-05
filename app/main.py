"""
AI Helpdesk Ticket Assistant — FastAPI Application Entry Point
"""

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, status
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.ai.config import get_ai_settings
from app.database import SessionLocal, engine
from app.models import Base
from app.routers import auth, users, categories, tickets, dashboard, reports, ai, notifications, settings as settings_router, websocket

app_settings = get_settings()

# Loaded (and validated) at import time, deliberately *outside* the
# try/except in on_startup() below — a missing/misconfigured AI provider
# key must crash the process on boot, not be swallowed as a warning.
get_ai_settings()

# ---------------------------------------------------------------------------
# App instantiation
# ---------------------------------------------------------------------------

app = FastAPI(
    title=app_settings.APP_NAME,
    description=(
        "AI-powered helpdesk ticket management system.\n\n"
        "Roles: **employee** | **agent** | **admin**\n\n"
        "Default admin: `admin@helpdesk.local` / `Admin1234`"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins in dev; restrict in production
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "message": "An unexpected error occurred. Please try again later."},
    )

# ---------------------------------------------------------------------------
# Startup — create tables + seed
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    """Create all tables and seed reference data on first run."""
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            from app.seed import run_seed
            run_seed(db)
            # Seed default system settings
            from app.models import SystemSetting
            existing = db.query(SystemSetting).filter(
                SystemSetting.key == "employee_comments_enabled"
            ).first()
            if not existing:
                db.add(SystemSetting(key="employee_comments_enabled", value="true"))
                db.commit()

        # Capture the running event loop for ConnectionManager
        import asyncio
        from app.websocket import manager
        manager.loop = asyncio.get_running_loop()
    except Exception as exc:
        print(f"⚠️  Startup warning: {exc}")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(tickets.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(ai.router)
app.include_router(notifications.router)
app.include_router(settings_router.router)
app.include_router(websocket.router)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "app": app_settings.APP_NAME}


@app.get("/", tags=["System"])
def root():
    return {
        "message": f"Welcome to {app_settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
    }
