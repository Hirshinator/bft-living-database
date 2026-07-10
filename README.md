# BFT Living Database — shared deployment

A passcode-gated, shared version of the BFT Living Intelligence Database. Everyone with the passcode reads and writes the same data (last save wins if two people edit at the same moment — there's no live real-time sync).

## One-time setup (Vercel dashboard)

1. **Import this repo into Vercel**: vercel.com → Add New → Project → import this GitHub repo. No build settings needed — it's a static `index.html` plus one serverless function in `api/`.
2. **Add a Redis/KV integration**: in the Vercel project → Storage tab → connect an Upstash Redis (or Vercel KV) database. This auto-populates the `KV_REST_API_URL` / `KV_REST_API_TOKEN` (or `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`) environment variables — the API function reads either naming.
3. **Set the shared passcode**: Project → Settings → Environment Variables → add `BFT_PASSCODE` with whatever passcode you want to share with the team. Redeploy after adding it (Vercel only picks up new env vars on the next deploy).
4. Visit the deployed URL, enter the passcode once — it's remembered per-browser after that (stored in `localStorage`), so teammates only enter it once per device.

## What this is not

- **Not real security.** The passcode is a shared secret checked server-side, which stops casual/opportunistic access, but anyone with it has full read/write access and there's no per-person login or audit trail. Don't put anything in here you wouldn't want visible to everyone who has the passcode.
- **Not live-sync.** No websockets/real-time updates — data loads on page load and saves on edit, like the original local version, just now backed by a shared database instead of `localStorage`.

## Local file vs. this deployment

The standalone file (`BFT_Living_Database_6.html`, kept separately in Downloads) still works fully offline with no passcode, saving to that one browser's `localStorage` only. This repo is a separate, shared deployment for team use — the two don't sync with each other.
