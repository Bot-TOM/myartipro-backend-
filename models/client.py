from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ClientCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    nom: str
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None
    statut: Optional[str] = "nouveau"


class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None
    statut: Optional[str] = None


class ClientResponse(BaseModel):
    id: str
    user_id: str
    nom: str
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None
    statut: Optional[str] = "nouveau"
    created_at: datetime
