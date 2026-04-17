import uuid
from fastapi import APIRouter, HTTPException, Depends
from models.devis import DevisCreate, DevisUpdate
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user
from services.email_service import envoyer_devis_email
from datetime import datetime, timezone

router = APIRouter()


def _generer_numero(user_id: str, token: str) -> str:
    """Génère le prochain numéro de devis : DEV-2026-001."""
    year = datetime.now().year
    prefix = f"DEV-{year}-"

    result = (
        get_supabase_for_user(token).table("devis")
        .select("numero")
        .eq("user_id", user_id)
        .like("numero", f"{prefix}%")
        .order("numero", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        last_num = int(result.data[0]["numero"].split("-")[-1])
        return f"{prefix}{last_num + 1:03d}"
    return f"{prefix}001"


def _calculer_montants(prestations: list, tva: float) -> tuple:
    """Calcule HT et TTC à partir des prestations."""
    montant_ht = sum(p["quantite"] * p["prix_unitaire"] for p in prestations)
    montant_ttc = montant_ht * (1 + tva / 100)
    return round(montant_ht, 2), round(montant_ttc, 2)


@router.get("")
async def list_devis(current_user: dict = Depends(get_current_user)):
    """Liste tous les devis de l'utilisateur connecté."""
    db = get_supabase_for_user(current_user["token"])
    result = (
        db.table("devis")
        .select("*, clients(nom, prenom, email)")
        .eq("user_id", current_user["id"])
        .order("date_creation", desc=True)
        .execute()
    )
    return result.data


@router.post("", status_code=201)
async def create_devis(
    data: DevisCreate,
    current_user: dict = Depends(get_current_user),
):
    """Crée un nouveau devis avec numéro auto-généré."""
    db = get_supabase_for_user(current_user["token"])
    prestations = [p.model_dump() for p in data.prestations]
    montant_ht, montant_ttc = _calculer_montants(prestations, data.tva)
    numero = _generer_numero(current_user["id"], current_user["token"])

    devis_data = {
        "user_id": current_user["id"],
        "client_id": data.client_id,
        "numero": numero,
        "titre": data.titre,
        "prestations": prestations,
        "montant_ht": montant_ht,
        "tva": data.tva,
        "montant_ttc": montant_ttc,
        "notes": data.notes,
        "date_validite": data.date_validite,
        "urgence": data.urgence or "normal",
        "charge": data.charge,
    }

    result = db.table("devis").insert(devis_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.get("/{devis_id}")
async def get_devis(
    devis_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Récupère un devis par son ID."""
    db = get_supabase_for_user(current_user["token"])
    result = (
        db.table("devis")
        .select("*, clients(nom, prenom, email, telephone, adresse)")
        .eq("id", devis_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    return result.data


@router.put("/{devis_id}")
async def update_devis(
    devis_id: str,
    data: DevisUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Modifie un devis existant."""
    db = get_supabase_for_user(current_user["token"])
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

    if "prestations" in update_data and update_data["prestations"] is not None:
        prestations = [p.model_dump() if hasattr(p, "model_dump") else p for p in update_data["prestations"]]
        tva = update_data.get("tva", 20.0)
        montant_ht, montant_ttc = _calculer_montants(prestations, tva)
        update_data["prestations"] = prestations
        update_data["montant_ht"] = montant_ht
        update_data["montant_ttc"] = montant_ttc

    result = (
        db.table("devis")
        .update(update_data)
        .eq("id", devis_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    return result.data[0]


@router.delete("/{devis_id}")
async def delete_devis(
    devis_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Supprime un devis."""
    db = get_supabase_for_user(current_user["token"])
    # Vérifier que le devis existe avant de supprimer
    check = (
        db.table("devis")
        .select("id")
        .eq("id", devis_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not check.data:
        raise HTTPException(status_code=404, detail="Devis non trouvé")

    db.table("devis").delete().eq("id", devis_id).eq("user_id", current_user["id"]).execute()
    return {"message": "Devis supprimé"}


@router.post("/{devis_id}/envoyer")
async def envoyer_devis(
    devis_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Envoie le devis par email au client et passe le statut à 'envoyé'."""
    db = get_supabase_for_user(current_user["token"])
    devis = (
        db.table("devis")
        .select("*, clients(email, nom, prenom)")
        .eq("id", devis_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    ).data

    if not devis:
        raise HTTPException(status_code=404, detail="Devis non trouvé")

    client = devis.get("clients")
    if not client or not client.get("email"):
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")

    artisan = (
        db.table("profiles")
        .select("nom, prenom, entreprise")
        .eq("id", current_user["id"])
        .single()
        .execute()
    ).data

    artisan_nom = artisan.get("entreprise") or f"{artisan.get('prenom', '')} {artisan.get('nom', '')}".strip()

    # Générer un token d'acceptation sécurisé
    acceptance_token = str(uuid.uuid4())

    try:
        envoyer_devis_email(
            client_email=client["email"],
            client_nom=f"{client.get('prenom', '')} {client['nom']}".strip(),
            artisan_nom=artisan_nom,
            devis_numero=devis["numero"],
            devis_id=devis_id,
            acceptance_token=acceptance_token,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur envoi email: {str(e)}")

    db.table("devis").update({
        "statut": "envoyé",
        "date_envoi": datetime.now(timezone.utc).isoformat(),
        "acceptance_token": acceptance_token,
    }).eq("id", devis_id).execute()

    # Sync statut client → devis_envoye
    if devis.get("client_id"):
        db.table("clients").update({"statut": "devis_envoye"}).eq("id", devis["client_id"]).execute()

    return {"message": f"Devis {devis['numero']} envoyé à {client['email']}"}


# ── Routes publiques (sans auth) ─────────────────────────────────────────────

@router.get("/public/{acceptance_token}")
async def get_devis_public(acceptance_token: str):
    """Récupère les infos d'un devis via son token — accessible sans auth."""
    db = get_supabase()
    result = (
        db.table("devis")
        .select("id, numero, titre, prestations, montant_ht, tva, montant_ttc, statut, date_creation, date_validite, notes, user_id, clients(nom, prenom, adresse)")
        .eq("acceptance_token", acceptance_token)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis introuvable ou lien invalide")

    devis = result.data[0]

    # Marquer comme consulté si encore en statut envoyé/relancé
    if devis["statut"] in ("envoyé", "relancé"):
        db.table("devis").update({"statut": "consulté"}).eq("acceptance_token", acceptance_token).execute()
        devis["statut"] = "consulté"

    # Récupérer les infos paiement de l'artisan
    profile = db.table("profiles").select(
        "stripe_enabled, moyens_paiement, instructions_paiement, entreprise, prenom, nom"
    ).eq("id", devis["user_id"]).single().execute()

    devis["artisan_paiement"] = {
        "stripe_enabled": profile.data.get("stripe_enabled", False) if profile.data else False,
        "moyens_paiement": profile.data.get("moyens_paiement") or [] if profile.data else [],
        "instructions_paiement": profile.data.get("instructions_paiement") or "" if profile.data else "",
        "artisan_nom": (
            profile.data.get("entreprise") or
            f"{profile.data.get('prenom', '')} {profile.data.get('nom', '')}".strip()
        ) if profile.data else "",
    }

    return devis


@router.post("/public/{acceptance_token}/accepter")
async def accepter_devis_public(acceptance_token: str):
    """Le client accepte le devis via son token."""
    db = get_supabase()
    result = db.table("devis").select("id, statut, numero, client_id").eq("acceptance_token", acceptance_token).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Devis introuvable ou lien invalide")

    devis = result.data[0]
    if devis["statut"] in ("facturé", "accepté"):
        return {"message": "Devis déjà accepté"}
    if devis["statut"] == "refusé":
        raise HTTPException(status_code=400, detail="Ce devis a déjà été refusé")

    db.table("devis").update({
        "statut": "accepté",
        "date_acceptation": datetime.now(timezone.utc).isoformat(),
    }).eq("acceptance_token", acceptance_token).execute()

    # Sync statut client → accepte
    if devis.get("client_id"):
        db.table("clients").update({"statut": "accepte"}).eq("id", devis["client_id"]).execute()

    return {"message": f"Devis {devis['numero']} accepté"}


@router.post("/public/{acceptance_token}/refuser")
async def refuser_devis_public(acceptance_token: str):
    """Le client refuse le devis via son token."""
    db = get_supabase()
    result = db.table("devis").select("id, statut, numero, client_id").eq("acceptance_token", acceptance_token).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Devis introuvable ou lien invalide")

    devis = result.data[0]
    if devis["statut"] == "refusé":
        return {"message": "Devis déjà refusé"}
    if devis["statut"] in ("facturé", "accepté"):
        raise HTTPException(status_code=400, detail="Ce devis ne peut plus être refusé")

    db.table("devis").update({"statut": "refusé"}).eq("acceptance_token", acceptance_token).execute()

    # Sync statut client → a_rappeler (devis refusé = à recontacter)
    if devis.get("client_id"):
        db.table("clients").update({"statut": "a_rappeler"}).eq("id", devis["client_id"]).execute()

    return {"message": f"Devis {devis['numero']} refusé"}


@router.post("/relances/executer")
async def executer_relances(current_user: dict = Depends(get_current_user)):
    """Déclenche manuellement la vérification des relances."""
    from services.relance_service import relancer_devis_sans_reponse
    relancer_devis_sans_reponse()
    return {"message": "Relances exécutées"}
