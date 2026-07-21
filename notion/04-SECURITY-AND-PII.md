# Handling this data responsibly

*PII = "personally identifiable information" — names tied to contact details, private info, or in this case, political stance ratings. Please read before adding people or sharing access.*

This database rates named individuals by political stance. That's legitimate research on public figures — but combined with contact details it becomes sensitive, so we handle it carefully.

## The core rules

- **Public figures only.** We track people because of their public platform and public positions. We do not build profiles on private individuals.
- **Keep ratings and contact info separate.** Stance ratings live in the database; personal contact details (emails, phone numbers) belong in a **separate, restricted** place — never mixed into shared narrative pages.
- **Default to restricted.** New Notion pages and shared views should start private, not workspace-wide. Widen access deliberately.
- **The mirror test.** Before adding someone to a view others can see, ask: *would this hold up if that person read their own entry?* If not, reconsider the framing or the evidence.

## Credentials

- The app passcode and any API tokens belong **only** in their secure home (Vercel environment variables, a local secrets file) — never in Notion, chat, email, or any shared document.
- If a credential is ever exposed, **rotate it** and treat the old one as compromised.

## Why it matters

BFT operates thoughtfully and out of the spotlight. A well-sourced map of allies and adversaries is a real strategic asset — and exactly the kind of thing to steward carefully. When in doubt, keep it restricted and ask.
