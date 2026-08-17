# BFT + Jewish business networks — Supabase setup

Two Supabase projects. Each has two tables: `grassroots_business` + `business_leaders`.

| Project | Tables | Read access | Wired to |
|---|---|---|---|
| **BFT** | grassroots_business, business_leaders | public (anon read) | 2 new tabs in the Vercel app |
| **Jewish** | grassroots_business, business_leaders | **private** (service-role only) | standalone passcode-gated viewer |

Overlap between the two is tracked with `is_bft` / `is_jewish` flags + a `tags[]` column,
so a business that belongs to both is reconcilable across the projects.

## One-time setup (you do this — I can't create the projects)

1. Create two free projects at supabase.com: name them **bft** and **jewish**.
2. **BFT project** → SQL Editor → paste & run `schema_bft.sql`, then `seed_bft_grassroots.sql`,
   then `seed_bft_leaders.sql`. (123 rows: 3 grassroots + 120 leaders — pulled live from the app data.)
3. **Jewish project** → SQL Editor → paste & run `schema_jewish.sql`. The two Jewish seed files
   are empty templates on purpose — religion isn't inferred; fill them from a sourced list.
4. Send me, or set in Vercel (Project → Settings → Environment Variables):
   - `SUPABASE_BFT_URL` and `SUPABASE_BFT_ANON_KEY`  (BFT project → Settings → API)
   - `SUPABASE_JEWISH_URL` and `SUPABASE_JEWISH_SERVICE_KEY`  (Jewish project → keep the
     service key server-side only; never in client code)

Once those env vars exist, I wire the two BFT tabs + the standalone Jewish viewer and deploy.

## Format lineage — Aleph's "The Spreadsheet"

The investor/operator columns (`investor_kind`, `activity_level`, `notable_investments`,
`when_to_approach`, `follow_on`, `self_guidelines`, `min/max_investment`, `primary_interest`)
are **design ideas** adapted from Eden Shochat's "The Spreadsheet" (Aleph VC). Its smart moves:
activity-level to separate the active from the titled; proof-of-activity over self-description;
a self-authored guidelines column only the subject edits; contact/criteria pushed right to cut spam.

**We did NOT import its data.** That sheet carries an explicit restriction against being copied or
aggregated by any organization, and its investor tab is full of personal emails. Israeli investors
we track are added from public/first-party sources with public contact channels only.

## Re-generating the BFT seed

`seed_bft_*.sql` is generated from the master HTML — re-run after data changes:

```bash
python3 tools/supabase_seed.py
```
