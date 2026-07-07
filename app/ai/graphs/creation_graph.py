from __future__ import annotations
# pyrefly: ignore [missing-import]
from langgraph.graph import END, START, StateGraph
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from app.ai.nodes.bundle import build_ticket_analysis_node, handle_out_of_scope_ticket
from app.ai.nodes.confidence import evaluate_confidence
from app.ai.nodes.intent import analyze_intent, route_after_intent
from app.ai.nodes.similar_tickets import build_similar_tickets_node
from app.ai.nodes.validate import route_after_validation, validate_ticket_input
from app.ai.nodes.store_ai_data import (
    build_store_summary_node,
    build_store_first_fix_node,
    build_store_embedding_node,
    build_store_similar_tickets_node,
)
from app.ai.state import TicketCreationState


def build_creation_graph(db: Session, *, include_similar_tickets: bool = True):
    """Construct and compile the Feature 1 graph, bound to `db` for this request.
    `include_similar_tickets` controls whether the `find_similar_tickets`
    (LLM embedding + vector search) step runs at all.

    - Pre-submission preview (`POST /ai/ticket-suggestion`): the ticket
      doesn't exist in the DB yet, and "Analyze Issue" can be clicked
      repeatedly while the employee edits the description. Running the
      similar-ticket search on every click burns an LLM/embedding call
      each time for a result that isn't even shown in that panel. Callers
      building this preview pass `include_similar_tickets=False`.
    - Post-submission (background generation once the ticket has actually
      been created): similar tickets ARE generated here, exactly once, and
      persisted via `store_similar_tickets` so every later view (ticket
      detail page, `GET /ai/tickets/{id}/summary`) reads the cached column
      instead of re-invoking the LLM.
    """
    graph = StateGraph(TicketCreationState)

    graph.add_node("validate_ticket_input", validate_ticket_input)
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("analyze_ticket_bundle", build_ticket_analysis_node(db))
    graph.add_node("handle_out_of_scope_ticket", handle_out_of_scope_ticket)
    graph.add_node("evaluate_confidence", evaluate_confidence)

    graph.add_node("store_summary", build_store_summary_node(db))
    graph.add_node("store_first_fix", build_store_first_fix_node(db))
    graph.add_node("store_embedding", build_store_embedding_node(db))

    graph.add_edge(START, "validate_ticket_input")
    graph.add_conditional_edges(
        "validate_ticket_input",
        route_after_validation,
        {"continue": "analyze_intent", "halt": END},
    )
    graph.add_conditional_edges(
        "analyze_intent",
        route_after_intent,
        {"it_related": "analyze_ticket_bundle", "out_of_scope": "handle_out_of_scope_ticket"},
    )

    if include_similar_tickets:
        graph.add_node("find_similar_tickets", build_similar_tickets_node(db))
        graph.add_node("store_similar_tickets", build_store_similar_tickets_node(db))
        graph.add_edge("analyze_ticket_bundle", "find_similar_tickets")
        graph.add_edge("handle_out_of_scope_ticket", "find_similar_tickets")
        graph.add_edge("find_similar_tickets", "evaluate_confidence")
    else:
        graph.add_edge("analyze_ticket_bundle", "evaluate_confidence")
        graph.add_edge("handle_out_of_scope_ticket", "evaluate_confidence")

    graph.add_edge("evaluate_confidence", "store_summary")
    graph.add_edge("store_summary", "store_first_fix")

    if include_similar_tickets:
        graph.add_edge("store_first_fix", "store_similar_tickets")
        graph.add_edge("store_similar_tickets", "store_embedding")
    else:
        graph.add_edge("store_first_fix", "store_embedding")

    graph.add_edge("store_embedding", END)

    return graph.compile()
