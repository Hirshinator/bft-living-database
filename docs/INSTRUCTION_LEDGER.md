# BFT Living Database — Instruction Completion Ledger

**Standing rule (Andy, 17 Jul 2026):** follow every instruction — including earlier ones — through to *full* completion; and where something could not be completed, say so and log it here so it's not silently dropped.

**Status key:** ✅ done · ◑ partial · ⛔ blocked (needs Andy or a capability) · ○ open/queued
**Last reconciled:** 17 Jul 2026. This ledger is the master accountability list; the app's `backlog` tab holds the operational detail.

---

## A. Adds (named people / orgs / companies)
- ✅ The large influencer/org/business/political batches across the project (692→~720 entries). Cross-checked 17 Jul: **115 of 119** explicitly-named entities present.
- ◑ **4 named adds still missing:** AmyMek (handle on file, entry not yet written), Shaida Rice, Troy Miller (confirm = NRB CEO), Adam Francisco (found — was stranded in the Nurture schema bug, now live).
- ✅ Recent batch (17 Jul): Pastor Grant, Scooter Braun, Isabella Redjai, Ben Domenech, Dana Loesch, George Will, Ellisa Allen, Natasha Hausdorff (boosted), Jackie Chea, Ally Kiss, Armand Klein, Jake Hilton, Parscale/Yakoby/Sortor (tracked as phenomena).
- ⛔ **Free Press journalist roster** — org + 2 people added; the actual masthead (Bari Weiss, Nellie Bowles, et al.) not yet swept. Queued.
- ⛔ **IAF Top-50 Christian Allies 2021–2024** (~250 names) — only 2025 processed.
- ⛔ **"Everyone associated with" ColdSpark / JNS / RepublicanJobs / Ben Sasse network** — unbounded; needs a bounded roster source.

## B. Data enrichment (the current focus)
- ◑ **Follower counts across all platforms** — 12 X counts verified via browser (17 Jul); YouTube (20) + TikTok (4) verified accurate. **Binding constraint: only 74 of 603 entries have any handle; 529 need handle-finding first.**
- ⛔ **Instagram (8), LinkedIn (9), Facebook (2) counts** — login-walled; need Andy's session (login-assist workflow now defined).
- ○ **Handle-finding for 529 no-handle entries** — the dominant remaining job; start with highest-audience entries.
- ◑ **Sources** — 344/585 have a clickable source (was 311 unsourced; political/israeli_tech/sponsor complete). Influencer (178) + organization (59) remain.
- ⛔ **~211 of 233 "pro" influencers have no cost-paid signal** — the central gap; records agreement, not loyalty.

## C. Government data
- ✅ **House roll-call sweep 2015–2026** (6,332 votes) — red-line rule executed with the 3-tier disambiguation; political tab 22→130.
- ⛔ **Senate** roll-call sweep — not done (same free XML pipeline).
- ⛔ **State / local** legislature data — needs OpenStates key (Andy).
- ⛔ **Gubernatorial** — governors cast no votes; needs the signed-legislation method + their prior congressional records.
- ⛔ **"All LIVING officials" filter** — dataset has no death dates; needs Wikidata death-date join (Grijalva d. Mar 2025 is a known case).
- ⛔ **Pre-2015 votes** — not swept.

## D. Methodology / rules (criteria tab — mostly done)
- ✅ Two gates (loyalty=cost-paid, talent), organic>paid (sub-30K + earliest-content), stance system, congressional evidence, source hierarchy (Wikipedia banned), platform capability map, login-assist, LLM cross-check, paid-op/tainted-source rules.
- ✅ Nationality ranking + audience-geography-outranks-nationality + charisma override.
- ⛔ **Alliance Score rubric** — still awaiting Andy's signal weights; scores currently assigned ad hoc.

## E. Deployment / infrastructure
- ✅ Vercel + GitHub deploy, passcode gate, `jsc` validator (replaced brace-counting after 3 syntax errors reached prod), stable `bftId`s on all records.
- ✅ Google Sheets workbook + per-category CSVs (export/).
- ✅ Airtable-backed API **built and tested**; tabled by Andy until schema settles.
- ✅ LLM cross-audit brief (docs/LLM_CROSS_AUDIT_BRIEF.md).

## F. Roadmap (Phase 2 — captured, not started; correctly deferred until base is accurate)
- ○ **Live-data adaptive model** — poll principals (Trump/Vance/Rubio/Shapiro/Carlson) + influencers; classify new statements; discovery of emerging allies.
- ○ **Continuous self-audit + standing cross-LLM verification** — self-regenerating AI to-do list.
- ○ **Comment-network / grassroots discovery** (Andy, 17 Jul): identify accounts posting POSITIVE sentiment on ally posts (→ grassroots + emerging-influencer pipeline) and NEGATIVE sentiment on hostile posts (→ enemy-of-enemy allies). **Tested feasibility 17 Jul: reading a post's commenters requires a logged-in session** (X shows follower counts logged-out, but gates the timeline/replies behind login). Feasible via Andy's session + a Phase-2 scanner; not doable at scale logged-out.

## G. Things I could NOT complete, and why (the honest column)
1. **Instagram / LinkedIn / Facebook data** — login walls. *Fix: Andy logs in (Claude-in-Chrome or clears the wall).*
2. **Reading comment sections / commenter identities** — login-gated on X. *Fix: same.*
3. **Spotify / SoundCloud follower counts** — need authed APIs. *Apple Podcasts works.*
4. **claude.ai (regular-Claude) instruction history** — not readable from Claude Code, so instructions Andy gave there are invisible here. *Fix: Andy exports/pastes them.* **This is why this ledger may still be incomplete — it can only cover instructions given in Claude Code.**
5. **Start-Up Nation Central bulk extraction** — declined on licensing (their ToU forbids reuse). A values call, not a capability gap; flagged for Andy/other-LLM review.
6. **Senate/state/local/gubernatorial + pre-2015 gov data** — not yet run (capability exists; time/keys needed).
