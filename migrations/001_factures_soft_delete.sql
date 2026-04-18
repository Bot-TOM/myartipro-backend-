-- Migration 001 : soft-delete des factures
-- Conformité légale France : une facture émise doit être conservée 10 ans.
-- On ne supprime jamais réellement une facture émise ou payée ; on la masque.

alter table public.factures
  add column if not exists deleted_at timestamptz;

-- Index partiel pour lister rapidement les factures non supprimées
create index if not exists idx_factures_not_deleted
  on public.factures (user_id, date_creation desc)
  where deleted_at is null;
