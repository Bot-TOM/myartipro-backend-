from fastapi import APIRouter, HTTPException, Depends
from models.rappel import RappelCreate, RappelUpdate
from utils.supabase_client import get_supabase_for_user
from utils.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_rappels(current_user: dict = Depends(get_current_user)):
    """Liste tous les rappels de l'utilisateur, tries par date."""
    db = get_supabase_for_user(current_user["token"])
    result = (
        db.table("rappels")
        .select("*, clients(nom, prenom)")
        .eq("user_id", current_user["id"])
        .order("date_rappel", desc=False)
        .execute()
    )
    return result.data


@router.post("", status_code=201)
async def create_rappel(
    data: RappelCreate,
    current_user: dict = Depends(get_current_user),
):
    """Cree un nouveau rappel."""
    db = get_supabase_for_user(current_user["token"])
    rappel_data = {
        "user_id": current_user["id"],
        "client_id": data.client_id,
        "date_rappel": data.date_rappel,
        "commentaire": data.commentaire,
    }

    result = db.table("rappels").insert(rappel_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la creation")
    return result.data[0]


@router.put("/{rappel_id}")
async def update_rappel(
    rappel_id: str,
    data: RappelUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Modifie un rappel existant."""
    db = get_supabase_for_user(current_user["token"])
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnee a mettre a jour")

    result = (
        db.table("rappels")
        .update(update_data)
        .eq("id", rappel_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Rappel non trouve")
    return result.data[0]


@router.delete("/{rappel_id}")
async def delete_rappel(
    rappel_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Supprime un rappel."""
    db = get_supabase_for_user(current_user["token"])
    result = (
        db.table("rappels")
        .delete()
        .eq("id", rappel_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Rappel non trouve")
    return {"message": "Rappel supprime"}
