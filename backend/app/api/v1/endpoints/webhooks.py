import logging
from typing import Any
from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.webhook import Webhook, WebhookStatus

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/meta", response_class=PlainTextResponse)
async def verify_meta_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """
    Handle Meta's GET verification request.
    Meta sends this to confirm ownership of the endpoint.
    """
    logger.info("Received Meta webhook verification request. Mode: %s, Token: %s", hub_mode, hub_verify_token)
    
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        return hub_challenge
        
    logger.warning("Meta webhook verification failed. Expected token: %s, received: %s", settings.META_WEBHOOK_VERIFY_TOKEN, hub_verify_token)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch"
    )

@router.post("/meta")
async def receive_meta_webhook(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Meta's POST event webhook notification.
    Saves the received event to the database.
    """
    logger.info("Received Meta webhook payload: %s", payload)
    
    # Identify event source and type
    source = "meta"
    object_type = payload.get("object", "unknown")
    entry = payload.get("entry", [])
    
    # Try to extract the first action as event_type
    event_type = f"object_{object_type}"
    if entry and isinstance(entry, list):
        changes = entry[0].get("changes", [])
        if changes and isinstance(changes, list):
            event_type = changes[0].get("field", event_type)
            
    try:
        webhook_record = Webhook(
            source=source,
            event_type=event_type,
            payload=payload,
            status=WebhookStatus.RECEIVED
        )
        db.add(webhook_record)
        await db.commit()
        logger.info("Successfully recorded Meta webhook: %s", event_type)
        return {"status": "accepted"}
    except Exception as e:
        logger.error("Failed to record Meta webhook: %s", str(e))
        # Don't fail the request so Meta doesn't disable the webhook
        return {"status": "error", "message": str(e)}
