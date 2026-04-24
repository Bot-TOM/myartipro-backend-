from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from utils.supabase_client import get_supabase_for_user
from utils.auth import get_current_user

router = APIRouter()


class ModeleCreate(BaseModel):
    titre: str
    prestations: list[dict]
    tva: float = 20
    acompte_pct: int = 0
    notes: Optional[str] = None
    urgence: str = "normal"
    charge: Optional[str] = None


@router.get("")
async def list_modeles(current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]) \
        .table("modeles") \
        .select("*") \
        .eq("user_id", current_user["id"]) \
        .order("created_at", desc=True) \
        .execute()
    return result.data


@router.post("", status_code=201)
async def create_modele(data: ModeleCreate, current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]) \
        .table("modeles") \
        .insert({
            "user_id": current_user["id"],
            "titre": data.titre,
            "prestations": data.prestations,
            "tva": data.tva,
            "acompte_pct": data.acompte_pct,
            "notes": data.notes,
            "urgence": data.urgence,
            "charge": data.charge,
        }) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du modèle")
    return result.data[0]


@router.delete("/{modele_id}", status_code=204)
async def delete_modele(modele_id: str, current_user: dict = Depends(get_current_user)):
    result = await get_supabase_for_user(current_user["token"]) \
        .table("modeles") \
        .delete() \
        .eq("id", modele_id) \
        .eq("user_id", current_user["id"]) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Modèle introuvable")
