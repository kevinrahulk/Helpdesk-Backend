from fastapi import APIRouter

from app.routers.tickets.actions import router as actions_router
from app.routers.tickets.attachments import router as attachments_router
from app.routers.tickets.comments import router as comments_router
from app.routers.tickets.crud import router as crud_router
from app.routers.tickets.helpers import resolve_similar_tickets, _to_ticket_response

router = APIRouter(tags=["Tickets"])

router.include_router(crud_router)
router.include_router(actions_router)
router.include_router(comments_router)
router.include_router(attachments_router)
