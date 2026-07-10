// Shared backend for the BFT Living Database.
// GET  -> load the stored JSON blob
// POST -> save a new JSON blob (body: { value: "<json string>" })
// Every request must include the shared passcode (header "x-passcode"),
// checked against the BFT_PASSCODE environment variable set in Vercel.
// Data is stored as a single string value under one Redis key via Upstash's
// REST API (works with either the Vercel KV marketplace integration or a
// direct Upstash integration -- both expose equivalent REST env vars).

const REDIS_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const REDIS_TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
const DATA_KEY = "bft_database";

async function redisGet(key) {
  const res = await fetch(`${REDIS_URL}/get/${encodeURIComponent(key)}`, {
    headers: { Authorization: `Bearer ${REDIS_TOKEN}` },
  });
  if (!res.ok) throw new Error(`Redis GET failed: ${res.status}`);
  const json = await res.json();
  return json.result;
}

async function redisSet(key, value) {
  const res = await fetch(`${REDIS_URL}/set/${encodeURIComponent(key)}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${REDIS_TOKEN}`, "Content-Type": "text/plain" },
    body: value,
  });
  if (!res.ok) throw new Error(`Redis SET failed: ${res.status}`);
}

module.exports = async (req, res) => {
  if (!process.env.BFT_PASSCODE) {
    res.status(500).json({ error: "Server misconfigured: BFT_PASSCODE is not set." });
    return;
  }
  if (!REDIS_URL || !REDIS_TOKEN) {
    res.status(500).json({ error: "Server misconfigured: no Redis/KV integration connected." });
    return;
  }

  const passcode = req.headers["x-passcode"];
  if (!passcode || passcode !== process.env.BFT_PASSCODE) {
    res.status(401).json({ error: "Invalid or missing passcode." });
    return;
  }

  try {
    if (req.method === "GET") {
      const value = await redisGet(DATA_KEY);
      res.status(200).json({ value: value || null });
      return;
    }
    if (req.method === "POST") {
      const value = req.body && req.body.value;
      if (typeof value !== "string") {
        res.status(400).json({ error: "Missing 'value' string in request body." });
        return;
      }
      await redisSet(DATA_KEY, value);
      res.status(200).json({ ok: true });
      return;
    }
    res.status(405).json({ error: "Method not allowed." });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message || e) });
  }
};
