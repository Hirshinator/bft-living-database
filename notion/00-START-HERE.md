# BFT Living Intelligence Database — Notion System of Record

**Generated:** 20 Jul 2026 · **Source:** the live database + *Builders For Tomorrow Project Notes 19 July 2026*

## How to import this into Notion

1. In Notion: **Settings → Import → Markdown & CSV**, or drag this whole `notion/` folder into a page.
2. The `.md` files become pages. Import them first — they're the narrative layer.
3. The `.csv` files in `../export/` become **Notion databases** (one per category). Import each separately so Notion types the columns properly.
4. After importing the CSVs, set **`bftId` as the unique key** on every database. It is the permanent join key back to the live app — never edit or delete it.

## What lives where

| Layer | Home | Why |
|---|---|---|
| **Records** (people, orgs, companies) | Notion databases from `../export/*.csv` | Sortable, filterable, relational |
| **Narrative** (strategy, methodology, notes) | These `.md` pages | Reads as documentation |
| **Live app + visualisations** | https://bft-living-database.vercel.app | Stance Map + Ecosystem Network can't be rebuilt in Notion |

The live app stays the source of truth for the graph views; Notion becomes the system of record for everything readable.

## Current contents

- **influencer** — 368 records
- **political** — 237 records
- **criteria** — 114 records
- **backlog** — 100 records
- **organization** — 90 records
- **business_leader** — 40 records
- **israeli_tech** — 38 records
- **business** — 35 records
- **nurture** — 11 records
- **sponsor** — 9 records
- **ecosystem** — 4 records

## ⚠ Before you share this workspace

Two things in the source notes must NOT be carried into a shared workspace — see `04-SECURITY-AND-PII.md`. Read that first.
