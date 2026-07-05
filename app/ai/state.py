"""
Typed state for the LangGraph workflows.

Two graphs are defined in this package:

  * `creation_graph`  — Feature 1: AI Ticket Creation Assistant
  * `detail_graph`    — Feature 2: AI Ticket Detail Summary

Each state is a `TypedDict` so LangGraph can do partial updates (a node
only needs to return the keys it actually changed). `operator.add`-style
reducers are used for the `errors` list so that multiple nodes can append
to it without clobbering each other's writes.
"""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, Optional

from typing_extensions import TypedDict

from app.ai.schemas import (
    CategoryPrediction,
    ConfidenceResult,
    FirstFixSuggestion,
    IntentAnalysis,
    PriorityPrediction,
    SimilarTicket,
    TicketSummary,
)


def _append_errors(left: list[str], right: list[str]) -> list[str]:
    return [*left, *right]


# ---------------------------------------------------------------------------
# Feature 1 — Ticket Creation Assistant
# ---------------------------------------------------------------------------

class TicketCreationState(TypedDict, total=False):
    # ---- input ----
    ticket_id: Optional[uuid.UUID]
    title: str
    description: str
    requester_id: Optional[uuid.UUID]

    # ---- validation ----
    is_valid: bool
    validation_errors: list[str]

    # ---- per-node outputs ----
    intent: IntentAnalysis
    category: CategoryPrediction
    priority: PriorityPrediction
    summary: TicketSummary
    first_fix: FirstFixSuggestion
    similar_tickets: list[SimilarTicket]
    confidence: ConfidenceResult
    embedding: list[float]

    # ---- bookkeeping ----
    errors: Annotated[list[str], _append_errors]
    trace_id: str





# ---------------------------------------------------------------------------
# Redesigned Summary Workflows
# ---------------------------------------------------------------------------

class TicketAssignmentState(TypedDict, total=False):
    ticket_id: uuid.UUID
    title: str
    description: str
    agent_name: str
    existing_summary: str
    summary: TicketSummary
    errors: Annotated[list[str], _append_errors]
    trace_id: str


class TicketResolutionState(TypedDict, total=False):
    ticket_id: uuid.UUID
    title: str
    description: str
    agent_name: str
    status: str
    resolution_details: str
    original_summary: str
    comments: list[dict[str, Any]]
    summary: TicketSummary
    errors: Annotated[list[str], _append_errors]
    trace_id: str

