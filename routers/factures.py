import csv
import io
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from models.facture import FactureUpdate
from utils.supabase_client import get_supabase_for_user
from utils.auth import get_current_user
from datetime import datetime, timezone

router = APIRouter()


async def _generer_numero_facture(user_id: str, token: str) -> str:
    year = datetime.now().year
    prefix = f"FAC-{year}-"
    result = await (
        get_supabase_for_user(token).table("factures")
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


@router.get("")
async def list_factures(current_user: dict = Depends(get_current_user)):
    result = await (
        get_supabase_for_user(current_user["token"]).table("factures")
        .select("*, clients(nom, prenom, email)")
        .eq("user_id", current_user["id"])
        .order("date_creation", desc=True)
        .execute()
    )
    return result.data


@router.post("/depuis-devis/{devis_id}", status_code=201)
async def creer_facture_depuis_devis(devis_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])

    devis = (await (
        db.table("devis").select("*")
        .eq("id", devis_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )).data
    if not devis:
        raise HTTPException(status_code=404, detail="Devis non trouvé")
    if devis["statut"] not in ("accepté", "envoyé", "relancé"):
        raise HTTPException(status_code=400, detail="Le devis doit être envoyé, relancé ou accepté")

    existing = (await db.table("factures").select("id").eq("devis_id", devis_id).execute()).data
    if existing:
        raise HTTPException(status_code=400, detail="Ce devis a déjà été converti en facture")

    numero = await _generer_numero_facture(current_user["id"], current_user["token"])
    result = await db.table("factures").insert({
        "user_id": current_user["id"],
        "client_id": devis["client_id"],
        "devis_id": devis_id,
        "numero": numero,
        "titre": devis["titre"],
        "prestations": devis["prestations"],
        "montant_ht": float(devis["montant_ht"]),
        "tva": float(devis["tva"]),
        "montant_ttc": float(devis["montant_ttc"]),
        "notes": devis.get("notes"),
        "date_echeance": None,
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la facture")

    await db.table("devis").update({"statut": "facturé"}).eq("id", devis_id).execute()
    return result.data[0]


@router.get("/{facture_id}")
async def get_facture(facture_id: str, current_user: dict = Depends(get_current_user)):
    result = await (
        get_supabase_for_user(current_user["token"]).table("factures")
        .select("*, clients(nom, prenom, email, telephone, adresse)")
        .eq("id", facture_id)
        .eq("user_id", current_user["id"])
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return result.data


@router.put("/{facture_id}")
async def update_facture(facture_id: str, data: FactureUpdate, current_user: dict = Depends(get_current_user)):
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = await (
        get_supabase_for_user(current_user["token"]).table("factures")
        .update(update_data)
        .eq("id", facture_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return result.data[0]


@router.delete("/{facture_id}")
async def delete_facture(facture_id: str, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    check = await db.table("factures").select("id").eq("id", facture_id).eq("user_id", current_user["id"]).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    await db.table("factures").delete().eq("id", facture_id).eq("user_id", current_user["id"]).execute()
    return {"message": "Facture supprimée"}


@router.get("/export/csv")
async def export_factures_csv(current_user: dict = Depends(get_current_user)):
    result = await (
        get_supabase_for_user(current_user["token"]).table("factures")
        .select("*, clients(nom, prenom)")
        .eq("user_id", current_user["id"])
        .order("date_creation", desc=False)
        .execute()
    )
    factures = result.data or []
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Numero', 'Client', 'Date creation', 'Date echeance', 'Date paiement', 'Montant HT', 'TVA %', 'Montant TTC', 'Statut', 'Notes'])
    for f in factures:
        client_nom = f"{f['clients'].get('prenom', '')} {f['clients'].get('nom', '')}".strip() if f.get('clients') else ''
        writer.writerow([f.get('numero', ''), client_nom, (f.get('date_creation') or '')[:10], (f.get('date_echeance') or '')[:10], (f.get('date_paiement') or '')[:10], f.get('montant_ht', ''), f.get('tva', ''), f.get('montant_ttc', ''), f.get('statut', ''), f.get('notes', '')])
    output.seek(0)
    filename = f"factures_export_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
