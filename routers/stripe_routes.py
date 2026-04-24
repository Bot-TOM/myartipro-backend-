import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user
from services.stripe_service import creer_checkout_session, verifier_webhook
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/checkout/{facture_id}")
async def creer_lien_paiement(facture_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    facture = (await db.table("factures").select("*, clients(nom, prenom, email)").eq("id", facture_id).eq("user_id", current_user["id"]).single().execute()).data
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    if facture["statut"] == "payée":
        raise HTTPException(status_code=400, detail="Cette facture est déjà payée")
    client = facture.get("clients")
    if not client or not client.get("email"):
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")
    artisan = (await db.table("profiles").select("nom, prenom, entreprise").eq("id", current_user["id"]).single().execute()).data
    artisan_nom = artisan.get("entreprise") or f"{artisan.get('prenom', '')} {artisan.get('nom', '')}".strip()
    try:
        checkout_url = creer_checkout_session(facture_id=facture_id, facture_numero=facture["numero"], montant_ttc=float(facture["montant_ttc"]), client_email=client["email"], artisan_nom=artisan_nom)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Stripe : {str(e)}")
    await db.table("factures").update({"stripe_checkout_url": checkout_url}).eq("id", facture_id).execute()
    return {"checkout_url": checkout_url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = verifier_webhook(payload, sig_header)
    except Exception as e:
        logger.warning("[stripe webhook] signature invalide: %s", e)
        raise HTTPException(status_code=400, detail="Signature webhook invalide")

    event_type = event.get("type")
    logger.info("[stripe webhook] event reçu: %s (id=%s)", event_type, event.get("id"))

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        facture_id = session.get("metadata", {}).get("facture_id")
        if not facture_id:
            logger.error("[stripe webhook] checkout.session.completed sans facture_id (session=%s)", session.get("id"))
            return {"received": True}
        try:
            db = get_supabase()
            result = await db.table("factures").update({
                "statut": "payée",
                "date_paiement": datetime.now(timezone.utc).isoformat(),
            }).eq("id", facture_id).execute()
            logger.info("[stripe webhook] facture %s marquée payée", facture_id)
            if result.data:
                facture = result.data[0]
                from routers.push import notify_user
                asyncio.ensure_future(notify_user(
                    facture["user_id"],
                    title="Paiement reçu 💰",
                    body=f"La facture {facture.get('numero', '')} a été réglée en ligne.",
                    url="/factures",
                    tag="paiement-recu",
                ))
        except Exception as e:
            logger.exception("[stripe webhook] erreur update facture %s: %s", facture_id, e)
            raise HTTPException(status_code=500, detail="Erreur mise à jour facture")

    return {"received": True}
