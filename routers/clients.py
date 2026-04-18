from fastapi import APIRouter, HTTPException, Depends
from models.client import ClientCreate, ClientUpdate
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user

router = APIRouter()


async def _ensure_profile(user_id: str, email: str) -> None:
    """Crée le profil s'il manque. Idempotent — silencieux si déjà présent."""
    db = get_supabase()
    try:
        existing = await db.table("profiles").select("id").eq("id", user_id).execute()
        if existing.data:
            return
    except Exception as e:
        print(f"[ensure_profile] check err: {e}")
    try:
        await db.table("profiles").insert({
            "id": user_id, "email": email, "nom": "", "prenom": "",
        }).execute()
        print(f"[ensure_profile] créé: {user_id}")
    except Exception as e:
        print(f"[ensure_profile] create err: {e}")


@router.get("")
async def list_clients(current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("clients").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return result.data


@router.post("", status_code=201)
async def create_client(client: ClientCreate, current_user: dict = Depends(get_current_user)):
    await _ensure_profile(current_user["id"], current_user.get("email", ""))
    data = client.model_dump()
    data["user_id"] = current_user["id"]
    result = await get_supabase_for_user(current_user["token"]).table("clients").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.get("/{client_id}")
async def get_client(client_id: str, current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("clients").select("*").eq("id", client_id).eq("user_id", current_user["id"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return result.data


@router.put("/{client_id}")
async def update_client(client_id: str, client: ClientUpdate, current_user: dict = Depends(get_current_user)):
    data = client.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = await get_supabase_for_user(current_user["token"]).table("clients").update(data).eq("id", client_id).eq("user_id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return result.data[0]


@router.delete("/{client_id}")
async def delete_client(client_id: str, current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]).table("clients").delete().eq("id", client_id).eq("user_id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return {"message": "Client supprimé"}
