-- Suivi des relances automatiques sur factures impayées.
-- Paliers J+30, J+45, J+60 — cf. art. L441-10 Code de commerce.

alter table public.factures
  add column if not exists relances_count int not null default 0,
  add column if not exists derniere_relance_at timestamptz;

-- Index pour le scheduler quotidien : ne scanner que les factures émises actives.
create index if not exists idx_factures_relance_scheduler
  on public.factures (date_creation)
  where statut = 'émise' and deleted_at is null and relances_count < 3;
