// Render a Notion page as HTML via the official Notion API.
// Notion refuses inline iframes (X-Frame-Options: SAMEORIGIN), so instead of embedding
// notion.site we read the page's blocks and return native HTML the app styles itself.
//
// Setup (Vercel -> Settings -> Environment Variables), then redeploy:
//   NOTION_TOKEN    -> an internal integration secret (notion.so/my-integrations)
//   NOTION_PAGE_ID  -> optional; defaults to the BFT page id below
// The page must be shared with that integration (page -> ... -> Connections -> add it).

const TOKEN = process.env.NOTION_TOKEN;
const PAGE_ID = process.env.NOTION_PAGE_ID || "3a369e5a893f80c0a7e1eaaf4a94ba95";
const NOTION_VERSION = "2022-06-28";

async function napi(path) {
  const res = await fetch("https://api.notion.com/v1" + path, {
    headers: { Authorization: `Bearer ${TOKEN}`, "Notion-Version": NOTION_VERSION },
  });
  if (!res.ok) throw new Error(`Notion API ${res.status}: ${(await res.text()).slice(0, 300)}`);
  return res.json();
}

async function getBlocks(blockId, depth) {
  if (depth > 6) return [];               // guard against runaway nesting
  let out = [], cursor = null;
  do {
    const qs = "?page_size=100" + (cursor ? `&start_cursor=${cursor}` : "");
    const data = await napi(`/blocks/${blockId}/children${qs}`);
    out = out.concat(data.results || []);
    cursor = data.has_more ? data.next_cursor : null;
  } while (cursor);
  for (const b of out) {
    if (b.has_children) b._children = await getBlocks(b.id, (depth || 0) + 1);
  }
  return out;
}

function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

function rich(rt) {
  return (rt || []).map((t) => {
    let x = esc(t.plain_text);
    const a = t.annotations || {};
    if (a.code) x = `<code>${x}</code>`;
    if (a.bold) x = `<b>${x}</b>`;
    if (a.italic) x = `<i>${x}</i>`;
    if (a.underline) x = `<u>${x}</u>`;
    if (a.strikethrough) x = `<s>${x}</s>`;
    if (t.href) x = `<a href="${esc(t.href)}" target="_blank" rel="noopener">${x}</a>`;
    return x;
  }).join("");
}

function render(blocks) {
  let html = "", listType = null, buf = [];
  const flush = () => { if (buf.length) { html += `<${listType}>${buf.join("")}</${listType}>`; buf = []; listType = null; } };
  for (const b of blocks || []) {
    const t = b.type, d = b[t] || {};
    if (t === "bulleted_list_item" || t === "numbered_list_item") {
      const lt = t === "bulleted_list_item" ? "ul" : "ol";
      if (listType && listType !== lt) flush();
      listType = lt;
      buf.push(`<li>${rich(d.rich_text)}${b._children ? render(b._children) : ""}</li>`);
      continue;
    }
    flush();
    switch (t) {
      case "paragraph": html += `<p>${rich(d.rich_text) || "&nbsp;"}</p>`; break;
      case "heading_1": html += `<h1>${rich(d.rich_text)}</h1>`; break;
      case "heading_2": html += `<h2>${rich(d.rich_text)}</h2>`; break;
      case "heading_3": html += `<h3>${rich(d.rich_text)}</h3>`; break;
      case "quote": html += `<blockquote>${rich(d.rich_text)}</blockquote>`; break;
      case "callout": html += `<div class="callout">${d.icon && d.icon.emoji ? d.icon.emoji + " " : ""}${rich(d.rich_text)}${b._children ? render(b._children) : ""}</div>`; break;
      case "to_do": html += `<div><input type="checkbox" disabled ${d.checked ? "checked" : ""}> ${rich(d.rich_text)}</div>`; break;
      case "toggle": html += `<details><summary>${rich(d.rich_text)}</summary>${b._children ? render(b._children) : ""}</details>`; break;
      case "code": html += `<pre><code>${esc((d.rich_text || []).map((x) => x.plain_text).join(""))}</code></pre>`; break;
      case "divider": html += "<hr>"; break;
      case "image": { const u = d.type === "external" ? (d.external || {}).url : (d.file || {}).url; if (u) html += `<img src="${esc(u)}" alt="">`; if ((d.caption || []).length) html += `<div style="font-size:12px;opacity:.6">${rich(d.caption)}</div>`; break; }
      case "bookmark": case "embed": html += `<p><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a></p>`; break;
      case "child_page": html += `<h3>&#128196; ${esc(d.title)}</h3>${b._children ? render(b._children) : ""}`; break;
      case "table": if (b._children) html += `<table>${b._children.map((r) => `<tr>${((r.table_row || {}).cells || []).map((c) => `<td>${rich(c)}</td>`).join("")}</tr>`).join("")}</table>`; break;
      case "column_list": case "column": if (b._children) html += render(b._children); break;
      default: if (d.rich_text) html += `<p>${rich(d.rich_text)}</p>`; else if (b._children) html += render(b._children);
    }
  }
  flush();
  return html;
}

module.exports = async (req, res) => {
  if (!TOKEN) { res.status(500).json({ error: "NOTION_TOKEN not set. Add it in Vercel env vars and share the page with the integration." }); return; }
  try {
    const blocks = await getBlocks(PAGE_ID, 0);
    const html = render(blocks);
    res.setHeader("Cache-Control", "s-maxage=300, stale-while-revalidate=600"); // 5-min edge cache
    res.status(200).json({ html, blocks: blocks.length });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
};
