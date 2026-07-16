// Shared backend for the BFT Living Database.
// GET  -> load the database as a JSON blob
// POST -> save it back (body: { value: "<json string>" })
// Every request must include the shared passcode (header "x-passcode"),
// checked against the BFT_PASSCODE environment variable set in Vercel.
//
// TWO MODES:
//
//  1. AIRTABLE MODE (active when AIRTABLE_TOKEN + AIRTABLE_BASE_ID are set).
//     Airtable is the single source of truth. This function reads and writes it
//     directly, so Airtable and the web app are always the same data -- there is
//     no second copy and therefore nothing that can diverge. Redis is demoted to
//     a short read cache, which is what Airtable's own docs recommend for read
//     volume (the API allows only 5 requests/second per base; a 429 locks you
//     out for 30 seconds).
//
//  2. BLOB MODE (the original, used when the Airtable vars are absent).
//     One JSON string in Redis. Kept as a fallback so the app keeps working
//     unchanged until the Airtable base is actually ready.
//
// Why not sync two databases? The records had no stable IDs -- they were keyed
// by name, and names both collide (Mike Garcia vs. Chuy Garcia) and change.
// Airtable mints a permanent record id, which is exactly the missing piece: we
// round-trip it as _id so a save knows precisely which row it is updating.

const REDIS_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const REDIS_TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
const DATA_KEY = "bft_database";
const CACHE_KEY = "bft_airtable_cache";
const CACHE_TTL = 10; // seconds -- an Airtable edit shows up in the app within this

const AT_TOKEN = process.env.AIRTABLE_TOKEN;
const AT_BASE = process.env.AIRTABLE_BASE_ID;
const AIRTABLE_MODE = Boolean(AT_TOKEN && AT_BASE);

// Curated categories only. The LinkedIn network_* tables stay backend-only and
// are never pushed to Airtable, per the standing instruction.
const TABLES = [
  "influencer", "organization", "business", "ecosystem", "political",
  "sponsor", "israeli_tech", "nurture", "criteria", "backlog",
];

/* ------------------------------- redis ---------------------------------- */

async function redisGet(key) {
  const res = await fetch(`${REDIS_URL}/get/${encodeURIComponent(key)}`, {
    headers: { Authorization: `Bearer ${REDIS_TOKEN}` },
  });
  if (!res.ok) throw new Error(`Redis GET failed: ${res.status}`);
  return (await res.json()).result;
}

async function redisSet(key, value, ttlSeconds) {
  const url = ttlSeconds
    ? `${REDIS_URL}/set/${encodeURIComponent(key)}?EX=${ttlSeconds}`
    : `${REDIS_URL}/set/${encodeURIComponent(key)}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${REDIS_TOKEN}`, "Content-Type": "text/plain" },
    body: value,
  });
  if (!res.ok) throw new Error(`Redis SET failed: ${res.status}`);
}

/* ------------------------------ airtable -------------------------------- */

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Airtable allows 5 req/s per base and answers a burst with a 429 that costs 30
// seconds. Stay under it deliberately rather than discovering the ceiling.
let lastCall = 0;
async function atFetch(path, options = {}, attempt = 0) {
  const gap = Date.now() - lastCall;
  if (gap < 220) await sleep(220 - gap);
  lastCall = Date.now();

  const res = await fetch(`https://api.airtable.com/v0/${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${AT_TOKEN}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (res.status === 429 && attempt < 3) {
    await sleep(30000);
    return atFetch(path, options, attempt + 1);
  }
  if (!res.ok) {
    throw new Error(`Airtable ${options.method || "GET"} ${path} -> ${res.status}: ${(await res.text()).slice(0, 300)}`);
  }
  return res.json();
}

async function atListAll(table) {
  const rows = [];
  let offset;
  do {
    const qs = new URLSearchParams({ pageSize: "100" });
    if (offset) qs.set("offset", offset);
    const page = await atFetch(`${AT_BASE}/${encodeURIComponent(table)}?${qs}`);
    for (const rec of page.records) rows.push({ _id: rec.id, ...rec.fields });
    offset = page.offset;
  } while (offset);
  return rows;
}

async function readAll() {
  const data = {};
  for (const t of TABLES) {
    try {
      data[t] = await atListAll(t);
    } catch (e) {
      // A table that doesn't exist yet is not fatal -- it just isn't imported.
      if (!String(e.message).includes("404") && !String(e.message).includes("NOT_FOUND")) throw e;
      data[t] = [];
    }
  }
  return data;
}

function chunk(arr, n) {
  const out = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
}

// Write back only what actually changed. A full rewrite of 713 records would be
// ~72 requests and ~15s against the rate limit; a normal edit touches one row.
async function writeAll(incoming) {
  const summary = { created: 0, updated: 0, deleted: 0 };

  for (const t of TABLES) {
    const rows = incoming[t];
    if (!Array.isArray(rows)) continue;

    let existing;
    try {
      existing = await atListAll(t);
    } catch (e) {
      if (String(e.message).includes("404") || String(e.message).includes("NOT_FOUND")) continue;
      throw e;
    }
    const before = new Map(existing.map((r) => [r._id, r]));

    const creates = [];
    const updates = [];
    for (const row of rows) {
      const { _id, ...fields } = row;
      // Airtable rejects unknown/empty keys; send only real, non-empty values.
      const clean = {};
      for (const [k, v] of Object.entries(fields)) {
        if (v !== undefined && v !== null && v !== "") clean[k] = typeof v === "string" ? v : String(v);
      }
      if (_id && before.has(_id)) {
        const prev = before.get(_id);
        const changed = Object.keys(clean).some((k) => prev[k] !== clean[k]) ||
          Object.keys(prev).some((k) => k !== "_id" && !(k in clean) && prev[k] !== "");
        if (changed) updates.push({ id: _id, fields: clean });
        before.delete(_id);
      } else {
        creates.push({ fields: clean });
      }
    }

    for (const batch of chunk(updates, 10)) {
      await atFetch(`${AT_BASE}/${encodeURIComponent(t)}`, {
        method: "PATCH", body: JSON.stringify({ records: batch, typecast: true }),
      });
      summary.updated += batch.length;
    }
    for (const batch of chunk(creates, 10)) {
      await atFetch(`${AT_BASE}/${encodeURIComponent(t)}`, {
        method: "POST", body: JSON.stringify({ records: batch, typecast: true }),
      });
      summary.created += batch.length;
    }
    // Anything still in `before` was removed in the app.
    const gone = [...before.keys()];
    for (const batch of chunk(gone, 10)) {
      const qs = batch.map((id) => `records[]=${id}`).join("&");
      await atFetch(`${AT_BASE}/${encodeURIComponent(t)}?${qs}`, { method: "DELETE" });
      summary.deleted += batch.length;
    }
  }
  return summary;
}

/* ------------------------------- handler -------------------------------- */

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
      if (!AIRTABLE_MODE) {
        const value = await redisGet(DATA_KEY);
        res.status(200).json({ value: value || null, mode: "blob" });
        return;
      }
      const cached = await redisGet(CACHE_KEY).catch(() => null);
      if (cached) {
        res.status(200).json({ value: cached, mode: "airtable", cached: true });
        return;
      }
      const value = JSON.stringify(await readAll());
      await redisSet(CACHE_KEY, value, CACHE_TTL).catch(() => {});
      res.status(200).json({ value, mode: "airtable", cached: false });
      return;
    }

    if (req.method === "POST") {
      const value = req.body && req.body.value;
      if (typeof value !== "string") {
        res.status(400).json({ error: "Missing 'value' string in request body." });
        return;
      }
      if (!AIRTABLE_MODE) {
        await redisSet(DATA_KEY, value);
        res.status(200).json({ ok: true, mode: "blob" });
        return;
      }
      let parsed;
      try {
        parsed = JSON.parse(value);
      } catch {
        res.status(400).json({ error: "'value' is not valid JSON." });
        return;
      }
      const summary = await writeAll(parsed);
      // Drop the read cache so the next GET reflects the write immediately.
      await redisSet(CACHE_KEY, "", 1).catch(() => {});
      res.status(200).json({ ok: true, mode: "airtable", ...summary });
      return;
    }

    res.status(405).json({ error: "Method not allowed." });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
};
