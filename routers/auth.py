import re
import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import Optional
from utils.supabase_client import get_supabase_for_user, get_supabase
from utils.auth import get_current_user

router = APIRouter()


class RegisterData(BaseModel):
    email: str
    password: str
    nom: str
    prenom: str
    entreprise: Optional[str] = None
    siret: Optional[str] = None
    telephone: Optional[str] = None

    @field_validator("siret")
    @classmethod
    def valider_siret(cls, v):
        if v and not re.match(r"^\d{14}$", v):
            raise ValueError("Le SIRET doit contenir exactement 14 chiffres")
        return v


@router.post("/register", status_code=201)
async def register(data: RegisterData):
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        raise HTTPException(status_code=500, detail="Supabase non configuré")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{supabase_url}/auth/v1/admin/users",
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json"},
            json={"email": data.email, "password": data.password, "email_confirm": True},
        )

    if resp.status_code not in (200, 201):
        detail = resp.json().get("msg") or resp.json().get("message") or "Erreur création compte"
        raise HTTPException(status_code=400, detail=detail)

    user_id = resp.json().get("id")
    if not user_id:
        raise HTTPException(status_code=500, detail="Impossible de récupérer l'ID utilisateur")

    try:
        await get_supabase().table("profiles").insert({
            "id": user_id, "email": data.email, "nom": data.nom, "prenom": data.prenom,
            "entreprise": data.entreprise or None, "siret": data.siret or None, "telephone": data.telephone or None,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compte créé mais erreur profil : {str(e)}")

    return {"message": "Compte créé avec succès", "user_id": user_id}


class ProfileUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    entreprise: Optional[str] = None
    siret: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    logo_url: Optional[str] = None
    stripe_enabled: Optional[bool] = None
    moyens_paiement: Optional[list[str]] = None
    instructions_paiement: Optional[str] = None
    onboarding_done: Optional[bool] = None
    regime_tva: Optional[str] = None

    @field_validator("regime_tva")
    @classmethod
    def valider_regime_tva(cls, v):
        if v is not None and v not in ("franchise", "reel"):
            raise ValueError("regime_tva doit être 'franchise' ou 'reel'")
        return v

    @field_validator("siret")
    @classmethod
    def valider_siret(cls, v):
        if v is not None and v != "" and not re.match(r"^\d{14}$", v):
            raise ValueError("Le SIRET doit contenir exactement 14 chiffres")
        return v


@router.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user)):
    db_user = get_supabase_for_user(current_user["token"])
    result = await db_user.table("profiles").select("*").eq("id", current_user["id"]).single().execute()
    if not result.data:
        try:
            await get_supabase().table("profiles").insert({
                "id": current_user["id"],
                "email": current_user.get("email", ""),
            }).execute()
        except Exception:
            pass
        result = await db_user.table("profiles").select("*").eq("id", current_user["id"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profil non trouvé")
    return result.data


@router.put("/me")
async def update_profile(data: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = await get_supabase_for_user(current_user["token"]).table("profiles").update(update_data).eq("id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profil non trouvé")
    return result.data[0]
