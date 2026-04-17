from fastapi import APIRouter, HTTPException, Depends
from models.client import ClientCreate, ClientUpdate
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user

router = APIRouter()


def _ensure_profile(user_id: str, email: str) -> None:
    try:
        get_supabase().table("profiles").insert({"id": user_id, "email": email}).execute()
    except Exception:
        pass


@router.get("")
async def list_clients(current_user: dict = Depends(get_current_user)):
    result = get_supabase_for_user(current_user["token"]).table("clients").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return result.data


@router.post("", status_code=201)
async def create_client(client: ClientCreate, current_user: dict = Depends(get_current_user)):
    _ensure_profile(current_user["id"], current_user.get("email", ""))
    data = client.model_dump()
    data["user_id"] = current_user["id"]
    result = get_supabase_for_user(current_user["token"]).table("clients").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.get("/{client_id}")
async def get_client(client_id: str, current_user: dict = Depends(get_current_user)):
    result = get_supabase_for_user(current_user["token"]).table("clients").select("*").eq("id", client_id).eq("user_id", current_user["id"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return result.data


@router.put("/{client_id}")
async def update_client(client_id: str, client: ClientUpdate, current_user: dict = Depends(get_current_user)):
    data = client.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = get_supabase_for_user(current_user["token"]).table("clients").update(data).eq("id", client_id).eq("user_id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return result.data[0]


@router.delete("/{client_id}")
async def delete_client(client_id: str, current_user: dict = Depends(get_current_user)):
    result = get_supabase_for_user(current_user["token"]).table("clients").delete().eq("id", client_id).eq("user_id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return {"message": "Client supprimé"}
