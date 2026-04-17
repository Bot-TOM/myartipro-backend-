from utils.supabase_client import get_supabase


def ensure_profile(user_id: str, email: str = "") -> None:
    """
    Garantit l'existence d'une ligne dans profiles pour user_id.
    Résout la FK xxx_user_id_fkey sur toutes les tables (clients, devis, rappels…).
    Silencieux si le profil existe déjà.
    """
    try:
        get_supabase().table("profiles").insert({
            "id": user_id,
            "email": email,
        }).execute()
    except Exception:
        pass  # Profil déjà présent — pas une erreur
