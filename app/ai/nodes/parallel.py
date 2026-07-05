# """Node — run independent Feature 1 nodes concurrently.

# `predict_category`, `predict_priority`, and `generate_summary` each make
# exactly one LLM call, and none of them depends on either of the other
# two — they only need `analyze_intent`'s output (or nothing at all, in
# `generate_summary`'s case). Running them as three separate serial graph
# edges means paying for three sequential LLM round-trips back-to-back.
# This node fires all three at once with `asyncio.gather` so the wall-clock
# cost is roughly the slowest of the three calls instead of the sum of all
# three, which is a meaningful chunk of the perceived latency on both
# Feature 1 endpoints.

# `generate_first_fix` is deliberately NOT included here — it depends on
# the category and priority predictions produced by this node, so it has
# to run after this node completes.
# """

# from __future__ import annotations

# import asyncio
# import logging
# from typing import Callable

# # pyrefly: ignore [missing-import]
# from sqlalchemy.orm import Session

# from app.ai.nodes.category import build_category_node
# from app.ai.nodes.priority import predict_priority
# from app.ai.state import TicketCreationState

# logger = logging.getLogger("app.ai.nodes.parallel")


# def build_parallel_prediction_node(db: Session) -> Callable[[TicketCreationState], dict]:
#     """Factory (needs `db` for the category node's category lookup)."""

#     predict_category = build_category_node(db)

#     async def predict_category_priority_summary(state: TicketCreationState) -> dict:
#         results = await asyncio.gather(
#             predict_category(state),
#             predict_priority(state),
#             return_exceptions=True,
#         ) 

#         merged: dict = {}
#         errors: list[str] = []
#         for result in results:
#             if isinstance(result, BaseException):
#                 # Each node already catches its own LLMInvocationError and
#                 # returns a fallback dict rather than raising, so this is a
#                 # last-resort safety net: one node blowing up unexpectedly
#                 # can't take the other two down with it.
#                 logger.error("parallel prediction node raised unexpectedly: %s", result)
#                 errors.append(f"parallel_prediction: {result}")
#                 continue
#             for key, value in result.items():
#                 if key == "errors":
#                     errors.extend(value)
#                 else:
#                     merged[key] = value

#         if errors:
#             merged["errors"] = errors
#         return merged

#     return predict_category_priority_summary
