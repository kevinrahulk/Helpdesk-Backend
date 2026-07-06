from __future__ import annotations

from app.ai.state import TicketCreationState

MIN_TITLE_LENGTH = 5
MIN_DESCRIPTION_LENGTH = 15


async def validate_ticket_input(state: TicketCreationState) -> dict:
    errors: list[str] = []
    title = (state.get("title") or "").strip()
    description = (state.get("description") or "").strip()

    if len(title) < MIN_TITLE_LENGTH:
        errors.append(f"Title must be at least {MIN_TITLE_LENGTH} characters.")
    if len(description) < MIN_DESCRIPTION_LENGTH:
        errors.append(f"Description must be at least {MIN_DESCRIPTION_LENGTH} characters.")

    return {
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
    }


def route_after_validation(state: TicketCreationState) -> str:
    """Conditional edge: skip straight to END-style short-circuit on invalid input."""
    return "continue" if state.get("is_valid") else "halt"
