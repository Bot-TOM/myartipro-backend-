"""Services de relance automatique : devis sans réponse + factures impayées."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from utils.supabase_client import get_supabase
from services.email_service import envoyer_relance_email, envoyer_relance_facture_email

DELAI_RELANCE_JOURS = 3

# Paliers de relance facture (jours depuis date_creation).
# Ordre : palier N déclenché si relances_count == N-1 ET jours >= seuil.
RELANCE_FACTURE_PALIERS = {
    1: 30,
    2: 45,
    3: 60,
}


async def relancer_devis_sans_reponse():
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


def _palier_a_declencher(relances_count: int, jours: int) -> Optional[int]:
    """Retourne le palier à déclencher (1/2/3) ou None."""
    prochain = relances_count + 1
    seuil = RELANCE_FACTURE_PALIERS.get(prochain)
    if seuil is None:
        return None
    return prochain if jours >= seuil else None


async def relancer_factures_impayees():
    """
    Relance quotidienne des factures impayées.
    Paliers : J+30 (cordial), J+45 (ferme), J+60 (mise en demeure amiable).
    """
    print(f"[RelanceFacture] Démarrage — {datetime.now()}")
    db = get_supabase()

    result = await (
        db.table("factures")
        .select(
            "id, numero, user_id, date_creation, montant_ttc, "
            "stripe_checkout_url, relances_count, clients(nom, prenom, email)"
        )
        .eq("statut", "émise")
        .is_("deleted_at", "null")
        .lt("relances_count", 3)
        .execute()
    )
    factures = result.data or []
    print(f"[RelanceFacture] {len(factures)} factures candidates")

    now = datetime.now(timezone.utc)
    relancees = 0

    for f in factures:
        client = f.get("clients")
        if not client or not client.get("email"):
            continue

        date_creation = datetime.fromisoformat(f["date_creation"].replace("Z", "+00:00"))
        jours = (now - date_creation).days
        palier = _palier_a_declencher(f.get("relances_count", 0), jours)
        if palier is None:
            continue

        artisan = (await (
            db.table("profiles")
            .select("nom, prenom, entreprise")
            .eq("id", f["user_id"])
            .single()
            .execute()
        )).data
        if not artisan:
            continue

        artisan_nom = artisan.get("entreprise") or f"{artisan.get('prenom', '')} {artisan.get('nom', '')}".strip()
        client_nom = f"{client.get('prenom', '')} {client.get('nom', '')}".strip()

        try:
            envoyer_relance_facture_email(
                client_email=client["email"],
                client_nom=client_nom,
                artisan_nom=artisan_nom,
                facture_numero=f["numero"],
                montant_ttc=float(f.get("montant_ttc") or 0),
                jours_depuis_emission=jours,
                palier=palier,
                lien_paiement=f.get("stripe_checkout_url") or "",
            )
            await db.table("factures").update({
                "relances_count": palier,
                "derniere_relance_at": now.isoformat(),
            }).eq("id", f["id"]).execute()
            relancees += 1
            print(f"[RelanceFacture] {f['numero']} → palier {palier} ({client['email']})")
        except Exception as e:
            print(f"[RelanceFacture] {f['numero']} → erreur: {e}")

    print(f"[RelanceFacture] Terminé — {relancees} relances envoyées")
