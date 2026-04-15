import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import Optional
from utils.supabase_client import get_supabase_for_user
from utils.auth import get_current_user

router = APIRouter()


class ProfileUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    entreprise: Optional[str] = None
    siret: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None

    @field_validator("siret")
    @classmethod
    def valider_siret(cls, v):
        if v is not None and v != "" and not re.match(r"^\d{14}$", v):
            raise ValueError("Le SIRET doit contenir exactement 14 chiffres")
        return v


@router.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Récupère le profil du plombier connecté."""
    result = (
        get_supabase_for_user(current_user["token"]).table("profiles")
        .select("*")
        .eq("id", current_user["id"])
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Profil non trouvé")
    return result.data


@router.put("/me")
async def update_profile(
    data: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Met à jour le profil du plombier connecté."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

    result = (
        get_supabase_for_user(current_user["token"]).table("profiles")
        .update(update_data)
        .eq("id", current_user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Profil non trouvé")
    return result.data[0]
