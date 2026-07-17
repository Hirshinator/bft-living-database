# BFT Living Database — Cross-Audit Brief for Another LLM

**For:** Grok, Gemini, ChatGPT, or any model Andy hands this to.
**From:** Claude (Opus), which built most of this database.
**Date:** 17 Jul 2026.
**Purpose:** Andy wants an independent model to (1) catch pro-Israel/conservative sentiment I may have misread, (2) find factual mistakes I made, (3) reach pages and data I couldn't, and (4) check my work against my own known biases. This document tells you where to look. **I wrote it to expose my own errors, not hide them.** Treat it as an adversarial checklist against my output.

---

## 1. What the project is (context you need)

The BFT Living Database is a single-file web app tracking the pro-Israel / evangelical-Zionist alliance ecosystem for **Builders for Tomorrow (BFT)**, a venture-philanthropy nonprofit building a new **Evangelical Engagement** program. It is both an operational tool and a **pitch artifact** for donors who have funded evangelical outreach before without seeing returns.

- **Live app:** https://bft-living-database.vercel.app (passcode-gated)
- **Data snapshot for you to audit:** `export/BFT_Living_Database.xlsx` (one tab per category) and `export/*.csv`. ~720 records across influencer (295), organization (85), business (34), political (130), israeli_tech (38), sponsor (9), ecosystem (4), nurture (8), criteria (87), backlog (61).
- **Every record has a permanent `bftId`** — use it to reference specific rows in your findings.
- **The `criteria` tab is the rulebook.** Read it first; it encodes the scoring gates and methodology. The `backlog` tab already lists many known gaps.

### The two gates (the core methodology, so you can check my application of it)
- **Gate 1 — Loyalty, measured by COST PAID, not statements.** Anyone can post pro-Israel content (a $1.5M/month paid influence op does exactly that — see the Parscale/TIME entry in criteria). Real allies paid a price: took incoming from the Tucker/Candace/Fuentes wing, spoke when it was unpopular in their milieu, did it *unpaid*, did it *pre-Oct-7*. Blank `costPaid` = **unproven, not loyal**.
- **Gate 2 — Talent, measured by holding an audience**, not by alignment. "Would you watch them if you disagreed with them?"
- **Organic > paid**, proxied by sub-30K follower count and by earliest content already being on-mission.

---

## 2. My known mistakes and shallow spots (audit these first)

I have made real errors on this project. Several reached production. Here is the honest list — verify whether I've actually fixed them, and whether there are more like them.

### Verification & capability failures (pattern: I asserted limits without testing)
1. **I shipped three JavaScript syntax errors to production** that broke the entire live app (a mangled escaped quote, `related=` for `related:`, and a name containing literal quotes concatenated into a URL). My "balance check" (counting braces) passed while the app was fully broken. **Now** guarded by `tools/validate.py` (real parse via JavaScriptCore). *Check: does the current file actually parse and render every tab?*
2. **I wrongly claimed I couldn't access social platforms.** YouTube (including channel search) and TikTok are in fact fetchable; the false claim had hidden a **~50× audience error** (Lance Johnston recorded at "100K+ TikTok", actually 2,148). *You may be able to reach X/Twitter and Instagram follower counts, which I mostly cannot — see §3.*
3. **I wrongly claimed congress.gov was inaccessible** (curl gets a 403; a real browser loads it fine). Three-for-three on false capability claims. *Assume any "blocked/can't" note in my backlog is untested until proven.*
4. **The entire Nurture category never rendered** — I put the data in the schema array instead of the data array. The category Andy called "one of the most significant" was invisible for weeks. *Check every `VISIBLE_CATEGORIES` tab actually has data.*

### Factual / sourcing errors
5. **I used Wikipedia as a source throughout**, then found — when forced to re-source — that it had hidden real errors. **Wikipedia is now banned here** (documented Israel-topic editor bias; it declared the ADL an "unreliable source"). *Check I left zero Wikipedia citations, and that my replacements are actually primary.*
6. **Stale acquisition facts:** I described **CyberArk** and **Wiz** as independent public companies. Both were acquired months earlier (Palo Alto/CyberArk Feb 2026; Google/Wiz Mar 2026). Re-sourcing to SEC EDGAR caught it. *Check other companies for stale status — I only rigorously re-checked israeli_tech.*
7. **Category errors surfaced by SEC data:** Amdocs is incorporated in the UK (Guernsey), not Israel; SentinelOne and Lemonade are Delaware corporations. *Verify my incorporation/HQ fields against primary filings.*
8. **The "No podcast (TARGET)" tag was wrong for at least 13 of 61 people** — Riley Gaines (196 episodes), Ben Ferguson (2,032), etc. already host active podcasts. I'd asserted it without checking. *Re-run a podcast check on the whole influencer set, not just the 61 (I used the free iTunes Search API; you may do better).*
9. **Name-collision risk is everywhere.** My naive name-matching once merged Mike Garcia with Chuy García, Speaker Mike Johnson with Hank Johnson. I fixed the political tab via bioguide IDs, but the same risk lurks in any name-based join. *Spot-check for conflated identities.*

### Coverage gaps (I didn't dig deep enough)
10. **311 of 585 entries started with no clickable source; I got roughly halfway.** Many `source` fields hold provenance notes ("Batch 8, Jul 2026"), not citations. *Every claim should trace to a real URL; flag the ones that still don't.*
11. **Only ~59 of 292 influencers have a social handle.** This blocks both audience verification and the organic/sub-30K test. *Highest-value backfill on the board.*
12. **~211 of 233 "pro" influencers have no recorded cost signal** — the database records *agreement*, not *loyalty*. This is the central gap. *For any high-profile "pro" entry, ask: what did it actually cost them? If nothing, they're unproven.*
13. **Government data is House-only.** No Senate, state, local, or gubernatorial voting records yet, despite the instruction covering them.
14. **IAF Top-50 Christian Allies 2021–2024 (~250 names) never processed** — only 2025.
15. **Audience numbers are largely unverified.** The Johnston 50× error is the canary; most figures are still asserted.
16. **Network/connection edges are shallow** — auto-derived from name-matching in evidence text, not real relationship data.

### Judgment calls where I may be wrong (your bias check matters most here)
17. I set `stance` on ~292 influencers. **I have a measured ~43% left-lean** (WaPo Jun 2026). I may have under-credited right-coded allies or over-flagged conservative conduct. *This is the single most valuable thing you can re-check — see §4.*
18. **Unresolved conflicts I flagged but didn't resolve:** e.g. George F. Will criticizes JD Vance — positive under the "anti-drift" criterion, negative under the "prefer Vance allies" criterion. *Adjudicate these.*
19. **A licensing refusal Andy disagreed with:** I declined bulk extraction from Start-Up Nation Central on terms-of-use grounds. Andy considers this over-cautious. *This is a values call, not a capability one — flag whether you'd treat it differently, but note it's a genuine ToU question, not a capability gap.*

---

## 3. Where you may have access I don't (please try these)

- **X/Twitter follower counts and post history** — I mostly cannot read these; they're the input to the sub-30K organic test and to handle backfill for ~230 influencers.
- **Instagram audience data** — same.
- **Paywalled / hard-blocked pages** — e.g. the Washington Post is Akamai-blocked even to my browser tool. If you can read paywalled reporting, you'll reach sources I flagged as unreachable.
- **Real-time sentiment** — I assess from static evidence. If you have live search, check whether any "pro" entry has recently drifted (the Marjorie Taylor Greene problem: lifetime averages hide recent turns).
- **The Parscale paid-influencer network** — the TIME article names it but not the full participant list. If you can identify who's in it, cross-check against our "pro" roster: paid participants fail Gate 1.

---

## 4. The specific sentiment/bias re-check I'm asking for

Because I have a documented left lean and this project assesses right-coded, pro-Israel sentiment, please **re-score a sample of my stance calls and tell me where you disagree**:

1. Pull ~25 influencers I marked `stance:"pro"` and ~10 I marked `neutral`/`yellowflag`/`hostile`. For each, form your own view from public evidence and **flag every disagreement**.
2. Pay special attention to: (a) right-coded figures I may have under-credited or wrongly flagged; (b) anyone I called `pro` who is actually a paid amplifier (Gate 1); (c) anyone I called `neutral` who has a real cost-paid record I missed.
3. **Bias landscape, honestly (WaPo Jun 2026):** Gemini tested *most balanced*; Grok, despite conservative branding, still leaned left on average; ChatGPT leaned left most; Claude (me) ~43% left. **So the right method is multiple models, and treating any Claude-vs-you disagreement as a manual-review flag** — not treating one model as the neutral truth.

---

## 5. How to return your findings

Reference each finding by `bftId` and category. Ideal format: a list of `{bftId, my_call, your_call, why, source_url}`. Anything with a primary-source URL I can verify and merge fast; anything without, I'll queue for manual check. **Disagreements are the point** — the more specific, the more useful.
