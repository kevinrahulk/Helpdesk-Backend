from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session
from app.ai.state import TicketResolutionState
from app.ai.nodes.new_summaries import generate_resolution_summary_node
from app.models import Ticket, User, TicketComment, TicketStatusLog, TicketAISuggestion, SuggestionTypeEnum
from datetime import datetime, timezone


def build_resolution_graph(db: Session):
    graph = StateGraph(TicketResolutionState)
    
    async def load_resolution_data(state: TicketResolutionState) -> dict:
        ticket = db.get(Ticket, state["ticket_id"])
        if not ticket:
            return {"errors": ["Ticket not found"]}
            
        agent_name = "Unassigned"
        if ticket.assigned_to:
            agent = db.get(User, ticket.assigned_to)
            if agent:
                agent_name = agent.full_name or agent.email
                
        # Find comments
        comments = (
            db.query(TicketComment)
            .filter(TicketComment.ticket_id == state["ticket_id"])
            .order_by(TicketComment.created_at.asc())
            .all()
        )
        comments_list = []
        for c in comments:
            author_name = "Unknown"
            author = db.get(User, c.author_id)
            if author:
                author_name = author.full_name or author.email
            comments_list.append({
                "author_name": author_name,
                "body": c.body,
                "is_internal": c.is_internal,
                "created_at": c.created_at.isoformat(),
            })
            
        # Get resolution details from status log
        resolution_log = (
            db.query(TicketStatusLog)
            .filter(
                TicketStatusLog.ticket_id == state["ticket_id"],
                TicketStatusLog.to_status == "resolved"
            )
            .order_by(TicketStatusLog.changed_at.desc())
            .first()
        )
        resolution_details = resolution_log.reason if resolution_log else "None"
        
        return {
            "title": ticket.title,
            "description": ticket.description,
            "agent_name": agent_name,
            "status": ticket.status.value,
            "resolution_details": resolution_details,
            "original_summary": ticket.ai_summary or "",
            "comments": comments_list,
        }
        
    async def store_resolution_summary(state: TicketResolutionState) -> dict:
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
            existing_suggestion.suggested_reply = "Resolved. No further action required."
            existing_suggestion.updated_at = datetime.now(timezone.utc)
        else:
            new_sug = TicketAISuggestion(
                ticket_id=ticket_id,
                suggestion_type=SuggestionTypeEnum.summary,
                summary=summary_text,
                suggested_reply="Resolved. No further action required.",
            )
            db.add(new_sug)
        db.commit()
        return {}

    graph.add_node("load_resolution_data", load_resolution_data)
    graph.add_node("generate_resolution_summary", generate_resolution_summary_node)
    graph.add_node("store_resolution_summary", store_resolution_summary)
    
    graph.add_edge(START, "load_resolution_data")
    graph.add_edge("load_resolution_data", "generate_resolution_summary")
    graph.add_edge("generate_resolution_summary", "store_resolution_summary")
    graph.add_edge("store_resolution_summary", END)
    
    return graph.compile()
