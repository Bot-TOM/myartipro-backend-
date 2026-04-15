import os
import httpx
from fastapi import HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    token: str = Query(None, alias="token"),
) -> dict:
    """Verifie le JWT Supabase et retourne l'utilisateur authentifie.
    Accepte le token via header Authorization OU via ?token= query param."""
    if credentials:
        token = credentials.credentials
    elif not token:
        raise HTTPException(status_code=401, detail="Token manquant")
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    try:
        async with httpx.AsyncClient(verify=True, timeout=10) as client:
            response = await client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": supabase_key,
                },
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de connexion auth: {str(e)}")

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    user_data = response.json()
    user_id = user_data.get("id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Utilisateur non trouvé")

    return {"id": user_id, "email": user_data.get("email", ""), "token": token}
