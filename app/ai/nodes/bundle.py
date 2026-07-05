"""Node 3 (merged) — category + priority + first_fix + summary in one call.

Replaces the previous predict_category / predict_priority /
generate_first_fix / generate_initial_summary chain for tickets that
analyze_intent has already confirmed are genuinely IT-related. Collapses
what used to be up to 3 sequential LLM round-trips (category+priority
concurrently, then first_fix, then summary) into a single call.

Tickets that are NOT IT-related (medical, legal, personal, etc.) never
reach this node at all — see `route_after_intent` in app.ai.nodes.intent
and `handle_out_of_scope_ticket` below, which short-circuits with a
fixed result and zero LLM calls. That split is deliberate: it keeps the
"never let the model invent a category for a non-IT problem" guarantee
enforced in code rather than resting on prompt instructions the model
could ignore inside a bigger merged call.
"""

from __future__ import annotations

import logging
from typing import Callable

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.llm.base import LLMInvocationError, StructuredLLM
from app.ai.nodes.new_summaries import clean_summary_text
from app.ai.prompts import render_prompt
from app.ai.schemas import (
    CategoryPrediction,
    FirstFixSuggestion,
    PriorityPrediction,
    TicketAnalysisBundle,
    TicketSummary,
)
from app.ai.state import TicketCreationState
from app.models import TicketCategory

logger = logging.getLogger("app.ai.nodes.bundle")

_llm = StructuredLLM()


def build_ticket_analysis_node(db: Session) -> Callable[[TicketCreationState], dict]:
    """Factory (needs `db` for the active-category lookup, same as the old category node)."""

    async def analyze_ticket(state: TicketCreationState) -> dict:
        categories = (
            db.query(TicketCategory.name)
            .filter(TicketCategory.is_active.is_(True))
            .order_by(TicketCategory.name)
            .all()
        )
        category_names = [c.name for c in categories] or ["General"]
        intent = state.get("intent")
        intent_summary = intent.primary_intent if intent else "unknown"
        urgency_signal = intent.urgency_signal if intent else "none"

        try:
            result = await _llm.ainvoke_structured(
                system_prompt=render_prompt("ticket_bundle_system"),
                user_prompt=render_prompt(
                    "ticket_bundle_user",
                    title=state["title"],
                    description=state["description"],
                    intent_summary=intent_summary,
                    urgency_signal=urgency_signal,
                    existing_categories="\n".join(f"- {c}" for c in category_names),
                ),
                output_model=TicketAnalysisBundle,
                node_name="analyze_ticket_bundle",
            )

            category = CategoryPrediction(
                category_name=result.category_name,
                confidence=result.category_confidence,
                alternative_categories=result.category_alternatives,
                rationale=result.category_rationale,
            )
            priority = PriorityPrediction(
                priority=result.priority,
                confidence=result.priority_confidence,
                rationale=result.priority_rationale,
            )
            first_fix = FirstFixSuggestion(
                steps=result.first_fix_steps,
                estimated_resolution_minutes=result.first_fix_estimated_resolution_minutes,
                requires_agent=result.first_fix_requires_agent,
            )
            summary = TicketSummary(summary=clean_summary_text(result.summary))

            return {
                "category": category,
                "priority": priority,
                "first_fix": first_fix,
                "summary": summary,
            }
        except LLMInvocationError as exc:
            logger.error("analyze_ticket_bundle failed: %s", exc)
            fallback_category = CategoryPrediction(
                category_name=category_names[0],
                confidence=0.0,
                alternative_categories=[],
                rationale="Fallback default — AI analysis unavailable.",
            )
            fallback_priority = PriorityPrediction(
                priority="medium",
                confidence=0.0,
                rationale="Fallback default — AI analysis unavailable.",
            )
            fallback_first_fix = FirstFixSuggestion(
                steps=[], estimated_resolution_minutes=None, requires_agent=True
            )
            fallback_summary = TicketSummary(summary=state.get("title", ""))
            return {
                "category": fallback_category,
                "priority": fallback_priority,
                "first_fix": fallback_first_fix,
                "summary": fallback_summary,
                "errors": [f"analyze_ticket_bundle: {exc}"],
            }

    return analyze_ticket


async def handle_out_of_scope_ticket(state: TicketCreationState) -> dict:
    """No-LLM-call path for tickets analyze_intent flagged as not IT-related.

    Fixed, deterministic result — never asks a model to improvise a
    category, priority, troubleshooting steps, or "awaiting assignment"
    framing for a problem (medical, legal, personal, etc.) this helpdesk
    doesn't handle.
    """
    category = CategoryPrediction(
        category_name="Not IT Support",
        confidence=1.0,
        alternative_categories=[],
        rationale=(
            "This request does not describe an IT/helpdesk issue, so it has not "
            "been assigned a support category. Please direct it to the "
            "appropriate department or professional."
        ),
    )
    priority = PriorityPrediction(
        priority="low",
        confidence=1.0,
        rationale="Not an IT/helpdesk issue, so no support priority applies.",
    )
    first_fix = FirstFixSuggestion(steps=[], estimated_resolution_minutes=None, requires_agent=False)
    summary = TicketSummary(
        summary=(
            "This request does not describe an IT/helpdesk issue and falls outside "
            "this system's scope. It has not been assigned a category, priority, or "
            "agent. Please contact the appropriate department or professional directly."
        )
    )
    return {"category": category, "priority": priority, "first_fix": first_fix, "summary": summary}
