// Live feed: aggregate current headlines from Google News RSS for coalition-relevant queries.
// No API key needed; server-side fetch avoids browser CORS. Cached ~10 min at the edge.
// Optional override: set FEED_QUERIES env var to a comma-separated list to tune the topics.

const DEFAULT_QUERIES = [
  "pro-Israel evangelical",
  "Christians United for Israel",
  "Christian Zionist Israel",
  "evangelical support for Israel",
  "pastor stands with Israel",
  "campus antisemitism",
];

function decode(s) {
  return String(s || "")
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .trim();
}

function tag(block, name) {
  const m = block.match(new RegExp("<" + name + "[^>]*>([\\s\\S]*?)</" + name + ">"));
  return m ? decode(m[1]) : "";
}

function parseItems(xml, query) {
  const out = [];
  const re = /<item>([\s\S]*?)<\/item>/g;
  let m;
  while ((m = re.exec(xml))) {
    const b = m[1];
    let title = tag(b, "title");
    let source = tag(b, "source");
    // Google News titles are "Headline - Source"; split the source off if not given separately.
    if (!source && title.includes(" - ")) { const p = title.split(" - "); source = p.pop().trim(); title = p.join(" - ").trim(); }
    out.push({ title, link: tag(b, "link"), date: tag(b, "pubDate"), source: source || "Google News", query });
  }
  return out;
}

module.exports = async (req, res) => {
  try {
    const queries = (process.env.FEED_QUERIES ? process.env.FEED_QUERIES.split(",").map(s => s.trim()).filter(Boolean) : DEFAULT_QUERIES);
    let all = [];
    await Promise.all(queries.map(async (q) => {
      const url = "https://news.google.com/rss/search?q=" + encodeURIComponent(q) + "&hl=en-US&gl=US&ceid=US:en";
      try {
        const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (compatible; BFTFeed/1.0)" } });
        if (r.ok) all = all.concat(parseItems(await r.text(), q));
      } catch (e) { /* skip a failing query */ }
    }));
    // Dedupe by title, sort newest first, cap.
    const seen = new Set(), uniq = [];
    all.sort((a, b) => new Date(b.date) - new Date(a.date));
    for (const it of all) { const k = it.title.toLowerCase(); if (it.title && !seen.has(k)) { seen.add(k); uniq.push(it); } }
    res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate=1800");
    res.status(200).json({ items: uniq.slice(0, 40), queries });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
};
