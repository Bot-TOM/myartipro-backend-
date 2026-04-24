-- Migration 006 : table modeles (templates de devis réutilisables)
CREATE TABLE IF NOT EXISTS modeles (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  titre text NOT NULL,
  prestations jsonb NOT NULL DEFAULT '[]',
  tva numeric NOT NULL DEFAULT 20,
  acompte_pct integer NOT NULL DEFAULT 0,
  notes text,
  urgence text NOT NULL DEFAULT 'normal',
  charge text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE modeles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "modeles_own" ON modeles
  FOR ALL USING (auth.uid() = user_id);
