"""
FastAPI router for LangSmith Observability Integration.
Exposes endpoints to configure tracing, fetch runs/traces, inspect spans, and view metrics.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from langsmith import Client

from app.ai.config import get_ai_settings
from app.auth import require_admin, require_agent_or_admin
from app.models import User
from app.schemas.common import APIResponse

logger = logging.getLogger("app.observability")
router = APIRouter(prefix="/observability", tags=["Observability"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ObservabilityConfigPayload(BaseModel):
    tracing_enabled: bool
    api_key: Optional[str] = None
    project: Optional[str] = "helpdesk-assistant"
    endpoint: Optional[str] = "https://api.smith.langchain.com"


class ObservabilityStatusResponse(BaseModel):
    tracing_enabled: bool
    connected: bool
    project: str
    endpoint: str
    has_api_key: bool
    error: Optional[str] = None


class TraceRunResponse(BaseModel):
    id: str
    name: str
    run_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    latency_ms: Optional[float] = None
    status: str
    error: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class TraceNodeResponse(BaseModel):
    id: str
    name: str
    run_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    latency_ms: Optional[float] = None
    status: str
    error: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    children: List[TraceNodeResponse] = []


class ObservabilityStatsResponse(BaseModel):
    total_runs: int
    success_count: int
    error_count: int
    success_rate_pct: float
    avg_latency_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    runs_by_day: Dict[str, int]
    latency_by_name: Dict[str, float]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def update_env_file(updates: Dict[str, str]) -> None:
    """Updates the .env file with the key-value pairs, maintaining file content."""
    # Find .env relative to this router file: helpdesk/app/routers/observability.py -> helpdesk/.env
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    processed_keys = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            try:
                key, val = stripped.split("=", 1)
                key = key.strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    processed_keys.add(key)
                    continue
            except ValueError:
                pass
        new_lines.append(line)

    for key, val in updates.items():
        if key not in processed_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def format_run_obj(run: Any) -> Dict[str, Any]:
    """Helper to convert a LangSmith Run into a clean dictionary representation."""
    latency = None
    if run.end_time and run.start_time:
        latency = round((run.end_time - run.start_time).total_seconds() * 1000, 1)

    status_str = "running"
    if run.end_time:
        status_str = "error" if run.error else "success"

    prompt_tokens = getattr(run, "prompt_tokens", None)
    completion_tokens = getattr(run, "completion_tokens", None)
    total_tokens = getattr(run, "total_tokens", None)

    # Check extra metadata if token usage attributes aren't populated directly
    if not total_tokens and getattr(run, "extra", None):
        metadata = run.extra.get("metadata", {})
        token_usage = metadata.get("token_usage", {})
        if token_usage:
            prompt_tokens = token_usage.get("prompt_tokens")
            completion_tokens = token_usage.get("completion_tokens")
            total_tokens = token_usage.get("total_tokens")

    return {
        "id": str(run.id),
        "name": run.name,
        "run_type": run.run_type,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "latency_ms": latency,
        "status": status_str,
        "error": run.error,
        "inputs": run.inputs,
        "outputs": run.outputs,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/status", response_model=APIResponse[ObservabilityStatusResponse])
def get_status(_: User = Depends(require_agent_or_admin)):
    """Check the configuration and connection status to LangSmith."""
    settings = get_ai_settings()
    tracing_enabled = settings.LANGCHAIN_TRACING_V2.lower() == "true"
    api_key = settings.LANGCHAIN_API_KEY
    project = settings.LANGCHAIN_PROJECT
    endpoint = settings.LANGCHAIN_ENDPOINT

    connected = False
    error = None

    if tracing_enabled and api_key:
        try:
            client = Client(api_url=endpoint, api_key=api_key)
            # Fetch projects to verify API key connection validity
            list(client.list_projects())
            connected = True
        except Exception as e:
            error = str(e)
            logger.warning("Failed to connect to LangSmith: %s", e)

    return APIResponse(
        success=True,
        message="LangSmith status retrieved",
        data=ObservabilityStatusResponse(
            tracing_enabled=tracing_enabled,
            connected=connected,
            project=project,
            endpoint=endpoint,
            has_api_key=bool(api_key),
            error=error,
        ),
    )


@router.post("/config", response_model=APIResponse[ObservabilityStatusResponse])
def save_config(
    payload: ObservabilityConfigPayload,
    _: User = Depends(require_admin),
):
    """Update LangSmith settings, persist them to .env, and update os.environ."""
    updates = {
        "LANGCHAIN_TRACING_V2": "true" if payload.tracing_enabled else "false",
        "LANGCHAIN_API_KEY": payload.api_key or "",
        "LANGCHAIN_PROJECT": payload.project or "helpdesk-assistant",
        "LANGCHAIN_ENDPOINT": payload.endpoint or "https://api.smith.langchain.com",
    }

    try:
        # 1. Update .env file
        update_env_file(updates)

        # 2. Update active env variables in current process
        for key, val in updates.items():
            os.environ[key] = val

        # 3. Clear cache of Settings function
        get_ai_settings.cache_clear()

        # Clear factory model caches so they re-instantiate using the new env settings
        from app.ai.llm.factory import get_chat_model, get_embeddings_model
        get_chat_model.cache_clear()
        get_embeddings_model.cache_clear()

        # Clear prompt response caches so new queries force actual LLM calls and generate new traces
        from app.ai.tools.cache import ai_cache
        if hasattr(ai_cache, "clear"):
            ai_cache.clear()

        # Validate the new connection
        connected = False
        error = None
        if payload.tracing_enabled and payload.api_key:
            try:
                client = Client(api_url=payload.endpoint, api_key=payload.api_key)
                list(client.list_projects())
                connected = True
            except Exception as e:
                error = str(e)
                logger.warning("Failed to connect to LangSmith with new keys: %s", e)

        return APIResponse(
            success=True,
            message="LangSmith settings updated successfully",
            data=ObservabilityStatusResponse(
                tracing_enabled=payload.tracing_enabled,
                connected=connected,
                project=payload.project,
                endpoint=payload.endpoint,
                has_api_key=bool(payload.api_key),
                error=error,
            ),
        )
    except Exception as e:
        logger.error("Failed to update LangSmith configuration: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {e}",
        ) from e


@router.get("/runs", response_model=APIResponse[List[TraceRunResponse]])
def list_runs(
    limit: int = 50,
    _: User = Depends(require_agent_or_admin),
):
    """Retrieve root runs from LangSmith for the configured project."""
    settings = get_ai_settings()
    tracing_enabled = settings.LANGCHAIN_TRACING_V2.lower() == "true"
    api_key = settings.LANGCHAIN_API_KEY
    project = settings.LANGCHAIN_PROJECT
    endpoint = settings.LANGCHAIN_ENDPOINT

    if not tracing_enabled or not api_key:
        return APIResponse(
            success=True,
            message="Tracing is disabled or API key is not configured.",
            data=[],
        )

    try:
        client = Client(api_url=endpoint, api_key=api_key)
        # Fetch root runs (e.g. initial graph chains/calls, not children spans)
        runs_list = list(
            client.list_runs(
                project_name=project,
                limit=limit,
                is_root=True,
            )
        )
        
        formatted_runs = []
        for r in runs_list:
            formatted_runs.append(TraceRunResponse.model_validate(format_run_obj(r)))
            
        return APIResponse(
            success=True,
            message="LangSmith runs list retrieved",
            data=formatted_runs,
        )
    except Exception as e:
        logger.error("Failed to fetch runs from LangSmith: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LangSmith connection error: {e}",
        ) from e


@router.get("/runs/{run_id}", response_model=APIResponse[TraceNodeResponse])
def get_run_details(
    run_id: UUID,
    _: User = Depends(require_agent_or_admin),
):
    """Retrieve execution span hierarchy for a specific run ID."""
    settings = get_ai_settings()
    api_key = settings.LANGCHAIN_API_KEY
    endpoint = settings.LANGCHAIN_ENDPOINT

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LangSmith API key is not configured.",
        )

    try:
        client = Client(api_url=endpoint, api_key=api_key)
        
        # Fetch all runs in this trace (descendants and root)
        all_runs = list(client.list_runs(trace_id=run_id))
        
        # If trace_id query is empty, fallback to parent_run_id children
        if not all_runs:
            root_run = client.read_run(run_id)
            child_runs = list(client.list_runs(parent_run_id=run_id))
            all_runs = [root_run] + child_runs
            
        root_run_obj = None
        descendants = []
        for r in all_runs:
            if str(r.id) == str(run_id):
                root_run_obj = r
            else:
                descendants.append(r)
                
        if not root_run_obj:
            root_run_obj = client.read_run(run_id)

        # Format the root run
        root_dict = format_run_obj(root_run_obj)
        root_dict["children"] = []
        
        # Add root to map for lookup
        id_map = {root_dict["id"]: root_dict}
        
        # Format descendants and add them to map
        for c in descendants:
            c_dict = format_run_obj(c)
            c_dict["children"] = []
            id_map[c_dict["id"]] = c_dict

        # Bind children to their parent
        for c in descendants:
            c_id = str(c.id)
            parent_id = str(c.parent_run_id) if c.parent_run_id else None
            
            if parent_id and parent_id in id_map:
                id_map[parent_id]["children"].append(id_map[c_id])
        
        # Sort children lists recursively by start time
        for item in id_map.values():
            item["children"].sort(key=lambda x: x["start_time"] or "")
            
        return APIResponse(
            success=True,
            message="Trace run details retrieved",
            data=TraceNodeResponse.model_validate(root_dict),
        )
    except Exception as e:
        logger.error("Failed to fetch run details for ID %s: %s", run_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading LangSmith run details: {e}",
        ) from e


@router.get("/stats", response_model=APIResponse[ObservabilityStatsResponse])
def get_stats(_: User = Depends(require_agent_or_admin)):
    """Fetch recent runs and aggregate statistics (success rate, latency, tokens)."""
    settings = get_ai_settings()
    tracing_enabled = settings.LANGCHAIN_TRACING_V2.lower() == "true"
    api_key = settings.LANGCHAIN_API_KEY
    project = settings.LANGCHAIN_PROJECT
    endpoint = settings.LANGCHAIN_ENDPOINT

    if not tracing_enabled or not api_key:
        return APIResponse(
            success=True,
            message="Tracing is disabled or API key is not configured.",
            data=ObservabilityStatsResponse(
                total_runs=0,
                success_count=0,
                error_count=0,
                success_rate_pct=0.0,
                avg_latency_ms=0.0,
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                runs_by_day={},
                latency_by_name={},
            ),
        )

    try:
        client = Client(api_url=endpoint, api_key=api_key)
        
        # Fetch last 100 runs (root runs)
        runs_list = list(
            client.list_runs(
                project_name=project,
                limit=100,
                is_root=True,
            )
        )
        
        total_runs = len(runs_list)
        success_count = 0
        error_count = 0
        total_latency = 0.0
        latency_count = 0
        
        prompt_tokens_sum = 0
        completion_tokens_sum = 0
        total_tokens_sum = 0

        runs_by_day = {}
        latency_sum_by_name = {}
        latency_count_by_name = {}

        for r in runs_list:
            formatted = format_run_obj(r)
            
            # Status
            if formatted["status"] == "success":
                success_count += 1
            elif formatted["status"] == "error":
                error_count += 1
                
            # Latency
            lat = formatted["latency_ms"]
            if lat is not None:
                total_latency += lat
                latency_count += 1
                
                # Group latency by name
                name = formatted["name"]
                latency_sum_by_name[name] = latency_sum_by_name.get(name, 0.0) + lat
                latency_count_by_name[name] = latency_count_by_name.get(name, 0) + 1
                
            # Tokens
            if formatted["prompt_tokens"]:
                prompt_tokens_sum += formatted["prompt_tokens"]
            if formatted["completion_tokens"]:
                completion_tokens_sum += formatted["completion_tokens"]
            if formatted["total_tokens"]:
                total_tokens_sum += formatted["total_tokens"]
                
            # Trend by day
            if r.start_time:
                day_str = r.start_time.strftime("%Y-%m-%d")
                runs_by_day[day_str] = runs_by_day.get(day_str, 0) + 1

        success_rate = (success_count / total_runs * 100.0) if total_runs > 0 else 0.0
        avg_latency = (total_latency / latency_count) if latency_count > 0 else 0.0

        # Calculate average latency by run name
        avg_latency_by_name = {}
        for name, total_lat in latency_sum_by_name.items():
            count = latency_count_by_name[name]
            avg_latency_by_name[name] = round(total_lat / count, 1)

        return APIResponse(
            success=True,
            message="LangSmith statistics aggregated",
            data=ObservabilityStatsResponse(
                total_runs=total_runs,
                success_count=success_count,
                error_count=error_count,
                success_rate_pct=round(success_rate, 1),
                avg_latency_ms=round(avg_latency, 1),
                total_prompt_tokens=prompt_tokens_sum,
                total_completion_tokens=completion_tokens_sum,
                total_tokens=total_tokens_sum,
                runs_by_day=runs_by_day,
                latency_by_name=avg_latency_by_name,
            ),
        )
    except Exception as e:
        logger.error("Failed to compile stats from LangSmith: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error compiling LangSmith statistics: {e}",
        ) from e
