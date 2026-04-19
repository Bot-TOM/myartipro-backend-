import csv
import io
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from models.facture import FactureUpdate
from utils.supabase_client import get_supabase_for_user
from utils.auth import get_current_user
from datetime import datetime, timezone
from typing import Optional

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
    if devis["statut"] not in ("accepté", "envoyé", "relancé"):
        raise HTTPException(status_code=400, detail="Le devis doit être envoyé, relancé ou accepté")
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
    return result.data[0]


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


@router.get("/export/csv")
async def export_factures_csv(
    current_user: dict = Depends(get_current_user),
    mois: Optional[int] = Query(None, ge=1, le=12),
    annee: Optional[int] = Query(None, ge=2020, le=2100),
):
    db = get_supabase_for_user(current_user["token"])
    query = db.table("factures").select("*, clients(nom, prenom)").eq("user_id", current_user["id"]).is_("deleted_at", "null")

    if mois and annee:
        # Filtrage sur la date de création du mois demandé
        debut = f"{annee}-{mois:02d}-01"
        # Dernier jour du mois suivant (exclusive)
        if mois == 12:
            fin = f"{annee + 1}-01-01"
        else:
            fin = f"{annee}-{mois + 1:02d}-01"
        query = query.gte("date_creation", debut).lt("date_creation", fin)

    result = await query.order("date_creation", desc=False).execute()
    factures = result.data or []

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        'Numero', 'Client', 'Titre',
        'Date creation', 'Date echeance', 'Date paiement',
        'Montant HT (EUR)', 'TVA (%)', 'Montant TTC (EUR)',
        'Statut', 'Notes',
    ])

    total_ht = 0.0
    total_ttc = 0.0
    nb_payees = 0

    for f in factures:
        client_nom = f"{f['clients'].get('prenom', '')} {f['clients'].get('nom', '')}".strip() if f.get('clients') else ''
        ht = float(f.get('montant_ht') or 0)
        ttc = float(f.get('montant_ttc') or 0)
        total_ht += ht
        total_ttc += ttc
        if f.get('statut') == 'payée':
            nb_payees += 1
        writer.writerow([
            f.get('numero', ''),
            client_nom,
            f.get('titre', ''),
            (f.get('date_creation') or '')[:10],
            (f.get('date_echeance') or '')[:10],
            (f.get('date_paiement') or '')[:10],
            f"{ht:.2f}",
            f.get('tva', ''),
            f"{ttc:.2f}",
            f.get('statut', ''),
            f.get('notes', ''),
        ])

    # Ligne de totaux
    writer.writerow([])
    writer.writerow([
        f"TOTAL ({len(factures)} facture{'s' if len(factures) > 1 else ''}, {nb_payees} payee{'s' if nb_payees > 1 else ''})",
        '', '',  '', '', '',
        f"{total_ht:.2f}",
        '',
        f"{total_ttc:.2f}",
        '', '',
    ])

    # UTF-8 BOM pour compatibilité Excel
    content = '\ufeff' + output.getvalue()

    if mois and annee:
        filename = f"factures_{annee}-{mois:02d}.csv"
    else:
        filename = f"factures_export_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([content.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
