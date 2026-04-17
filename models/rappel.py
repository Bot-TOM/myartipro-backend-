from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RappelCreate(BaseModel):
    client_id: Optional[str] = None
    date_rappel: str
    heure_rappel: Optional[str] = None
    commentaire: str


class RappelUpdate(BaseModel):
    client_id: Optional[str] = None
    date_rappel: Optional[str] = None
    heure_rappel: Optional[str] = None
    commentaire: Optional[str] = None
    fait: Optional[bool] = None


class RappelResponse(BaseModel):
    id: str
    user_id: str
    client_id: Optional[str] = None
    date_rappel: str
    heure_rappel: Optional[str] = None
    commentaire: str
    fait: bool
    created_at: datetime
