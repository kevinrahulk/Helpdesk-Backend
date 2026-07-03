import logging
import re
from app.ai.llm.base import LLMInvocationError, StructuredLLM
from app.ai.prompts import render_prompt
from app.ai.schemas import TicketSummary

logger = logging.getLogger("app.ai.nodes.new_summaries")
_llm = StructuredLLM()


def clean_summary_text(text: str) -> str:
    if not text:
        return text
    # Clean up trailing word count / meta comments / braces
    # Matches patterns like " } (Word count: 170)" or " (Word count: 170) " or " (170 words) "
    cleaned = re.sub(
        r"\s*\}?\s*\(\s*(?:Word\s*count\s*:\s*\d+|\d+\s*words?)\s*\)\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Also clean up trailing braces or parentheses
    cleaned = cleaned.strip().rstrip("}").strip()
    return cleaned


async def generate_initial_summary_node(state: dict) -> dict:
    title = state.get("title", "")
    description = state.get("description", "")
    category = state.get("category")
    priority = state.get("priority")
    first_fix = state.get("first_fix")
    
    category_name = category.category_name if category else "Unknown"
    priority_val = priority.priority if priority else "medium"
    
    # We descriptive-summarize the first fix steps if available, without numbered list.
    first_fix_str = "None"
    if first_fix and first_fix.steps:
        first_fix_str = ", ".join(first_fix.steps)
        
    try:
        result = await _llm.ainvoke_structured(
            system_prompt=render_prompt("initial_summary_system"),
            user_prompt=render_prompt(
                "initial_summary_user",
                title=title,
                description=description,
                category=category_name,
                priority=priority_val,
                first_fix=first_fix_str,
            ),
            output_model=TicketSummary,
            node_name="generate_initial_summary",
        )
        result.summary = clean_summary_text(result.summary)
        return {"summary": result}
    except LLMInvocationError as exc:
        logger.error("generate_initial_summary_node failed: %s", exc)
        fallback = TicketSummary(summary=title)
        return {"summary": fallback, "errors": [f"generate_initial_summary: {exc}"]}


async def update_assignment_summary_node(state: dict) -> dict:
    title = state.get("title", "")
    description = state.get("description", "")
    agent_name = state.get("agent_name", "Unassigned")
    existing_summary = state.get("existing_summary", "")
    
    try:
        result = await _llm.ainvoke_structured(
            system_prompt=render_prompt("assignment_summary_system"),
            user_prompt=render_prompt(
                "assignment_summary_user",
                title=title,
                description=description,
                agent_name=agent_name,
                existing_summary=existing_summary,
            ),
            output_model=TicketSummary,
            node_name="update_assignment_summary",
        )
        result.summary = clean_summary_text(result.summary)
        return {"summary": result}
    except LLMInvocationError as exc:
        logger.error("update_assignment_summary_node failed: %s", exc)
        fallback = TicketSummary(summary=f"{existing_summary} (Assigned to {agent_name})")
        return {"summary": fallback, "errors": [f"update_assignment_summary: {exc}"]}


async def generate_resolution_summary_node(state: dict) -> dict:
    title = state.get("title", "")
    description = state.get("description", "")
    agent_name = state.get("agent_name", "Unassigned")
    status = state.get("status", "Resolved")
    resolution_details = state.get("resolution_details", "None")
    original_summary = state.get("original_summary", "")
    comments = state.get("comments", [])
    
    # Format comments history chronologically
    comments_history = ""
    if comments:
        lines = []
        for c in comments:
            visibility = "internal" if c.get("is_internal") else "public"
            author = c.get("author_name") or "Unknown"
            lines.append(f"[{c.get('created_at')}] ({author} - {visibility}): {c.get('body')}")
        comments_history = "\n".join(lines)
    else:
        comments_history = "(no comments)"
        
    try:
        result = await _llm.ainvoke_structured(
            system_prompt=render_prompt("resolution_summary_system"),
            user_prompt=render_prompt(
                "resolution_summary_user",
                title=title,
                description=description,
                agent_name=agent_name,
                status=status,
                resolution_details=resolution_details,
                original_summary=original_summary,
                comments_history=comments_history,
            ),
            output_model=TicketSummary,
            node_name="generate_resolution_summary",
        )
        result.summary = clean_summary_text(result.summary)
        return {"summary": result}
    except LLMInvocationError as exc:
        logger.error("generate_resolution_summary_node failed: %s", exc)
        fallback = TicketSummary(summary=f"{original_summary} (Status changed to Resolved)")
        return {"summary": fallback, "errors": [f"generate_resolution_summary: {exc}"]}
