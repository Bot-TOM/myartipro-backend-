import asyncio
import uuid
from fastapi import APIRouter, HTTPException, Depends
from models.devis import DevisCreate, DevisUpdate
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user
from services.email_service import envoyer_devis_email
from datetime import datetime, timezone

router = APIRouter()


async def _generer_numero(user_id: str, token: str) -> str:
    year = datetime.now().year
    prefix = f"DEV-{year}-"
    result = await get_supabase_for_user(token).table("devis").select("numero").eq("user_id", user_id).like("numero", f"{prefix}%").order("numero", desc=True).limit(1).execute()
    if result.data:
        last_num = int(result.data[0]["numero"].split("-")[-1])
        return f"{prefix}{last_num + 1:03d}"
    return f"{prefix}001"


def _calculer_montants(prestations: list, tva: float) -> tuple:
    montant_ht = sum(p["quantite"] * p["prix_unitaire"] for p in prestations)
    montant_ttc = montant_ht * (1 + tva / 100)
    return round(montant_ht, 2), round(montant_ttc, 2)


@router.get("")
async def list_devis(current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("devis").select("*, clients(nom, prenom, email)").eq("user_id", current_user["id"]).order("date_creation", desc=True).execute()
    return result.data


@router.post("", status_code=201)
async def create_devis(data: DevisCreate, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    prestations = [p.model_dump() for p in data.prestations]
    montant_ht, montant_ttc = _calculer_montants(prestations, data.tva)
    numero = await _generer_numero(current_user["id"], current_user["token"])
    result = await db.table("devis").insert({
        "user_id": current_user["id"], "client_id": data.client_id, "numero": numero,
        "titre": data.titre, "prestations": prestations, "montant_ht": montant_ht,
        "tva": data.tva, "montant_ttc": montant_ttc, "notes": data.notes,
        "date_validite": data.date_validite, "urgence": data.urgence or "normal", "charge": data.charge,
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.get("/{devis_id}")
async def get_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("devis").select("*, clients(nom, prenom, email, telephone, adresse)").eq("id", devis_id).eq("user_id", current_user["id"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    return result.data


@router.put("/{devis_id}")
async def update_devis(devis_id: str, data: DevisUpdate, current_user: dict = Depends(get_current_user)):
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
    result = await db.table("devis").update(update_data).eq("id", devis_id).eq("user_id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    return result.data[0]


@router.delete("/{devis_id}")
async def delete_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    check = await db.table("devis").select("id").eq("id", devis_id).eq("user_id", current_user["id"]).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    await db.table("devis").delete().eq("id", devis_id).eq("user_id", current_user["id"]).execute()
    return {"message": "Devis supprimé"}


@router.post("/{devis_id}/dupliquer", status_code=201)
async def dupliquer_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    source = (await db.table("devis").select("client_id, titre, prestations, tva, acompte_pct, notes, date_validite, urgence, charge").eq("id", devis_id).eq("user_id", current_user["id"]).single().execute()).data
    if not source:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    numero = await _generer_numero(current_user["id"], current_user["token"])
    prestations = source.get("prestations") or []
    tva = source.get("tva") or 20.0
    montant_ht, montant_ttc = _calculer_montants(prestations, tva)
    result = await db.table("devis").insert({
        "user_id": current_user["id"],
        "client_id": source["client_id"],
        "numero": numero,
        "titre": f"Copie — {source['titre']}",
        "prestations": prestations,
        "montant_ht": montant_ht,
        "tva": tva,
        "montant_ttc": montant_ttc,
        "acompte_pct": source.get("acompte_pct") or 0,
        "notes": source.get("notes"),
        "date_validite": source.get("date_validite"),
        "urgence": source.get("urgence") or "normal",
        "charge": source.get("charge"),
        "statut": "brouillon",
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la duplication")
    return result.data[0]


@router.post("/{devis_id}/envoyer")
async def envoyer_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    devis = (await db.table("devis").select("*, clients(email, nom, prenom)").eq("id", devis_id).eq("user_id", current_user["id"]).single().execute()).data
    if not devis:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    client = devis.get("clients")
    if not client or not client.get("email"):
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")
    artisan = (await db.table("profiles").select("nom, prenom, entreprise, email, telephone").eq("id", current_user["id"]).single().execute()).data
    artisan_nom = artisan.get("entreprise") or f"{artisan.get('prenom', '')} {artisan.get('nom', '')}".strip()
    acceptance_token = str(uuid.uuid4())
    try:
        envoyer_devis_email(
            client_email=client["email"],
            client_nom=f"{client.get('prenom', '')} {client['nom']}".strip(),
            artisan_nom=artisan_nom, devis_numero=devis["numero"],
            devis_id=devis_id, acceptance_token=acceptance_token,
            artisan_email=artisan.get("email") or "",
            artisan_telephone=artisan.get("telephone") or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur envoi email: {str(e)}")
    await db.table("devis").update({"statut": "envoyé", "date_envoi": datetime.now(timezone.utc).isoformat(), "acceptance_token": acceptance_token}).eq("id", devis_id).execute()
    if devis.get("client_id"):
        await db.table("clients").update({"statut": "devis_envoye"}).eq("id", devis["client_id"]).execute()
    return {"message": f"Devis {devis['numero']} envoyé à {client['email']}"}


# ── Routes publiques ──────────────────────────────────────────────────────────

@router.get("/public/{acceptance_token}")
async def get_devis_public(acceptance_token: str):
    db = get_supabase()
    result = await db.table("devis").select("id, numero, titre, prestations, montant_ht, tva, montant_ttc, statut, date_creation, date_validite, notes, user_id, clients(nom, prenom, adresse)").eq("acceptance_token", acceptance_token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis introuvable ou lien invalide")
    devis = result.data[0]
    if devis["statut"] in ("envoyé", "relancé"):
        await db.table("devis").update({"statut": "consulté"}).eq("acceptance_token", acceptance_token).execute()
        devis["statut"] = "consulté"
    profile = await db.table("profiles").select("stripe_enabled, moyens_paiement, instructions_paiement, entreprise, prenom, nom").eq("id", devis["user_id"]).single().execute()
    devis["artisan_paiement"] = {
        "stripe_enabled": profile.data.get("stripe_enabled", False) if profile.data else False,
        "moyens_paiement": profile.data.get("moyens_paiement") or [] if profile.data else [],
        "instructions_paiement": profile.data.get("instructions_paiement") or "" if profile.data else "",
        "artisan_nom": (profile.data.get("entreprise") or f"{profile.data.get('prenom', '')} {profile.data.get('nom', '')}".strip()) if profile.data else "",
    }
    return devis


@router.post("/public/{acceptance_token}/accepter")
async def accepter_devis_public(acceptance_token: str):
    db = get_supabase()
    result = await db.table("devis").select("id, statut, numero, client_id, user_id, titre").eq("acceptance_token", acceptance_token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis introuvable ou lien invalide")
    devis = result.data[0]
    if devis["statut"] in ("facturé", "accepté"):
        return {"message": "Devis déjà accepté"}
    if devis["statut"] == "refusé":
        raise HTTPException(status_code=400, detail="Ce devis a déjà été refusé")
    await db.table("devis").update({"statut": "accepté", "date_acceptation": datetime.now(timezone.utc).isoformat()}).eq("acceptance_token", acceptance_token).execute()
    if devis.get("client_id"):
        await db.table("clients").update({"statut": "accepte"}).eq("id", devis["client_id"]).execute()
    if devis.get("user_id"):
        from routers.push import notify_user
        asyncio.ensure_future(notify_user(
            devis["user_id"],
            title="Devis accepté ✓",
            body=f"{devis.get('titre') or devis['numero']} a été accepté par votre client.",
            url="/devis",
            tag="devis-accepte",
        ))
    return {"message": f"Devis {devis['numero']} accepté"}


@router.post("/public/{acceptance_token}/refuser")
async def refuser_devis_public(acceptance_token: str):
    db = get_supabase()
    result = await db.table("devis").select("id, statut, numero, client_id").eq("acceptance_token", acceptance_token).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Devis introuvable ou lien invalide")
    devis = result.data[0]
    if devis["statut"] == "refusé":
        return {"message": "Devis déjà refusé"}
    if devis["statut"] in ("facturé", "accepté"):
        raise HTTPException(status_code=400, detail="Ce devis ne peut plus être refusé")
    await db.table("devis").update({"statut": "refusé"}).eq("acceptance_token", acceptance_token).execute()
    if devis.get("client_id"):
        await db.table("clients").update({"statut": "a_rappeler"}).eq("id", devis["client_id"]).execute()
    return {"message": f"Devis {devis['numero']} refusé"}


@router.post("/relances/executer")
async def executer_relances(current_user: dict = Depends(get_current_user)):
    from services.relance_service import relancer_devis_sans_reponse
    await relancer_devis_sans_reponse()
    return {"message": "Relances exécutées"}
