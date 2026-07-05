from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.auth import decode_access_token
from app.websocket import manager
import logging

router = APIRouter(tags=["WebSockets"])
logger = logging.getLogger("app.websocket_router")

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    user_id = None
    try:
        # Decode and validate token to authenticate the user
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("WebSocket connection attempt with invalid token sub")
            await websocket.close(code=1008)  # Policy Violation
            return
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        # Accept the connection first so we can close it with a code
        await websocket.accept()
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            # Keep connection alive; discard any incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for user_id={user_id}: {e}")
        manager.disconnect(user_id, websocket)
