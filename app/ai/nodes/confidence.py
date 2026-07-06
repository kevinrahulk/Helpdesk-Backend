"""Below `AI_LOW_CONFIDENCE_THRESHOLD`, `needs_human_review` is set so the
UI can flag the ticket for manual triage."""

from __future__ import annotations
from app.ai.config import get_ai_settings
from app.ai.schemas import ConfidenceResult
from app.ai.state import TicketCreationState

WEIGHTS = {
    "category": 0.35,
    "priority": 0.35,
    "similarity": 0.30,
}


async def evaluate_confidence(state: TicketCreationState) -> dict:
    settings = get_ai_settings()

    category = state.get("category")
    priority = state.get("priority")
    similar_tickets = state.get("similar_tickets") or []
    errors = state.get("errors") or []

    category_score = category.confidence if category else 0.0
    priority_score = priority.confidence if priority else 0.0
    similarity_score = max((t.similarity_score for t in similar_tickets), default=0.0)

    component_scores = {
        "category_confidence": round(category_score, 4),
        "priority_confidence": round(priority_score, 4),
        "similarity_quality": round(similarity_score, 4),
    }

    raw_confidence = (
        category_score * WEIGHTS["category"]
        + priority_score * WEIGHTS["priority"]
        + similarity_score * WEIGHTS["similarity"]
    )

    # Small penalty per upstream node error (capped so it can't go negative)
    error_penalty = min(0.15 * len(errors), raw_confidence)
    final_confidence = round(max(0.0, raw_confidence - error_penalty), 4)

    needs_review = final_confidence < settings.AI_LOW_CONFIDENCE_THRESHOLD

    reason_parts = [
        f"category confidence {category_score:.2f}",
        f"priority confidence {priority_score:.2f}",
        f"best similar-ticket match {similarity_score:.2f}",
    ]
    if errors:
        reason_parts.append(f"{len(errors)} upstream node error(s) reduced confidence")
    reason = "; ".join(reason_parts)

    result = ConfidenceResult(
        confidence=final_confidence,
        reason=reason,
        needs_human_review=needs_review,
        component_scores=component_scores,
    )
    return {"confidence": result}
