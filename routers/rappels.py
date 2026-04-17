from fastapi import APIRouter, HTTPException, Depends
from models.rappel import RappelCreate, RappelUpdate
from utils.supabase_client import get_supabase_for_user
from utils.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_rappels(current_user: dict = Depends(get_current_user)):
    result = await (
        get_supabase_for_user(current_user["token"]).table("rappels")
        .select("*, clients(nom, prenom)")
        .eq("user_id", current_user["id"])
        .order("date_rappel", desc=False)
        .order("heure_rappel", desc=False, nullsfirst=False)
        .execute()
    )
    return result.data


@router.post("", status_code=201)
async def create_rappel(data: RappelCreate, current_user: dict = Depends(get_current_user)):
    db = get_supabase_for_user(current_user["token"])
    result = await db.table("rappels").insert({
        "user_id": current_user["id"],
        "client_id": data.client_id,
        "date_rappel": data.date_rappel,
        "heure_rappel": data.heure_rappel or None,
        "commentaire": data.commentaire,
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.put("/{rappel_id}")
async def update_rappel(rappel_id: str, data: RappelUpdate, current_user: dict = Depends(get_current_user)):
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = await (
        get_supabase_for_user(current_user["token"]).table("rappels")
        .update(update_data)
        .eq("id", rappel_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Rappel non trouvé")
    return result.data[0]


@router.delete("/{rappel_id}")
async def delete_rappel(rappel_id: str, current_user: dict = Depends(get_current_user)):
    result = await (
        get_supabase_for_user(current_user["token"]).table("rappels")
        .delete()
        .eq("id", rappel_id)
        .eq("user_id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Rappel non trouvé")
    return {"message": "Rappel supprimé"}
