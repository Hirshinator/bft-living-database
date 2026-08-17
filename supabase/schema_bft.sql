-- ============================================================================
-- BFT Supabase project — schema
-- Run this once in the BFT project's SQL editor (Dashboard → SQL → New query).
-- Two tables: grassroots_business + business_leaders. PUBLIC READ (the Vercel
-- app reads them live via the anon key); writes require the service_role key.
-- ============================================================================

create extension if not exists moddatetime schema extensions;

-- ---- shared column set (kept identical across both tables) ------------------
create table if not exists public.grassroots_business (
  id                 bigint generated always as identity primary key,
  bft_id             text unique,
  name               text not null,
  tier               text default 'grassroots',
  network            text default 'bft',
  stance             text,
  alliance_score     int,
  affiliation        text,
  company            text,
  industry           text,
  expertise          text,
  profession         text,
  platform           text,
  related            text,
  links              text,
  evidence           text,
  source             text,
  added_by           text,
  needs_verification text,
  -- investor/operator profile — format adapted from Aleph's "The Spreadsheet" (design only)
  investor_kind       text,     -- Angel / VC / Micro VC / Corp VC / Angel fund / Operator-Angel
  primary_interest    text,     -- main sector focus
  other_interests     text,     -- freeform secondary interests
  min_investment      numeric,  -- typical check size floor
  max_investment      numeric,  -- typical check size ceiling
  activity_level      text,     -- '1. High' | '2. Medium' | '3. Low' | '4. None'
  notable_investments text,     -- proof-of-activity ("investments of note")
  when_to_approach    text,     -- stage/criteria to engage
  follow_on           boolean,  -- does follow-on rounds?
  self_guidelines     text,     -- ONLY the subject edits: how they want to be approached
  contact_via         text,     -- preferred PUBLIC channel (LinkedIn / firm form)
  is_jewish          boolean default false,
  is_bft             boolean default true,
  tags               text[] default '{}',
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);

create table if not exists public.business_leaders (
  id                 bigint generated always as identity primary key,
  bft_id             text unique,
  name               text not null,
  tier               text default 'leader',
  network            text default 'bft',
  stance             text,
  alliance_score     int,
  affiliation        text,
  company            text,
  industry           text,
  expertise          text,
  profession         text,
  platform           text,
  related            text,
  links              text,
  evidence           text,
  source             text,
  added_by           text,
  needs_verification text,
  -- investor/operator profile — format adapted from Aleph's "The Spreadsheet" (design only)
  investor_kind       text,     -- Angel / VC / Micro VC / Corp VC / Angel fund / Operator-Angel
  primary_interest    text,     -- main sector focus
  other_interests     text,     -- freeform secondary interests
  min_investment      numeric,  -- typical check size floor
  max_investment      numeric,  -- typical check size ceiling
  activity_level      text,     -- '1. High' | '2. Medium' | '3. Low' | '4. None'
  notable_investments text,     -- proof-of-activity ("investments of note")
  when_to_approach    text,     -- stage/criteria to engage
  follow_on           boolean,  -- does follow-on rounds?
  self_guidelines     text,     -- ONLY the subject edits: how they want to be approached
  contact_via         text,     -- preferred PUBLIC channel (LinkedIn / firm form)
  is_jewish          boolean default false,
  is_bft             boolean default true,
  tags               text[] default '{}',
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);

-- keep updated_at fresh on every UPDATE
drop trigger if exists set_updated_at on public.grassroots_business;
create trigger set_updated_at before update on public.grassroots_business
  for each row execute function extensions.moddatetime(updated_at);
drop trigger if exists set_updated_at on public.business_leaders;
create trigger set_updated_at before update on public.business_leaders
  for each row execute function extensions.moddatetime(updated_at);

-- Row Level Security: anon may READ; nobody writes without the service_role key.
alter table public.grassroots_business enable row level security;
alter table public.business_leaders   enable row level security;

drop policy if exists "public read grassroots" on public.grassroots_business;
create policy "public read grassroots" on public.grassroots_business
  for select to anon, authenticated using (true);
drop policy if exists "public read leaders" on public.business_leaders;
create policy "public read leaders" on public.business_leaders
  for select to anon, authenticated using (true);

-- indexes for the filters the app uses
create index if not exists grassroots_stance_idx on public.grassroots_business (stance);
create index if not exists leaders_stance_idx    on public.business_leaders   (stance);
create index if not exists grassroots_jewish_idx on public.grassroots_business (is_jewish);
create index if not exists leaders_jewish_idx    on public.business_leaders   (is_jewish);
