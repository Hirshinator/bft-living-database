# ⚠ Security & PII — read before sharing this workspace

Two items found in *Builders For Tomorrow Project Notes 19 July 2026* were **deliberately excluded** from every generated file. They are flagged here rather than reproduced.

## 1. A live credential is sitting in the notes document
The notes contain the **BFT_PASSCODE in plaintext** — the passcode gating the live Vercel app.

**Do this:**
- Delete that line from the Word document.
- **Rotate the passcode** in Vercel (Settings → Environment Variables → `BFT_PASSCODE`) and redeploy. Treat the current one as compromised — it has been sitting in a synced document.
- Never paste it into Notion, chat, or any shared file. Nobody needs it written down; it belongs in Vercel's env vars only.

## 2. Personal contact details
The notes contain at least one **personal mobile number** (a team member's WhatsApp) plus donor and funding-status details from interview notes.

**Do this:**
- Keep contact details out of any Notion page that gets shared beyond the inner circle.
- If contacts are needed, put them in a **separate, restricted** Notion database — not in the narrative pages.

## 3. Standing rule for this project
The database rates named private individuals by political stance. Combined with contact details or faces, that is a sensitive dossier for an organisation that "operates under the radar."

- Keep **stance ratings** and **contact information** in separate, separately-permissioned places.
- Default new Notion pages to **restricted**, not workspace-wide.
- Before adding anyone to a shared view, ask whether you would be comfortable with that person reading their own entry.
