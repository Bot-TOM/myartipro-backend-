import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pywebpush import webpush, WebPushException

from services.sms_service import envoyer_sms
from utils.auth import get_current_user
from utils.supabase_client import get_supabase, get_supabase_for_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Railway stocke parfois les clés multilignes avec des \n littéraux
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
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
    try:
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
    except Exception as e:
        logger.error("[push] subscribe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe(data: UnsubscribeIn, current_user: dict = Depends(get_current_user)):
    await get_supabase_for_user(current_user["token"]) \
        .table("push_subscriptions") \
        .delete() \
        .eq("user_id", current_user["id"]) \
        .eq("endpoint", data.endpoint) \
        .execute()
    return {"ok": True}


@router.post("/test-sms")
async def test_sms(current_user: dict = Depends(get_current_user)):
    """Envoie un SMS de test au numéro du profil."""
    result = await get_supabase_for_user(current_user["token"]) \
        .table("profiles") \
        .select("telephone, sms_notifications") \
        .eq("id", current_user["id"]) \
        .single() \
        .execute()

    profil = result.data or {}
    if not profil.get("telephone"):
        return {"ok": False, "error": "Aucun numéro de téléphone dans votre profil"}
    if not profil.get("sms_notifications"):
        return {"ok": False, "error": "Les SMS sont désactivés dans votre profil"}

    ok, err = await envoyer_sms(profil["telephone"], "Test MyArtipro 📲\nLes notifications SMS fonctionnent !")
    if ok:
        return {"ok": True}
    return {"ok": False, "error": err or "Envoi échoué"}


@router.post("/test")
async def test_push(current_user: dict = Depends(get_current_user)):
    """Envoie une notification push de test à tous les appareils enregistrés."""
    if not VAPID_PRIVATE_KEY:
        return {"ok": False, "error": "VAPID_PRIVATE_KEY non configuré sur le serveur"}

    result = await get_supabase_for_user(current_user["token"]) \
        .table("push_subscriptions") \
        .select("id") \
        .eq("user_id", current_user["id"]) \
        .execute()

    count = len(result.data or [])
    if count == 0:
        return {"ok": False, "error": "Aucune souscription enregistrée — activez les notifications d'abord"}

    await _send_push(
        current_user["id"],
        "Test MyArtipro 🔔",
        "Les notifications fonctionnent correctement !",
        "/",
        "test",
    )
    return {"ok": True, "subscriptions": count}


async def _send_push(user_id: str, title: str, body: str, url: str, tag: str) -> None:
    if not VAPID_PRIVATE_KEY:
        logger.warning("[push] VAPID_PRIVATE_KEY absent — notification non envoyée")
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
            logger.info("[push] envoyée → %s…", sub["endpoint"][:50])
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                await get_supabase().table("push_subscriptions").delete().eq("endpoint", sub["endpoint"]).execute()
                logger.info("[push] souscription expirée supprimée")
            else:
                logger.warning("[push] erreur %s : %s", status, e)
        except Exception as e:
            logger.warning("[push] erreur inattendue : %s", e)


async def _send_sms(user_id: str, message: str) -> None:
    result = await get_supabase() \
        .table("profiles") \
        .select("telephone, sms_notifications") \
        .eq("id", user_id) \
        .single() \
        .execute()

    if result.data and result.data.get("sms_notifications") and result.data.get("telephone"):
        ok, err = await envoyer_sms(result.data["telephone"], message)
        if not ok:
            logger.warning("[sms] échec pour user %s : %s", user_id, err)


async def notify_user(
    user_id: str,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "myartipro",
) -> None:
    """Push + SMS selon les préférences. Appeler avec asyncio.ensure_future()."""
    try:
        await asyncio.gather(
            _send_push(user_id, title, body, url, tag),
            _send_sms(user_id, f"{title}\n{body}"),
            return_exceptions=True,
        )
    except Exception as e:
        logger.warning("[notify] erreur : %s", e)


# Compat legacy
async def send_push_to_user(user_id: str, title: str, body: str, url: str = "/", tag: str = "myartipro") -> None:
    await notify_user(user_id, title, body, url, tag)
