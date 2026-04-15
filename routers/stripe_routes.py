from fastapi import APIRouter, HTTPException, Depends, Request
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user
from services.stripe_service import creer_checkout_session, verifier_webhook
from datetime import datetime

router = APIRouter()


@router.post("/checkout/{facture_id}")
async def creer_lien_paiement(
    facture_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Crée un lien de paiement Stripe pour une facture."""
    db = get_supabase_for_user(current_user["token"])

    facture = (
        db.table("factures")
        .select("*, clients(nom, prenom, email)")
        .eq("id", facture_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    ).data

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    if facture["statut"] == "payée":
        raise HTTPException(status_code=400, detail="Cette facture est déjà payée")

    client = facture.get("clients")
    if not client or not client.get("email"):
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")

    # Récupérer le nom du plombier
    plombier = (
        db.table("profiles")
        .select("nom, prenom, entreprise")
        .eq("id", current_user["id"])
        .single()
        .execute()
    ).data

    plombier_nom = plombier.get("entreprise") or f"{plombier.get('prenom', '')} {plombier.get('nom', '')}".strip()

    try:
        checkout_url = creer_checkout_session(
            facture_id=facture_id,
            facture_numero=facture["numero"],
            montant_ttc=float(facture["montant_ttc"]),
            client_email=client["email"],
            plombier_nom=plombier_nom,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Stripe : {str(e)}")

    # Sauvegarder l'URL dans la facture (optionnel, pour la partager)
    db.table("factures").update(
        {"stripe_checkout_url": checkout_url}
    ).eq("id", facture_id).execute()

    return {"checkout_url": checkout_url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Webhook Stripe — marque la facture comme payée après paiement réussi."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = verifier_webhook(payload, sig_header)
    except Exception:
        raise HTTPException(status_code=400, detail="Signature webhook invalide")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        facture_id = session.get("metadata", {}).get("facture_id")

        if facture_id:
            db = get_supabase()
            db.table("factures").update({
                "statut": "payée",
                "date_paiement": datetime.now().isoformat(),
            }).eq("id", facture_id).execute()

    return {"received": True}
