"""Node 4 — predict ticket priority."""

from __future__ import annotations

import logging

from app.ai.llm.base import LLMInvocationError, StructuredLLM
from app.ai.prompts import render_prompt
from app.ai.schemas import PriorityPrediction
from app.ai.state import TicketCreationState

logger = logging.getLogger("app.ai.nodes.priority")

_llm = StructuredLLM()


async def predict_priority(state: TicketCreationState) -> dict:
    intent = state.get("intent")
    urgency_signal = intent.urgency_signal if intent else "none"
    intent_summary = intent.primary_intent if intent else "unknown"

    if intent is not None and not intent.is_it_related:
        out_of_scope = PriorityPrediction(
            priority="low",
            confidence=1.0,
            rationale="Not an IT/helpdesk issue, so no support priority applies.",
        )
        return {"priority": out_of_scope}

    try:
        result = await _llm.ainvoke_structured(
            system_prompt=render_prompt("priority_prediction_system"),
            user_prompt=render_prompt(
                "priority_prediction_user",
                title=state["title"],
                description=state["description"],
                urgency_signal=urgency_signal,
                intent_summary=intent_summary,
            ),
            output_model=PriorityPrediction,
            node_name="predict_priority",
        )
        return {"priority": result}
    except LLMInvocationError as exc:
        logger.error("predict_priority failed: %s", exc)
        fallback = PriorityPrediction(
            priority="medium",
            confidence=0.0,
            rationale="Fallback default — AI priority prediction unavailable.",
        )
        return {"priority": fallback, "errors": [f"predict_priority: {exc}"]}
