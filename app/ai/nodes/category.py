"""Node 3 — predict ticket category.

Implemented as a factory (`build_category_node(db)`) rather than a bare
function because it needs a request-scoped DB session to look up the
active category list. The graph builder (see app.ai.graphs.creation_graph)
closes over the session when constructing the graph per-request.
"""

from __future__ import annotations

import logging
from typing import Callable

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.llm.base import LLMInvocationError, StructuredLLM
from app.ai.prompts import render_prompt
from app.ai.schemas import CategoryPrediction
from app.ai.state import TicketCreationState
from app.models import TicketCategory

logger = logging.getLogger("app.ai.nodes.category")

_llm = StructuredLLM()


def build_category_node(db: Session) -> Callable[[TicketCreationState], dict]:
    async def predict_category(state: TicketCreationState) -> dict:
        categories = (
            db.query(TicketCategory.name)
            .filter(TicketCategory.is_active.is_(True))
            .order_by(TicketCategory.name)
            .all()
        )
        category_names = [c.name for c in categories] or ["General"]
        intent = state.get("intent")
        intent_summary = intent.primary_intent if intent else "unknown"

        try:
            result = await _llm.ainvoke_structured(
                system_prompt=render_prompt("category_prediction_system"),
                user_prompt=render_prompt(
                    "category_prediction_user",
                    title=state["title"],
                    description=state["description"],
                    intent_summary=intent_summary,
                    existing_categories="\n".join(f"- {c}" for c in category_names),
                ),
                output_model=CategoryPrediction,
                node_name="predict_category",
            )
            return {"category": result}
        except LLMInvocationError as exc:
            logger.error("predict_category failed: %s", exc)
            fallback = CategoryPrediction(
                category_name=category_names[0],
                confidence=0.0,
                alternative_categories=[],
                rationale="Fallback default — AI category prediction unavailable.",
            )
            return {"category": fallback, "errors": [f"predict_category: {exc}"]}

    return predict_category
