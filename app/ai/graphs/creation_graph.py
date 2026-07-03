"""
Graph construction — Feature 1: AI Ticket Creation Assistant.

    START
      │
      ▼
  validate_ticket_input ──(invalid)──▶ END
      │ (valid)
      ▼
  analyze_intent
      │
      ▼
  predict_category_priority_summary   (predict_category, predict_priority,
      │                                 generate_summary run concurrently
      │                                 via asyncio.gather — see
      │                                 app.ai.nodes.parallel)
      ▼
  generate_first_fix
      │
      ▼
  find_similar_tickets   (needs DB + embeddings)
      │
      ▼
  evaluate_confidence
      │
      ▼
     END

Each step is an independently-testable node (see app.ai.nodes). Nodes
that need a DB session are built as factories and closed over a
request-scoped `Session`, so the compiled graph itself holds no global
state and is safe to build fresh per request.
"""

from __future__ import annotations

# pyrefly: ignore [missing-import]
from langgraph.graph import END, START, StateGraph
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.nodes.confidence import evaluate_confidence
from app.ai.nodes.first_fix import generate_first_fix
from app.ai.nodes.intent import analyze_intent
# pyrefly: ignore [missing-import]
from app.ai.nodes.parallel import build_parallel_prediction_node
from app.ai.nodes.similar_tickets import build_similar_tickets_node
from app.ai.nodes.validate import route_after_validation, validate_ticket_input
from app.ai.nodes.store_ai_data import build_generate_embedding_node, build_store_summary_node, build_store_first_fix_node, build_store_embedding_node
from app.ai.nodes.new_summaries import generate_initial_summary_node
from app.ai.state import TicketCreationState


def build_creation_graph(db: Session):
    """Construct and compile the Feature 1 graph, bound to `db` for this request."""
    graph = StateGraph(TicketCreationState)

    graph.add_node("validate_ticket_input", validate_ticket_input)
    graph.add_node("analyze_intent", analyze_intent)
    # predict_category, predict_priority are
    # independent of each other (see app.ai.nodes.parallel) and run
    # concurrently via asyncio.gather instead of two serial edges.
    graph.add_node("predict_category_priority_summary", build_parallel_prediction_node(db))
    graph.add_node("generate_first_fix", generate_first_fix)
    graph.add_node("generate_initial_summary", generate_initial_summary_node)
    graph.add_node("find_similar_tickets", build_similar_tickets_node(db))
    graph.add_node("evaluate_confidence", evaluate_confidence)
    
    graph.add_node("generate_embedding", build_generate_embedding_node())
    graph.add_node("store_summary", build_store_summary_node(db))
    graph.add_node("store_first_fix", build_store_first_fix_node(db))
    graph.add_node("store_embedding", build_store_embedding_node(db))

    graph.add_edge(START, "validate_ticket_input")
    graph.add_conditional_edges(
        "validate_ticket_input",
        route_after_validation,
        {"continue": "analyze_intent", "halt": END},
    )
    graph.add_edge("analyze_intent", "predict_category_priority_summary")
    graph.add_edge("predict_category_priority_summary", "generate_first_fix")
    graph.add_edge("generate_first_fix", "generate_initial_summary")
    graph.add_edge("generate_initial_summary", "find_similar_tickets")
    graph.add_edge("find_similar_tickets", "evaluate_confidence")
    graph.add_edge("evaluate_confidence", "generate_embedding")
    graph.add_edge("generate_embedding", "store_summary")
    graph.add_edge("store_summary", "store_first_fix")
    graph.add_edge("store_first_fix", "store_embedding")
    graph.add_edge("store_embedding", END)

    return graph.compile()
