import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status, HTTPException
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
    logger.info("Received Meta webhook verification request. Mode: %s", hub_mode)
    
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        return hub_challenge
        
    # Never log the expected token: it is the shared secret that authorises
    # the handshake, and a failed attempt is exactly when an attacker is
    # watching for it to appear in a log.
    logger.warning("Meta webhook verification failed for mode %s", hub_mode)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch"
    )

SIGNATURE_HEADER = "X-Hub-Signature-256"


def _verify_meta_signature(raw_body: bytes, header_value: str | None) -> bool:
    """Check Meta's HMAC-SHA256 over the exact bytes received.

    The digest must be computed on the raw body: re-serialising the parsed JSON
    changes whitespace and key order and would never match.
    """
    secret = (settings.META_APP_SECRET or "").strip()
    if not secret:
        # Unverifiable. An unauthenticated endpoint that writes to the database
        # is worth more to an attacker than the events are to us, so absence of
        # a secret means "reject", not "trust".
        logger.error(
            "META_APP_SECRET is not configured; rejecting Meta webhook because "
            "its signature cannot be verified."
        )
        return False

    if not header_value or not header_value.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    # Constant-time: a plain == leaks how much of the digest matched.
    return hmac.compare_digest(expected, header_value.split("=", 1)[1])


@router.post("/meta")
async def receive_meta_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Meta's POST event webhook notification.
    Saves the received event to the database, but only once the payload is
    proven to have come from Meta.
    """
    raw_body = await request.body()
    if not _verify_meta_signature(raw_body, request.headers.get(SIGNATURE_HEADER)):
        logger.warning("Rejected Meta webhook with an invalid or missing signature")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    try:
        payload: dict[str, Any] = json.loads(raw_body)
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload",
        )

    logger.info("Received verified Meta webhook: object=%s", payload.get("object"))
    
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
