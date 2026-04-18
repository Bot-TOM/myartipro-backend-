-- Migration 005 : acompte sur devis
-- Pourcentage d'acompte demandé à la commande (0 = pas d'acompte)
ALTER TABLE devis
  ADD COLUMN IF NOT EXISTS acompte_pct integer DEFAULT 0
    CHECK (acompte_pct >= 0 AND acompte_pct <= 100);
