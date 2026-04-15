"""Service de relance automatique des devis sans réponse.

Utilise get_supabase() (service_role) car le scheduler tourne sans contexte
utilisateur — c'est une opération admin qui scanne tous les comptes.
"""

from datetime import datetime, timedelta
from utils.supabase_client import get_supabase
from services.email_service import envoyer_relance_email

DELAI_RELANCE_JOURS = 3


def relancer_devis_sans_reponse():
    """Vérifie les devis envoyés depuis +3 jours et envoie une relance.

    - Ne relance que les devis au statut "envoyé"
    - Ne relance qu'une seule fois (passe le statut à "relancé")
    - Ne relance que si le client a un email
    """
    print(f"[Relance] Vérification des devis à relancer — {datetime.now()}")

    db = get_supabase()
    from datetime import timezone
    seuil = (datetime.now(timezone.utc) - timedelta(days=DELAI_RELANCE_JOURS)).isoformat()

    # Récupérer les devis envoyés il y a + de 3 jours
    result = (
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
            print(f"[Relance] {devis['numero']} — pas d'email client, ignoré")
            continue

        # Récupérer le nom du plombier
        plombier = (
            db.table("profiles")
            .select("nom, prenom, entreprise")
            .eq("id", devis["user_id"])
            .single()
            .execute()
        ).data

        if not plombier:
            print(f"[Relance] {devis['numero']} — profil plombier introuvable, ignoré")
            continue

        plombier_nom = plombier.get("entreprise") or f"{plombier.get('prenom', '')} {plombier.get('nom', '')}".strip()
        client_nom = f"{client.get('prenom', '')} {client.get('nom', '')}".strip()

        # Calcul des jours depuis l'envoi
        date_envoi = datetime.fromisoformat(devis["date_envoi"].replace("Z", "+00:00"))
        jours = (datetime.now(date_envoi.tzinfo) - date_envoi).days

        try:
            envoyer_relance_email(
                client_email=client["email"],
                client_nom=client_nom,
                plombier_nom=plombier_nom,
                devis_numero=devis["numero"],
                jours_depuis_envoi=jours,
            )

            # Passer le statut à "relancé" et enregistrer la date
            db.table("devis").update({
                "statut": "relancé",
                "date_relance": datetime.now(timezone.utc).isoformat(),
            }).eq("id", devis["id"]).execute()
            print(f"[Relance] {devis['numero']} — relance envoyée à {client['email']}")

        except Exception as e:
            print(f"[Relance] {devis['numero']} — erreur: {e}")

    print(f"[Relance] Terminé — {datetime.now()}")
