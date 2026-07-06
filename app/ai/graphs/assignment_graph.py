# pyrefly: ignore [missing-import]
from langgraph.graph import END, START, StateGraph
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.ai.state import TicketAssignmentState
from app.ai.nodes.new_summaries import update_assignment_summary_node
from app.models import Ticket, User, TicketAISuggestion, SuggestionTypeEnum
from datetime import datetime, timezone


def build_assignment_graph(db: Session):
    graph = StateGraph(TicketAssignmentState)
    
    async def load_assignment_data(state: TicketAssignmentState) -> dict:
        ticket = db.get(Ticket, state["ticket_id"])
        if not ticket:
            return {"errors": ["Ticket not found"]}
        agent_name = "Unassigned"
        if ticket.assigned_to:
            agent = db.get(User, ticket.assigned_to)
            if agent:
                agent_name = agent.full_name or agent.email
        return {
            "title": ticket.title,
            "description": ticket.description,
            "agent_name": agent_name,
            "existing_summary": ticket.ai_summary or "",
        }
        
    async def store_assignment_summary(state: TicketAssignmentState) -> dict:
        ticket_id = state["ticket_id"]
        summary_obj = state.get("summary")
        if not summary_obj:
            return {"errors": ["No summary generated"]}
        
        summary_text = summary_obj.summary
        
        # 1. Update tickets table
        ticket = db.get(Ticket, ticket_id)
        if ticket:
            ticket.ai_summary = summary_text
            ticket.last_ai_updated_at = datetime.now(timezone.utc)
            db.commit()
            
        # 2. Update/Insert in ticket_ai_suggestions table
        existing_suggestion = (
            db.query(TicketAISuggestion)
            .filter(
                TicketAISuggestion.ticket_id == ticket_id,
                TicketAISuggestion.suggestion_type == SuggestionTypeEnum.summary,
            )
            .first()
        )
        if existing_suggestion:
            existing_suggestion.summary = summary_text
            existing_suggestion.suggested_reply = f"Assigned to {state.get('agent_name', 'agent')}."
            existing_suggestion.updated_at = datetime.now(timezone.utc)
        else:
            new_sug = TicketAISuggestion(
                ticket_id=ticket_id,
                suggestion_type=SuggestionTypeEnum.summary,
                summary=summary_text,
                suggested_reply=f"Assigned to {state.get('agent_name', 'agent')}.",
            )
            db.add(new_sug)
        db.commit()
        return {}

    graph.add_node("load_assignment_data", load_assignment_data)
    graph.add_node("update_assignment_summary", update_assignment_summary_node)
    graph.add_node("store_assignment_summary", store_assignment_summary)
    
    graph.add_edge(START, "load_assignment_data")
    graph.add_edge("load_assignment_data", "update_assignment_summary")
    graph.add_edge("update_assignment_summary", "store_assignment_summary")
    graph.add_edge("store_assignment_summary", END)
    
    return graph.compile()
