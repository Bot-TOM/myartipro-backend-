from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from models.devis import Prestation


class FactureUpdate(BaseModel):
    statut: Optional[str] = None
    date_echeance: Optional[str] = None
    date_paiement: Optional[str] = None
    mode_paiement: Optional[str] = None
    notes: Optional[str] = None


class FactureResponse(BaseModel):
    id: str
    user_id: str
    client_id: str
    devis_id: Optional[str] = None
    numero: str
    titre: str
    prestations: list
    montant_ht: float
    tva: float
    montant_ttc: float
    statut: str
    date_creation: datetime
    date_echeance: Optional[datetime] = None
    date_paiement: Optional[datetime] = None
    notes: Optional[str] = None
    stripe_checkout_url: Optional[str] = None
    clients: Optional[dict] = None
