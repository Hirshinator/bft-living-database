-- ============================================================================
-- Jewish Supabase project — schema
-- Run this once in the JEWISH project's SQL editor.
-- Two tables: grassroots_business + business_leaders.
-- PRIVATE: Row Level Security is ON with NO anon/authenticated read policy, so
-- this data is NOT publicly readable. It is reached only via the service_role
-- key (server-side, behind a passcode) or the dashboard. This is deliberate —
-- a list keyed on religion is sensitive and should not sit on a public endpoint.
-- ============================================================================

create extension if not exists moddatetime schema extensions;

create table if not exists public.grassroots_business (
  id                 bigint generated always as identity primary key,
  bft_id             text unique,
  name               text not null,
  tier               text default 'grassroots',
  network            text default 'jewish',
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
  jewish_basis       text,   -- HOW we know it's Jewish-owned (sourced, self-identified, etc.)
  is_jewish          boolean default true,
  is_bft             boolean default false,
  tags               text[] default '{}',
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);

create table if not exists public.business_leaders (
  id                 bigint generated always as identity primary key,
  bft_id             text unique,
  name               text not null,
  tier               text default 'leader',
  network            text default 'jewish',
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
  jewish_basis       text,
  is_jewish          boolean default true,
  is_bft             boolean default false,
  tags               text[] default '{}',
  created_at         timestamptz default now(),
  updated_at         timestamptz default now()
);

drop trigger if exists set_updated_at on public.grassroots_business;
create trigger set_updated_at before update on public.grassroots_business
  for each row execute function extensions.moddatetime(updated_at);
drop trigger if exists set_updated_at on public.business_leaders;
create trigger set_updated_at before update on public.business_leaders
  for each row execute function extensions.moddatetime(updated_at);

-- RLS on, NO read policy -> private. service_role bypasses RLS for the viewer/proxy.
alter table public.grassroots_business enable row level security;
alter table public.business_leaders   enable row level security;

create index if not exists j_grassroots_stance_idx on public.grassroots_business (stance);
create index if not exists j_leaders_stance_idx    on public.business_leaders   (stance);
