from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Prestation(BaseModel):
    description: str
    quantite: float = 1.0
    prix_unitaire: float


class DevisCreate(BaseModel):
    client_id: str
    titre: str
    prestations: List[Prestation]
    tva: float = 20.0
    acompte_pct: int = 0
    date_validite: Optional[str] = None
    notes: Optional[str] = None
    urgence: Optional[str] = "normal"
    charge: Optional[str] = None


class DevisUpdate(BaseModel):
    client_id: Optional[str] = None
    titre: Optional[str] = None
    prestations: Optional[List[Prestation]] = None
    tva: Optional[float] = None
    acompte_pct: Optional[int] = None
    statut: Optional[str] = None
    date_validite: Optional[str] = None
    notes: Optional[str] = None
    urgence: Optional[str] = None
    charge: Optional[str] = None


class DevisResponse(BaseModel):
    id: str
    user_id: str
    client_id: str
    numero: str
    titre: str
    prestations: list
    montant_ht: float
    tva: float
    montant_ttc: float
    acompte_pct: int = 0
    statut: str
    date_creation: datetime
    date_envoi: Optional[datetime] = None
    date_validite: Optional[datetime] = None
    date_relance: Optional[datetime] = None
    date_acceptation: Optional[datetime] = None
    notes: Optional[str] = None
    urgence: Optional[str] = "normal"
    charge: Optional[str] = None
    acceptance_token: Optional[str] = None
    clients: Optional[dict] = None
