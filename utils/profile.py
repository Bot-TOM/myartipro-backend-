from utils.supabase_client import get_supabase


def ensure_profile(user_id: str, email: str = "") -> None:
    """Garantit l'existence d'une ligne dans profiles. Silencieux si déjà présent."""
    try:
        get_supabase().table("profiles").insert({
            "id": user_id,
            "email": email,
        }).execute()
    except Exception:
        pass
