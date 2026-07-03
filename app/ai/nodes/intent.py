"""Node 2 — analyze ticket intent.

Runs once and feeds its output into category/priority/first-fix nodes,
so those nodes don't each have to re-derive "what is this ticket even
about" from scratch.
"""

from __future__ import annotations

import logging

from app.ai.llm.base import LLMInvocationError, StructuredLLM
from app.ai.prompts import render_prompt
from app.ai.schemas import IntentAnalysis
from app.ai.state import TicketCreationState

logger = logging.getLogger("app.ai.nodes.intent")

_llm = StructuredLLM()


async def analyze_intent(state: TicketCreationState) -> dict:
    try:
        result = await _llm.ainvoke_structured(
            system_prompt=render_prompt("intent_analysis_system"),
            user_prompt=render_prompt(
                "intent_analysis_user",
                title=state["title"],
                description=state["description"],
            ),
            output_model=IntentAnalysis,
            node_name="analyze_intent",
        )
        return {"intent": result}
    except LLMInvocationError as exc:
        logger.error("analyze_intent failed: %s", exc)
        fallback = IntentAnalysis(
            primary_intent="unknown",
            key_symptoms=[],
            affected_system=None,
            urgency_signal="none",
            is_actionable=True,
        )
        return {"intent": fallback, "errors": [f"analyze_intent: {exc}"]}
