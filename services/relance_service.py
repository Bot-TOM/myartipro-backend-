"""Service de relance automatique des devis sans réponse (async)."""

from datetime import datetime, timedelta, timezone
from utils.supabase_client import get_supabase
from services.email_service import envoyer_relance_email

DELAI_RELANCE_JOURS = 3


async def relancer_devis_sans_reponse():
    """Relance les devis envoyés depuis +3 jours sans réponse.

    - Statut 'envoyé' uniquement → passe à 'relancé' après envoi
    - Ignoré si le client n'a pas d'email
    """
    print(f"[Relance] Démarrage — {datetime.now()}")
    db = get_supabase()
    seuil = (datetime.now(timezone.utc) - timedelta(days=DELAI_RELANCE_JOURS)).isoformat()

    result = await (
        db.table("devis")
        .select("id, numero, titre, user_id, date_envoi, clients(nom, prenom, email)")
        .eq("statut", "envoyé")
        .lt("date_envoi", seuil)
        .execute()
    )
    devis_a_relancer = result.data or []
    print(f"[Relance] {len(devis_a_relancer)} devis à relancer")

    for devis in devis_a_relancer:
        client = devis.get("clients")
        if not client or not client.get("email"):
            continue

        artisan = (await (
            db.table("profiles")
            .select("nom, prenom, entreprise")
            .eq("id", devis["user_id"])
            .single()
            .execute()
        )).data
        if not artisan:
            continue

        artisan_nom = artisan.get("entreprise") or f"{artisan.get('prenom', '')} {artisan.get('nom', '')}".strip()
        client_nom = f"{client.get('prenom', '')} {client.get('nom', '')}".strip()
        date_envoi = datetime.fromisoformat(devis["date_envoi"].replace("Z", "+00:00"))
        jours = (datetime.now(date_envoi.tzinfo) - date_envoi).days

        try:
            envoyer_relance_email(
                client_email=client["email"],
                client_nom=client_nom,
                artisan_nom=artisan_nom,
                devis_numero=devis["numero"],
                jours_depuis_envoi=jours,
            )
            await db.table("devis").update({
                "statut": "relancé",
                "date_relance": datetime.now(timezone.utc).isoformat(),
            }).eq("id", devis["id"]).execute()
            print(f"[Relance] {devis['numero']} → relancé ({client['email']})")
        except Exception as e:
            print(f"[Relance] {devis['numero']} → erreur: {e}")

    print(f"[Relance] Terminé — {datetime.now()}")
