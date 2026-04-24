import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pywebpush import webpush, WebPushException

from utils.supabase_client import get_supabase, get_supabase_for_user
from utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "contact@myartipro.fr")


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: SubscriptionKeys
    expirationTime: Optional[float] = None


class UnsubscribeIn(BaseModel):
    endpoint: str


@router.post("/subscribe", status_code=201)
async def subscribe(data: SubscriptionIn, current_user: dict = Depends(get_current_user)):
    await get_supabase_for_user(current_user["token"]) \
        .table("push_subscriptions") \
        .upsert({
            "user_id": current_user["id"],
            "endpoint": data.endpoint,
            "p256dh": data.keys.p256dh,
            "auth": data.keys.auth,
        }, on_conflict="endpoint") \
        .execute()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(data: UnsubscribeIn, current_user: dict = Depends(get_current_user)):
    await get_supabase_for_user(current_user["token"]) \
        .table("push_subscriptions") \
        .delete() \
        .eq("user_id", current_user["id"]) \
        .eq("endpoint", data.endpoint) \
        .execute()
    return {"ok": True}


async def send_push_to_user(user_id: str, title: str, body: str, url: str = "/", tag: str = "myartipro"):
    """Envoie une notification push à tous les appareils d'un utilisateur. Fire-and-forget."""
    if not VAPID_PRIVATE_KEY:
        return

    result = await get_supabase() \
        .table("push_subscriptions") \
        .select("endpoint, p256dh, auth") \
        .eq("user_id", user_id) \
        .execute()

    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})

    for sub in result.data or []:
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{VAPID_EMAIL}"},
            )
        except WebPushException as e:
            # Souscription expirée ou invalide → on la supprime
            if e.response is not None and e.response.status_code in (404, 410):
                await get_supabase().table("push_subscriptions").delete().eq("endpoint", sub["endpoint"]).execute()
            else:
                logger.warning("[push] erreur envoi: %s", e)
        except Exception as e:
            logger.warning("[push] erreur inattendue: %s", e)
