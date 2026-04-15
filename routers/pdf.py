import traceback
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user

router = APIRouter()


def _get_plombier(db, user_id: str) -> dict:
    """Récupère le profil plombier, retourne un dict vide par défaut si absent."""
    try:
        result = db.table("profiles").select("*").eq("id", user_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception:
        pass
    # Profil minimal si absent
    return {"nom": "", "prenom": "", "entreprise": "", "siret": "", "telephone": "", "adresse": "", "email": ""}


@router.get("/public/devis/{devis_id}")
async def public_devis_pdf(devis_id: str):
    """PDF public d'un devis envoye — accessible sans auth (lien email client)."""
    from services.pdf_service import generer_pdf_devis

    db = get_supabase()

    try:
        result = db.table("devis").select("*, clients(nom, prenom, email, telephone, adresse)").eq("id", devis_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur DB devis: {str(e)}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Devis non trouve")

    devis = result.data[0]

    if devis.get("statut") not in ("envoyé", "relancé", "accepté", "facturé"):
        raise HTTPException(status_code=403, detail="Ce devis n'est pas accessible")

    plombier = _get_plombier(db, devis["user_id"])

    try:
        pdf_bytes = bytes(generer_pdf_devis(devis, devis.get("clients") or {}, plombier))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur generation PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{devis.get("numero", "devis")}.pdf"'
        },
    )


@router.get("/facture/{facture_id}")
async def download_facture_pdf(
    facture_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Génère et télécharge le PDF d'une facture."""
    from services.pdf_service import generer_pdf_facture

    db = get_supabase_for_user(current_user["token"])

    try:
        result = db.table("factures").select("*, clients(nom, prenom, email, telephone, adresse)").eq("id", facture_id).eq("user_id", current_user["id"]).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur DB facture: {str(e)}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    facture = result.data[0]
    plombier = _get_plombier(db, current_user["id"])

    try:
        pdf_bytes = bytes(generer_pdf_facture(facture, facture.get("clients") or {}, plombier))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur generation PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{facture.get("numero", "facture")}.pdf"'
        },
    )


@router.get("/devis/{devis_id}")
async def download_devis_pdf(
    devis_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Genere et telecharge le PDF d'un devis."""
    from services.pdf_service import generer_pdf_devis

    db = get_supabase_for_user(current_user["token"])

    try:
        result = db.table("devis").select("*, clients(nom, prenom, email, telephone, adresse)").eq("id", devis_id).eq("user_id", current_user["id"]).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur DB devis: {str(e)}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Devis non trouve")

    devis = result.data[0]
    plombier = _get_plombier(db, current_user["id"])

    try:
        pdf_bytes = bytes(generer_pdf_devis(devis, devis.get("clients") or {}, plombier))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur generation PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{devis.get("numero", "devis")}.pdf"'
        },
    )
