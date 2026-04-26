import asyncio
import csv
import io
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from models.facture import FactureUpdate
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user
from datetime import datetime, timezone
from typing import Optional
from services.email_service import envoyer_facture_email

router = APIRouter()


async def _generer_numero_facture(user_id: str, token: str) -> str:
    year = datetime.now().year
    prefix = f"FAC-{year}-"
    result = await get_supabase_for_user(token).table("factures").select("numero").eq("user_id", user_id).like("numero", f"{prefix}%").order("numero", desc=True).limit(1).execute()
    if result.data:
        last_num = int(result.data[0]["numero"].split("-")[-1])
        return f"{prefix}{last_num + 1:03d}"
    return f"{prefix}001"


@router.get("")
async def list_factures(current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("factures").select("*, clients(nom, prenom, email)").eq("user_id", current_user["id"]).is_("deleted_at", "null").order("date_creation", desc=True).execute()
    return result.data


@router.post("/depuis-devis/{devis_id}", status_code=201)
async def creer_facture_depuis_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    devis = (await db.table("devis").select("*").eq("id", devis_id).eq("user_id", current_user["id"]).single().execute()).data
    if not devis:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    if devis["statut"] not in ("accepté", "envoyé", "relancé", "consulté"):
        raise HTTPException(status_code=400, detail="Le devis doit être accepté, envoyé ou relancé")
    existing = (await db.table("factures").select("id").eq("devis_id", devis_id).execute()).data
    if existing:
        raise HTTPException(status_code=400, detail="Ce devis a déjà été converti en facture")
    numero = await _generer_numero_facture(current_user["id"], current_user["token"])
    result = await db.table("factures").insert({
        "user_id": current_user["id"], "client_id": devis["client_id"], "devis_id": devis_id,
        "numero": numero, "titre": devis["titre"], "prestations": devis["prestations"],
        "montant_ht": float(devis["montant_ht"]), "tva": float(devis["tva"]),
        "montant_ttc": float(devis["montant_ttc"]), "notes": devis.get("notes"), "date_echeance": None,
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la facture")
    await db.table("devis").update({"statut": "facturé"}).eq("id", devis_id).execute()

    facture = result.data[0]

    # Envoi email au client (silencieux si pas d'email ou erreur)
    try:
        client = (await get_supabase().table("clients").select("email, nom, prenom").eq("id", devis["client_id"]).single().execute()).data
        profile = (await get_supabase().table("profiles").select("nom, prenom, entreprise, email, telephone").eq("id", current_user["id"]).single().execute()).data
        if client and client.get("email") and profile:
            artisan_nom = (profile.get("entreprise") or f"{profile.get('prenom', '')} {profile.get('nom', '')}".strip()) or "Votre artisan"
            client_nom  = f"{client.get('prenom', '')} {client.get('nom', '')}".strip() or "Client"
            envoyer_facture_email(
                client_email=client["email"],
                client_nom=client_nom,
                artisan_nom=artisan_nom,
                facture_numero=facture["numero"],
                facture_id=facture["id"],
                montant_ttc=float(facture["montant_ttc"]),
                artisan_email=profile.get("email") or "",
                artisan_telephone=profile.get("telephone") or "",
            )
    except Exception as e:
        print(f"[Email] Avertissement envoi facture : {e}")

    return facture


@router.get("/{facture_id}")
async def get_facture(facture_id: str, current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("factures").select("*, clients(nom, prenom, email, telephone, adresse)").eq("id", facture_id).eq("user_id", current_user["id"]).is_("deleted_at", "null").single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return result.data


@router.put("/{facture_id}")
async def update_facture(facture_id: str, data: FactureUpdate, current_user: dict = Depends(get_current_user)):
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = await get_supabase_for_user(current_user["token"]).table("factures").update(update_data).eq("id", facture_id).eq("user_id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return result.data[0]


@router.delete("/{facture_id}")
async def delete_facture(facture_id: str, current_user: dict = Depends(get_current_user)):
    """
    Suppression d'une facture.
    - Statut `brouillon` : suppression réelle autorisée.
    - Statut `émise` / `payée` : soft-delete uniquement (conservation 10 ans obligatoire en France).
    - Statut `annulée` : soft-delete également.
    """
    db = get_supabase_for_user(current_user["token"])
    check = await db.table("factures").select("id, statut").eq("id", facture_id).eq("user_id", current_user["id"]).is_("deleted_at", "null").execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    statut = check.data[0].get("statut")
    if statut == "brouillon":
        await db.table("factures").delete().eq("id", facture_id).eq("user_id", current_user["id"]).execute()
        return {"message": "Facture supprimée"}

    # Factures émises/payées/annulées : soft-delete pour conformité fiscale
    await db.table("factures").update({
        "deleted_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", facture_id).eq("user_id", current_user["id"]).execute()
    return {"message": "Facture archivée"}


_MOIS_FR = ["", "Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]

_MODE_LABELS = {
    "especes": "Especes", "cheque": "Cheque",
    "virement": "Virement bancaire", "carte": "Carte bancaire", "stripe": "Paiement en ligne",
}


@router.get("/export/csv")
async def export_factures_csv(
    current_user: dict = Depends(get_current_user),
    mois: Optional[int] = Query(None, ge=1, le=12),
    annee: Optional[int] = Query(None, ge=2020, le=2100),
):
    db = get_supabase_for_user(current_user["token"])
    result = await db.table("factures").select("*, clients(nom, prenom)").eq("user_id", current_user["id"]).is_("deleted_at", "null").order("date_creation", desc=False).execute()
    factures = result.data or []

    if mois and annee:
        debut = f"{annee}-{mois:02d}-01"
        fin = f"{annee + 1}-01-01" if mois == 12 else f"{annee}-{mois + 1:02d}-01"
        factures = [f for f in factures if debut <= (f.get("date_creation") or "")[:10] < fin]

    output = io.StringIO()
    w = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)

    w.writerow(["N Facture", "Date emission", "Client", "Objet",
                "HT (EUR)", "TVA (%)", "TVA (EUR)", "TTC (EUR)",
                "Statut", "Mode reglement", "Date encaissement", "Notes"])

    total_ht = total_tva = total_ttc = encaisse = impaye = 0.0
    nb_payees = nb_emises = 0

    for f in factures:
        client_nom = (f"{f['clients'].get('prenom', '')} {f['clients'].get('nom', '')}".strip()
                      if f.get("clients") else "")
        ht  = float(f.get("montant_ht") or 0)
        ttc = float(f.get("montant_ttc") or 0)
        tva_eur = ttc - ht
        total_ht += ht; total_tva += tva_eur; total_ttc += ttc
        statut = f.get("statut", "")
        if statut == "payée":   encaisse += ttc; nb_payees += 1
        elif statut == "émise": impaye   += ttc; nb_emises += 1
        w.writerow([
            f.get("numero", ""), (f.get("date_creation") or "")[:10], client_nom,
            f.get("titre", ""), f"{ht:.2f}", f"{float(f.get('tva') or 0):.0f}%",
            f"{tva_eur:.2f}", f"{ttc:.2f}", statut,
            _MODE_LABELS.get(f.get("mode_paiement") or "", ""),
            (f.get("date_paiement") or "")[:10], f.get("notes") or "",
        ])

    # Ligne vide + totaux
    w.writerow([])
    w.writerow([f"TOTAL — {len(factures)} facture{'s' if len(factures) > 1 else ''}", "", "", "",
                f"{total_ht:.2f}", "", f"{total_tva:.2f}", f"{total_ttc:.2f}", "", "", "", ""])
    w.writerow([f"Dont encaisse", "", "", "", "", "", "", f"{encaisse:.2f}", "", "", "", ""])
    w.writerow([f"Dont impaye", "", "", "", "", "", "", f"{impaye:.2f}", "", "", "", ""])

    content = '\ufeff' + output.getvalue()
    filename = (f"factures_{annee}-{mois:02d}.csv" if (mois and annee)
                else f"factures_{datetime.now().strftime('%Y%m%d')}.csv")

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/pdf")
async def export_livre_recettes_pdf(
    current_user: dict = Depends(get_current_user),
    mois: int = Query(..., ge=1, le=12),
    annee: int = Query(..., ge=2020, le=2100),
):
    from services.pdf_service import generer_livre_recettes

    db = get_supabase_for_user(current_user["token"])
    result = await db.table("factures").select("*, clients(nom, prenom)").eq("user_id", current_user["id"]).eq("statut", "payée").is_("deleted_at", "null").order("date_paiement", desc=False).execute()
    factures = result.data or []

    debut = f"{annee}-{mois:02d}-01"
    fin = f"{annee + 1}-01-01" if mois == 12 else f"{annee}-{mois + 1:02d}-01"
    factures = [f for f in factures if debut <= (f.get("date_paiement") or "")[:10] < fin]

    artisan_res = await db.table("profiles").select("*").eq("id", current_user["id"]).single().execute()
    artisan = artisan_res.data or {}

    pdf_bytes = bytes(generer_livre_recettes(factures, artisan, mois, annee))
    filename = f"livre_recettes_{annee}-{mois:02d}.pdf"

    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
