from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date


class RappelCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    client_id: Optional[str] = None
    date_rappel: str
    commentaire: str


class RappelUpdate(BaseModel):
    client_id: Optional[str] = None
    date_rappel: Optional[str] = None
    commentaire: Optional[str] = None
    fait: Optional[bool] = None


class RappelResponse(BaseModel):
    id: str
    user_id: str
    client_id: Optional[str] = None
    date_rappel: str
    commentaire: str
    fait: bool
    created_at: datetime
