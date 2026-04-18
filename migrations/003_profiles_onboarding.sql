-- Flag onboarding : la checklist d'accueil disparait a 100% ou sur skip.
-- Valeur false par defaut = nouveau user voit la checklist une fois.

alter table public.profiles
  add column if not exists onboarding_done boolean not null default false;
