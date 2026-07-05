# """Node 6 — generate first-fix troubleshooting steps."""

# from __future__ import annotations

# import logging

# from app.ai.llm.base import LLMInvocationError, StructuredLLM
# from app.ai.prompts import render_prompt
# from app.ai.schemas import FirstFixSuggestion
# from app.ai.state import TicketCreationState

# logger = logging.getLogger("app.ai.nodes.first_fix")

# _llm = StructuredLLM()


# async def generate_first_fix(state: TicketCreationState) -> dict:
#     category = state.get("category")
#     priority = state.get("priority")
#     intent = state.get("intent")

#     if intent is not None and not intent.is_it_related:
#         # Never generate self-service "fix" steps for a non-IT problem —
#         # that would mean an IT helpdesk bot giving medical/legal/personal
#         # advice, which is out of scope and potentially unsafe.
#         out_of_scope = FirstFixSuggestion(
#             steps=[],
#             estimated_resolution_minutes=None,
#             requires_agent=False,
#         )
#         return {"first_fix": out_of_scope}

#     try:
#         result = await _llm.ainvoke_structured(
#             system_prompt=render_prompt("first_fix_system"),
#             user_prompt=render_prompt(
#                 "first_fix_user",
#                 title=state["title"],
#                 description=state["description"],
#                 category=category.category_name if category else "Unknown",
#                 priority=priority.priority if priority else "medium",
#                 intent_summary=intent.primary_intent if intent else "unknown",
#             ),
#             output_model=FirstFixSuggestion,
#             node_name="generate_first_fix",
#         )
#         return {"first_fix": result}
#     except LLMInvocationError as exc:
#         logger.error("generate_first_fix failed: %s", exc)
#         fallback = FirstFixSuggestion(steps=[], estimated_resolution_minutes=None, requires_agent=True)
#         return {"first_fix": fallback, "errors": [f"generate_first_fix: {exc}"]}
